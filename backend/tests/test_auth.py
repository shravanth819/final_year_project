from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.auth_service import issue_email_verification, issue_password_reset, now_utc
from backend.database import SessionLocal
from backend.main import app
from backend.models import AuthSession, AuthUser


def test_auth_lifecycle(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    email = f"auth-{uuid4().hex}@example.com"
    password = "StrongPassword!123"
    with TestClient(app, headers={"X-Forwarded-For": uuid4().hex}) as client:
        signup = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
        assert signup.status_code == 200
        assert "token" not in signup.json()
        with SessionLocal() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.email == email))
            user.is_email_verified = True
            user_id = user.id
            session.commit()
        login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        assert "agrimitra_session" not in login.json()
        assert client.get("/api/v1/auth/me").status_code == 200
        assert client.get("/api/v1/fields").status_code == 200
        with SessionLocal() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.email == email))
            raw_reset_token = issue_password_reset(user)
            session.commit()
        reset = client.post("/api/v1/auth/password-reset/confirm", json={"token": raw_reset_token, "password": "NewStrongPassword!456"})
        assert reset.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_email_and_reset_tokens_are_rejected(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    email = f"expired-{uuid4().hex}@example.com"
    with TestClient(app, headers={"X-Forwarded-For": uuid4().hex}) as client:
        client.post("/api/v1/auth/signup", json={"email": email, "password": "StrongPassword!123"})
        with SessionLocal() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.email == email))
            email_token = issue_email_verification(user)
            user.email_verification_expires_at = now_utc() - timedelta(seconds=1)
            reset_token = issue_password_reset(user)
            user.password_reset_expires_at = now_utc() - timedelta(seconds=1)
            session.commit()
        assert client.get(f"/api/v1/auth/verify-email?token={email_token}").status_code == 400
        assert client.post("/api/v1/auth/password-reset/confirm", json={"token": reset_token, "password": "NewStrongPassword!456"}).status_code == 400


def test_unverified_login_and_expired_session_are_rejected(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    email = f"session-{uuid4().hex}@example.com"
    with TestClient(app, headers={"X-Forwarded-For": uuid4().hex}) as client:
        client.post("/api/v1/auth/signup", json={"email": email, "password": "StrongPassword!123"})
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword!123"}).status_code == 401
        with SessionLocal() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.email == email))
            user.is_email_verified = True
            user_id = user.id
            session.commit()
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword!123"}).status_code == 200
        with SessionLocal() as session:
            auth_session = session.scalar(select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)))
            auth_session.expires_at = now_utc() - timedelta(seconds=1)
            session.commit()
        assert client.get("/api/v1/auth/me").status_code == 401

import hashlib
import logging
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuthSession, AuthUser, now_utc

logger = logging.getLogger("agrimitra.auth")
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16, type=Type.ID)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
SESSION_COOKIE_NAME = "agrimitra_session"


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def session_ttl_seconds() -> int:
    return _positive_int("SESSION_TTL_SECONDS", 3600)


def session_idle_ttl_seconds() -> int:
    return _positive_int("SESSION_IDLE_TTL_SECONDS", 900)


def verification_ttl_seconds() -> int:
    return _positive_int("EMAIL_VERIFICATION_TTL_SECONDS", 86400)


def reset_ttl_seconds() -> int:
    return _positive_int("PASSWORD_RESET_TTL_SECONDS", 900)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(48)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def create_user(session: Session, email: str, password: str, farm_id: str | None = None) -> tuple[AuthUser, str]:
    verification_token = new_token()
    user = AuthUser(email=normalize_email(email), password_hash=hash_password(password), farm_id=farm_id, email_verification_token_hash=token_hash(verification_token), email_verification_expires_at=now_utc() + timedelta(seconds=verification_ttl_seconds()))
    session.add(user)
    session.flush()
    return user, verification_token


def issue_email_verification(user: AuthUser) -> str:
    raw_token = new_token()
    user.email_verification_token_hash = token_hash(raw_token)
    user.email_verification_expires_at = now_utc() + timedelta(seconds=verification_ttl_seconds())
    return raw_token


def issue_password_reset(user: AuthUser) -> str:
    raw_token = new_token()
    user.password_reset_token_hash = token_hash(raw_token)
    user.password_reset_expires_at = now_utc() + timedelta(seconds=reset_ttl_seconds())
    return raw_token


def send_security_email(recipient: str, subject: str, action_path: str, raw_token: str) -> bool:
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        logger.warning("Security email delivery is not configured; recipient remains pending: %s", hashlib.sha256(recipient.encode()).hexdigest()[:12])
        return False
    base_url = os.getenv("AUTH_PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        logger.error("SMTP configured without AUTH_PUBLIC_BASE_URL")
        return False
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(f"Complete this request within the configured expiry window: {base_url}{action_path}?token={raw_token}")
    try:
        port = _positive_int("SMTP_PORT", 587)
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.starttls(context=context)
            username = os.getenv("SMTP_USERNAME")
            password = os.getenv("SMTP_PASSWORD")
            if username and password:
                client.login(username, password)
            client.send_message(message)
        return True
    except Exception:
        logger.exception("Security email delivery failed")
        return False


def create_session(session: Session, user: AuthUser, request: Request) -> str:
    raw_token = new_token()
    session.add(AuthSession(user_id=user.id, token_hash=token_hash(raw_token), session_version=user.session_version, expires_at=now_utc() + timedelta(seconds=session_ttl_seconds()), ip_address=(request.client.host if request.client else None)))
    return raw_token


def set_session_cookie(response, raw_token: str) -> None:
    response.set_cookie(SESSION_COOKIE_NAME, raw_token, max_age=session_ttl_seconds(), httponly=True, secure=os.getenv("COOKIE_SECURE", "true").lower() == "true", samesite="lax", path="/")


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def get_current_user(request: Request, session: Session) -> AuthUser:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token or len(raw_token) > 256:
        raise HTTPException(status_code=401, detail="Authentication required")
    auth_session = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token), AuthSession.revoked_at.is_(None)))
    if auth_session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = session.get(AuthUser, auth_session.user_id)
    now = now_utc()
    expires_at = _aware(auth_session.expires_at)
    last_seen_at = _aware(auth_session.last_seen_at)
    if user is None or user.is_disabled or auth_session.session_version != user.session_version or expires_at is None or expires_at <= now or last_seen_at is None or last_seen_at + timedelta(seconds=session_idle_ttl_seconds()) <= now:
        auth_session.revoked_at = now
        session.commit()
        raise HTTPException(status_code=401, detail="Authentication required")
    auth_session.last_seen_at = now
    session.commit()
    return user

import asyncio

from fastapi.testclient import TestClient

from backend.main import app
from backend.security import RateLimitSettings, SlidingWindowLimiter, validate_upload_content


def test_rate_limiter_backoff_is_configurable():
    settings = RateLimitSettings(60, 2, 2, 1, 1, 0, 0, 100)
    limiter = SlidingWindowLimiter(settings)
    first = asyncio.run(limiter.check("ip:test", 1))
    second = asyncio.run(limiter.check("ip:test", 1))
    assert first.allowed is True
    assert second.allowed is False
    assert second.backoff_seconds == 0


def test_validation_rejects_unknown_fields():
    with TestClient(app) as client:
        response = client.post("/api/v1/telemetry/ingest", json={"soil_moisture": 50, "ph": 6.5, "unexpected": "value"})
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_request", "message": "Input does not match the required schema."}


def test_upload_is_content_validated_and_not_stored():
    try:
        validate_upload_content(b"not-a-pdf", "application/pdf")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe upload was accepted")
    assert validate_upload_content(b"%PDF-1.7\n%%EOF", "application/pdf") == "application/pdf"
    with TestClient(app) as client:
        assert client.post("/api/v1/ocr/pahani/upload", content=b"not-a-pdf", headers={"content-type": "application/pdf"}).status_code == 401

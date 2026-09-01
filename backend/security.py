import asyncio
import base64
import hashlib
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("agrimitra.security")


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _float_env(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class RateLimitSettings:
    window_seconds: int
    public_per_window: int
    user_per_window: int
    auth_ip_per_window: int
    auth_account_per_window: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    max_tracked_keys: int

    @classmethod
    def from_environment(cls):
        return cls(
            window_seconds=_int_env("RATE_LIMIT_WINDOW_SECONDS", 60),
            public_per_window=_int_env("RATE_LIMIT_PUBLIC_PER_WINDOW", 60),
            user_per_window=_int_env("RATE_LIMIT_USER_PER_WINDOW", 180),
            auth_ip_per_window=_int_env("RATE_LIMIT_AUTH_IP_PER_WINDOW", 10),
            auth_account_per_window=_int_env("RATE_LIMIT_AUTH_ACCOUNT_PER_WINDOW", 5),
            backoff_base_seconds=_float_env("RATE_LIMIT_BACKOFF_BASE_SECONDS", 1.0),
            backoff_max_seconds=_float_env("RATE_LIMIT_BACKOFF_MAX_SECONDS", 30.0),
            max_tracked_keys=_int_env("RATE_LIMIT_MAX_TRACKED_KEYS", 10000),
        )


@dataclass
class LimitDecision:
    allowed: bool
    retry_after: int = 0
    backoff_seconds: float = 0


class SlidingWindowLimiter:
    def __init__(self, settings: RateLimitSettings | None = None):
        self.settings = settings or RateLimitSettings.from_environment()
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._violations: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int) -> LimitDecision:
        now = time.monotonic()
        async with self._lock:
            if len(self._requests) > self.settings.max_tracked_keys:
                oldest_key = min(self._requests, key=lambda item: self._requests[item][0] if self._requests[item] else now)
                self._requests.pop(oldest_key, None)
                self._violations.pop(oldest_key, None)
            timestamps = self._requests[key]
            cutoff = now - self.settings.window_seconds
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) < limit:
                timestamps.append(now)
                self._violations[key] = 0
                return LimitDecision(True)
            self._violations[key] += 1
            backoff = min(self.settings.backoff_base_seconds * (2 ** (self._violations[key] - 1)), self.settings.backoff_max_seconds)
            retry_after = max(1, int(timestamps[0] + self.settings.window_seconds - now))
            return LimitDecision(False, retry_after=retry_after, backoff_seconds=backoff)


def client_ip(request: Request) -> str:
    if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def account_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()[:320]
    return "account:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def upload_limit_bytes() -> int:
    return _int_env("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)


def validate_upload_content(content: bytes, declared_type: str | None) -> str:
    if not content or len(content) > upload_limit_bytes():
        raise ValueError("upload is empty or exceeds the configured size limit")
    if content.startswith(b"%PDF-"):
        if b"%%EOF" not in content[-4096:]:
            raise ValueError("invalid PDF structure")
        if b"/JavaScript" in content or b"/JS" in content:
            raise ValueError("active PDF content is not allowed")
        return "application/pdf"
    try:
        from PIL import Image

        from io import BytesIO

        image = Image.open(BytesIO(content))
        image.verify()
        if image.width > 10000 or image.height > 10000:
            raise ValueError("image dimensions exceed the configured limit")
        detected = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
        if detected is None:
            raise ValueError("unsupported image format")
        return detected
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("unsupported or invalid upload") from error


def route_class(path: str, authenticated: bool) -> str:
    if path.startswith("/api/v1/auth/"):
        return "auth"
    if authenticated:
        return "user"
    return "public"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or SlidingWindowLimiter()

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in {"/health", "/api/v1/health"}:
            return await call_next(request)
        kind = route_class(request.url.path, bool(request.cookies.get("agrimitra_session") or request.headers.get("authorization") or request.headers.get("x-user-token")))
        if kind == "auth":
            limit = self.limiter.settings.auth_ip_per_window
        elif kind == "user":
            limit = self.limiter.settings.user_per_window
        else:
            limit = self.limiter.settings.public_per_window
        decision = await self.limiter.check(f"ip:{client_ip(request)}:{kind}", limit)
        if not decision.allowed:
            if decision.backoff_seconds:
                await asyncio.sleep(decision.backoff_seconds)
            return JSONResponse({"error": "rate limit exceeded", "message": "Please retry later."}, status_code=429, headers={"Retry-After": str(decision.retry_after)})
        if kind == "auth":
            identifier = request.headers.get("x-account-identifier") or request.query_params.get("account")
            if identifier is None:
                content_length = request.headers.get("content-length")
                if not content_length or (content_length.isdigit() and int(content_length) <= 65536):
                    try:
                        body = await request.json()
                        if isinstance(body, dict):
                            identifier = body.get("email") or body.get("username") or body.get("account")
                    except Exception:
                        identifier = None
            key = account_key(identifier)
            if key:
                account_decision = await self.limiter.check(key, self.limiter.settings.auth_account_per_window)
                if not account_decision.allowed:
                    if account_decision.backoff_seconds:
                        await asyncio.sleep(account_decision.backoff_seconds)
                    return JSONResponse({"error": "rate limit exceeded", "message": "Please retry later."}, status_code=429, headers={"Retry-After": str(account_decision.retry_after)})
        response = await call_next(request)
        response.headers["X-RateLimit-Policy"] = kind
        return response


def secure_base64(value: str, max_decoded_bytes: int) -> bytes:
    if len(value) > max_decoded_bytes * 2:
        raise ValueError("encoded payload too large")
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as error:
        raise ValueError("invalid base64 payload") from error
    if len(decoded) > max_decoded_bytes:
        raise ValueError("decoded payload too large")
    return decoded


def log_unhandled_error(request: Request, error: Exception) -> None:
    logger.exception("Unhandled request error method=%s path=%s", request.method, request.url.path, exc_info=error)

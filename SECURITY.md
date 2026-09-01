# Security review

Review date: 2026-08-16

## Checks performed

- Secret scan over source, configuration, firmware, frontend, CI, and documentation found no live API keys, private keys, passwords, or tokens. Database credentials, weather keys, Google keys, sensor credentials, and CORS origins are environment/build inputs.
- Dependency audit: `python -m pip_audit -r backend/requirements.txt -r frontend/requirements.txt` returned **No known vulnerabilities found**.
- Upload validation is content-based, bounded, memory-only, rejects active PDF JavaScript, ignores filenames, and never writes uploaded bytes to the web root.
- Unexpected backend exceptions are logged server-side and return only `internal_error` to clients.
- Authentication uses Argon2id, email verification gating, one-time SHA-256 token digests with expiry, revoked-on-use password resets, absolute/idle session expiry, and HttpOnly/SameSite cookies. Session tokens are never returned in JSON or exposed to frontend JavaScript.

## Operational requirements

- Set `DB_PASSWORD` and `SENSOR_TOKEN` before starting Docker Compose.
- Set `CORS_ALLOWED_ORIGINS` to the exact deployed frontend origins.
- Set `TRUST_PROXY_HEADERS=true` only when the service is behind a trusted proxy that overwrites forwarding headers.
- Use a shared limiter store such as Redis when running multiple backend replicas; the included limiter is process-local.
- Keep `.env` files, generated databases, model artifacts, and firmware build flags outside source control.
- Configure SMTP delivery in production; do not enable a local logging email backend that could expose verification or reset tokens.

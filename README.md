# Agri-Mitra

Agri-Mitra is a free smart-agriculture platform built only around the original datasets in `archive/` and the FAO documents in `rag_docs/`.

## Run locally

```powershell
python -m uvicorn backend.main:app --reload
```

- API: `http://localhost:8000/docs`
- Landing page: open `landing/index.html` or run `python -m http.server 8080 -d landing`
- Dashboard: `streamlit run frontend/app.py`

The backend defaults to a local `agrimitra.db` SQLite file. Set `DATABASE_URL` to the PostgreSQL URL used by Docker for deployment.

## Train models

Training scripts read only the supplied files. For example:

```powershell
python ml/train_crop_recommender.py --input archive/Crop Recommendation Dataset.xlsx
python ml/train_yield_regressor.py --input archive/crop_yield.csv
python ml/train_soil_classifier.py --data archive/CyAUG-Dataset
```

The crop recommender uses temperature, humidity, pH, and rainfall because the supplied crop recommendation workbook has no N/P/K columns. Live N/P/K is accepted only through telemetry.

## Security controls

- Rate limiting is configured through `RATE_LIMIT_*` environment variables. Authentication paths use both client-IP and the optional `X-Account-Identifier` account key with exponential backoff; authenticated requests use the user budget and unauthenticated requests use the public budget.
- Request bodies reject unknown fields and enforce bounded lengths, ranges, formats, and enumerated values.
- `POST /api/v1/ocr/pahani/upload` accepts bounded raw PDF/image bytes, validates file signatures and image structure, rejects active PDF JavaScript, never uses a client filename, and never stores the upload.
- Secrets are environment-only. Compose requires `DB_PASSWORD`; firmware credentials must be private build flags. Do not commit `.env` or generated databases.
- API errors return generic messages while full unexpected exceptions are logged server-side.
- Authentication uses Argon2id password hashes, email verification before login, one-time hashed verification/reset tokens, and absolute plus idle-expiring opaque sessions in an HttpOnly cookie. Auth secrets are never returned in JSON or placed in frontend code.
- Configure SMTP and `AUTH_PUBLIC_BASE_URL` for verification/reset delivery; Docker refuses to start without those values. Set `COOKIE_SECURE=false` only for local HTTP development.

## Core safety rules

- Invalid physical sensor values are quarantined into `flagged_readings`.
- Moisture below 20% is quarantined and skips calibration.
- Sensor retries are idempotent on `(field_id, timestamp)`.
- OCR extraction is always staged for human review.
- Crop rotation filtering runs before recommendation ranking.

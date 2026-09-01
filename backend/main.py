from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hmac
import os

from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Path as PathParam, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field as PydanticField, StrictBool, StrictFloat, StringConstraints
from pydantic import field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .alert_service import acknowledge_alert, escalate_due_alerts, evaluate_reading
from .auth_service import DUMMY_PASSWORD_HASH, clear_session_cookie, create_session, create_user, get_current_user, issue_email_verification, issue_password_reset, normalize_email, set_session_cookie, send_security_email, token_hash, verify_password, hash_password
from .database import get_db, init_db
from .ingestion_service import ingest_reading
from .language_service import answer_query
from .models import ActionLog, Alert, AuthSession, AuthUser, EnvironmentalEvent, Field, FarmProfile, FlaggedReading, SensorReading, now_utc
from .ocr_service import extract_pahani_text
from .preferences_service import upsert_preferences
from .report_service import pdf_bytes, report_payload
from .security import RateLimitMiddleware, log_unhandled_error, secure_base64, upload_limit_bytes, validate_upload_content
from .sse_service import publish, stream_response
from .vision_service import classify_placeholder
from .weather_service import fetch_forecast, irrigation_advice


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Agri-Mitra API", version="1.0.0", lifespan=lifespan)
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:8080").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Account-Identifier", "X-Sensor-Token", "X-User-Token"])
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, __: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "invalid_request", "message": "Input does not match the required schema."})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, error: Exception):
    log_unhandled_error(request, error)
    return JSONResponse(status_code=500, content={"error": "internal_error", "message": "An internal error occurred."})


class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: datetime | None = None
    field_id: str | None = PydanticField(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    soil_moisture: StrictFloat | None = PydanticField(default=None, ge=0, le=100)
    ph: StrictFloat | None = PydanticField(default=None, ge=0, le=14)
    raw_n: StrictFloat | None = PydanticField(default=None, ge=0, le=2000)
    raw_p: StrictFloat | None = PydanticField(default=None, ge=0, le=2000)
    raw_k: StrictFloat | None = PydanticField(default=None, ge=0, le=2000)
    temperature: StrictFloat | None = PydanticField(default=None, ge=-40, le=85)
    humidity: StrictFloat | None = PydanticField(default=None, ge=0, le=100)
    is_backlogged: StrictBool = False


class QueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_text: str = PydanticField(min_length=1, max_length=2000, pattern=r".*\S.*")
    language: Literal["en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "pa", "ml", "or"] = "en"
    context: list[Annotated[str, StringConstraints(min_length=1, max_length=500)]] = PydanticField(default_factory=list, max_length=10)


class CoordinatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: StrictFloat = PydanticField(ge=-90, le=90)
    lng: StrictFloat = PydanticField(ge=-180, le=180)


class FieldPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    farm_id: str | None = PydanticField(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = PydanticField(min_length=1, max_length=100)
    crop_type: str = PydanticField(default="Rice", min_length=1, max_length=50)
    growth_stage: str = PydanticField(default="Vegetative", min_length=1, max_length=50)
    gps_coordinates: CoordinatesPayload | None = None


class ActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: Literal["irrigation", "fertilizer", "pesticide", "manual_note"]
    details: str | None = PydanticField(default=None, max_length=2000)
    fertilizer_kg_per_ha: StrictFloat | None = PydanticField(default=None, ge=0, le=10000)
    timestamp: datetime | None = None


class PahaniPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = PydanticField(min_length=1, max_length=100000)


class VisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_base64: str = PydanticField(min_length=1, max_length=14000000)


class PreferencesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    farm_id: str | None = PydanticField(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    preferred_language: Literal["en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "pa", "ml", "or"] = "en"
    preferred_area_unit: Literal["hectare", "acre", "guntha", "bigha", "cent"] = "hectare"
    voice_playback_enabled: StrictBool = True


class SignupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = PydanticField(min_length=5, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = PydanticField(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value) or not any(char.islower() for char in value) or not any(char.isdigit() for char in value) or not any(not char.isalnum() for char in value):
            raise ValueError("password does not meet complexity requirements")
        return value


class LoginPayload(SignupPayload):
    pass


class PasswordResetRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = PydanticField(min_length=5, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PasswordResetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = PydanticField(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = PydanticField(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value) or not any(char.islower() for char in value) or not any(char.isdigit() for char in value) or not any(not char.isalnum() for char in value):
            raise ValueError("password does not meet complexity requirements")
        return value


def authenticated_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    return get_current_user(request, db)


def accessible_field(db: Session, user: AuthUser, field_id: str) -> Field:
    field = db.get(Field, field_id)
    if field is None or user.farm_id is None or field.farm_id != user.farm_id:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


def _serialize_reading(reading: SensorReading) -> dict:
    return {"id": reading.id, "field_id": reading.field_id, "timestamp": reading.timestamp.isoformat(), "soil_moisture": reading.soil_moisture, "ph": reading.ph, "n": reading.calibrated_n, "p": reading.calibrated_p, "k": reading.calibrated_k, "temperature": reading.temperature, "humidity": reading.humidity, "is_backlogged": reading.is_backlogged}


@app.get("/health")
def health():
    return {"status": "ok", "service": "agrimitra-backend"}


@app.get("/api/v1/health")
def api_health():
    return health()


@app.post("/api/v1/auth/signup")
def signup(payload: SignupPayload, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.scalar(select(AuthUser).where(AuthUser.email == email))
    if user is None:
        user, raw_token = create_user(db, email, payload.password)
        send_security_email(user.email, "Verify your Agri-Mitra email", "/api/v1/auth/verify-email", raw_token)
    elif not user.is_email_verified and not user.is_disabled:
        raw_token = issue_email_verification(user)
        send_security_email(user.email, "Verify your Agri-Mitra email", "/api/v1/auth/verify-email", raw_token)
    db.commit()
    return {"status": "verification_required", "message": "If the address can be registered, a verification email will be sent."}


@app.get("/api/v1/auth/verify-email")
def verify_email(token: str = Query(..., min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db)):
    user = db.scalar(select(AuthUser).where(AuthUser.email_verification_token_hash == token_hash(token)))
    expires_at = user.email_verification_expires_at if user else None
    if user is None or expires_at is None or (expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at) <= now_utc():
        raise HTTPException(status_code=400, detail="Verification token is invalid or expired")
    user.is_email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.commit()
    return {"status": "email_verified"}


@app.post("/api/v1/auth/login")
def login(payload: LoginPayload, request: Request, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.scalar(select(AuthUser).where(AuthUser.email == email))
    password_valid = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, payload.password)
    if user is None or not password_valid or user.is_disabled or not user.is_email_verified:
        raise HTTPException(status_code=401, detail="Invalid credentials or unverified email")
    raw_session = create_session(db, user, request)
    user.last_login_at = now_utc()
    db.commit()
    response = JSONResponse({"status": "authenticated"})
    set_session_cookie(response, raw_session)
    return response


@app.post("/api/v1/auth/password-reset/request")
def request_password_reset(payload: PasswordResetRequestPayload, db: Session = Depends(get_db)):
    user = db.scalar(select(AuthUser).where(AuthUser.email == normalize_email(payload.email), AuthUser.is_disabled.is_(False)))
    if user:
        raw_token = issue_password_reset(user)
        send_security_email(user.email, "Reset your Agri-Mitra password", "/api/v1/auth/password-reset/confirm", raw_token)
        db.commit()
    return {"status": "accepted", "message": "If the address is registered, a password reset email will be sent."}


@app.post("/api/v1/auth/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetPayload, db: Session = Depends(get_db)):
    user = db.scalar(select(AuthUser).where(AuthUser.password_reset_token_hash == token_hash(payload.token)))
    expires_at = user.password_reset_expires_at if user else None
    if user is None or expires_at is None or (expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at) <= now_utc():
        raise HTTPException(status_code=400, detail="Password reset token is invalid or expired")
    user.password_hash = hash_password(payload.password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.session_version += 1
    for active_session in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))).all():
        active_session.revoked_at = now_utc()
    db.commit()
    return {"status": "password_reset"}


@app.post("/api/v1/auth/logout")
def logout(request: Request, db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    raw_session = request.cookies.get("agrimitra_session")
    if raw_session:
        active_session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash == token_hash(raw_session), AuthSession.revoked_at.is_(None)))
        if active_session:
            active_session.revoked_at = now_utc()
    db.commit()
    response = JSONResponse({"status": "logged_out"})
    clear_session_cookie(response)
    return response


@app.get("/api/v1/auth/me")
def current_user_profile(user: AuthUser = Depends(authenticated_user)):
    return {"id": user.id, "email": user.email, "email_verified": user.is_email_verified, "farm_id": user.farm_id}


@app.post("/api/v1/telemetry/ingest")
async def telemetry_ingest(payload: TelemetryPayload, db: Session = Depends(get_db), field_id: str = Query("field_demo", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), x_sensor_token: str | None = Header(default=None, max_length=512)):
    expected_sensor_token = os.getenv("SENSOR_TOKEN")
    if expected_sensor_token and not hmac.compare_digest(x_sensor_token or "", expected_sensor_token):
        raise HTTPException(status_code=401, detail="Invalid sensor credentials")
    field_id = payload.field_id or field_id
    result = ingest_reading(db, field_id, payload.model_dump(mode="json", exclude_none=True))
    if result["status"] == "accepted":
        reading = db.get(SensorReading, result["reading_id"])
        alerts = evaluate_reading(db, reading)
        result["alerts"] = [alert.alert_type for alert in alerts]
        await publish({"type": "telemetry", "reading": _serialize_reading(reading), "alerts": result["alerts"]})
    db.commit()
    return result


@app.get("/api/v1/fields")
def fields(db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    if user.farm_id is None:
        return []
    return [{"id": item.id, "farm_id": item.farm_id, "name": item.name, "crop_type": item.crop_type, "growth_stage": item.growth_stage, "gps_coordinates": item.gps_coordinates} for item in db.scalars(select(Field).where(Field.farm_id == user.farm_id)).all()]


@app.post("/api/v1/fields")
def create_field(payload: FieldPayload, db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    farm = db.get(FarmProfile, user.farm_id) if user.farm_id else None
    if farm is None:
        raise HTTPException(403, "Farm access is not configured")
    if payload.farm_id and payload.farm_id != user.farm_id:
        raise HTTPException(403, "Farm access is not configured")
    field = Field(farm_id=farm.id, name=payload.name, crop_type=payload.crop_type, growth_stage=payload.growth_stage, gps_coordinates=payload.gps_coordinates.model_dump() if payload.gps_coordinates else None)
    db.add(field)
    db.commit()
    return {"id": field.id, "name": field.name}


@app.get("/api/v1/fields/{field_id}/readings")
def readings(field_id: str = PathParam(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    accessible_field(db, user, field_id)
    rows = db.scalars(select(SensorReading).where(SensorReading.field_id == field_id).order_by(SensorReading.timestamp.desc()).limit(limit)).all()
    return [_serialize_reading(row) for row in rows]


@app.get("/api/v1/alerts/active")
def active_alerts(db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    rows = db.scalars(select(Alert).join(Field, Field.id == Alert.field_id).where(Alert.status == "active", Field.farm_id == user.farm_id).order_by(Alert.created_at.desc())).all() if user.farm_id else []
    return [{"id": row.id, "field_id": row.field_id, "alert_type": row.alert_type, "status": row.status, "escalation_level": row.escalation_level, "created_at": row.created_at.isoformat(), "notes": row.compliance_notes} for row in rows]


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
def alert_acknowledge(alert_id: str = PathParam(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    alert = acknowledge_alert(db, alert_id)
    alert_field = db.get(Field, alert.field_id) if alert else None
    if alert is None or alert_field is None or user.farm_id is None or alert_field.farm_id != user.farm_id:
        raise HTTPException(404, "alert not found")
    db.commit()
    return {"status": alert.status, "id": alert.id}


@app.post("/api/v1/alerts/escalate")
def escalate_alerts(db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    changed = escalate_due_alerts(db, farm_id=user.farm_id)
    db.commit()
    return {"updated": [{"id": alert.id, "escalation_level": alert.escalation_level} for alert in changed]}


@app.post("/api/v1/simulate/stress-event")
async def stress_event(db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    created = []
    for field in db.scalars(select(Field).where(Field.farm_id == user.farm_id)).all() if user.farm_id else []:
        alert = Alert(field_id=field.id, alert_type="stress_event", escalation_level=0, compliance_notes="Simulated low-moisture stress event")
        db.add(alert)
        db.add(EnvironmentalEvent(farm_id=field.farm_id, source_field_id=field.id, event_type="moisture_drop", raw_value="15", timestamp=now_utc()))
        created.append({"field_id": field.id, "alert_type": alert.alert_type})
    db.commit()
    await publish({"type": "stress_event", "alerts": created})
    return {"status": "stress_injected", "alerts": created}


@app.get("/api/v1/stream/telemetry")
async def telemetry_stream(user: AuthUser = Depends(authenticated_user)):
    return stream_response()


@app.get("/api/v1/weather/forecast")
async def weather_forecast(field_id: str = Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    field = accessible_field(db, user, field_id)
    rows = await fetch_forecast(db, field)
    db.commit()
    return {"field_id": field_id, "advice": irrigation_advice(rows), "forecast": [{"forecast_time": row.forecast_time.isoformat(), "temperature_c": row.temperature_c, "humidity_pct": row.humidity_pct, "rain_probability": row.rain_probability, "description": row.description} for row in rows]}


@app.post("/api/v1/copilot/query")
def copilot_query(payload: QueryPayload, user: AuthUser = Depends(authenticated_user)):
    return answer_query(payload.query_text, payload.language, payload.context)


@app.post("/api/v1/ocr/pahani")
def pahani_ocr(payload: PahaniPayload, user: AuthUser = Depends(authenticated_user)):
    return {"status": "staged_for_review", "extracted": extract_pahani_text(payload.text), "auto_committed": False}


@app.post("/api/v1/ocr/pahani/upload")
async def pahani_upload(request: Request, user: AuthUser = Depends(authenticated_user)):
    maximum = upload_limit_bytes()
    declared_length = request.headers.get("content-length")
    if declared_length and declared_length.isdigit() and int(declared_length) > maximum:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > maximum:
            raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
        chunks.append(chunk)
    content = b"".join(chunks)
    try:
        detected_type = validate_upload_content(content, request.headers.get("content-type"))
    except ValueError:
        raise HTTPException(status_code=422, detail="Unsupported or unsafe upload")
    return {"status": "staged_for_review", "auto_committed": False, "content_type": detected_type, "size_bytes": len(content), "filename_used": False, "stored": False}


@app.post("/api/v1/vision/classify-soil")
def classify_soil(payload: VisionPayload, user: AuthUser = Depends(authenticated_user)):
    try:
        image = secure_base64(payload.image_base64, upload_limit_bytes())
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid image payload")
    return classify_placeholder(image, ["Alluvial", "Arid", "Black", "Laterite", "Mountain", "Red", "Yellow"])


@app.post("/api/v1/vision/classify-disease")
def classify_disease(payload: VisionPayload, user: AuthUser = Depends(authenticated_user)):
    try:
        image = secure_base64(payload.image_base64, upload_limit_bytes())
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid image payload")
    return classify_placeholder(image, ["healthy", "disease_unknown"])


@app.get("/api/v1/reports/cycle/{field_id}")
def cycle_report(field_id: str = PathParam(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    accessible_field(db, user, field_id)
    return report_payload(db, field_id)


@app.get("/api/v1/reports/certificate/{field_id}")
def certificate(field_id: str = PathParam(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    accessible_field(db, user, field_id)
    return Response(content=pdf_bytes(report_payload(db, field_id)), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=field-{field_id}-certificate.pdf"})


@app.get("/api/v1/reports/export/{field_id}")
def export_report(field_id: str = PathParam(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    accessible_field(db, user, field_id)
    return JSONResponse(report_payload(db, field_id), headers={"Content-Disposition": f"attachment; filename=field-{field_id}-export.json"})


@app.get("/api/v1/anomalies")
def anomalies(db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    rows = db.scalars(select(FlaggedReading).join(Field, Field.id == FlaggedReading.field_id).where(Field.farm_id == user.farm_id).order_by(FlaggedReading.received_at.desc())).all() if user.farm_id else []
    return [{"id": row.id, "field_id": row.field_id, "timestamp": row.timestamp.isoformat(), "reason": row.reason, "actual_value": row.actual_value, "is_disputed": row.is_disputed} for row in rows]


@app.post("/api/v1/fields/{field_id}/actions")
def log_action(payload: ActionPayload, field_id: str = PathParam(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    accessible_field(db, user, field_id)
    timestamp = payload.timestamp or now_utc()
    action = ActionLog(field_id=field_id, action_type=payload.action_type, details=payload.details, fertilizer_kg_per_ha=payload.fertilizer_kg_per_ha, timestamp=timestamp)
    db.add(action)
    db.commit()
    return {"id": action.id, "status": "logged"}


@app.post("/api/v1/preferences")
def preferences(payload: PreferencesPayload, db: Session = Depends(get_db), user: AuthUser = Depends(authenticated_user)):
    if payload.farm_id and payload.farm_id != user.farm_id:
        raise HTTPException(403, "Farm access is not configured")
    payload = payload.model_copy(update={"farm_id": user.farm_id})
    item = upsert_preferences(db, payload.model_dump(exclude_none=True))
    db.commit()
    return {"id": item.id, "preferred_language": item.preferred_language, "preferred_area_unit": item.preferred_area_unit, "voice_playback_enabled": item.voice_playback_enabled}


@app.get("/api/v1/entity-normalization/lookup")
def normalization_lookup(term: str = Query(..., min_length=1, max_length=200), language: Literal["en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "pa", "ml", "or"] | None = None):
    from .entity_normalization import lookup
    return lookup(term, language)

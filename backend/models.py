from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class FarmProfile(Base):
    __tablename__ = "farm_profile"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    secondary_contact_phone: Mapped[str | None] = mapped_column(String(20))
    survey_number: Mapped[str | None] = mapped_column(String(100))
    village: Mapped[str | None] = mapped_column(String(100))
    taluk: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    total_area: Mapped[float | None] = mapped_column(Float)
    cultivable_area: Mapped[float | None] = mapped_column(Float)
    irrigation_classification: Mapped[str] = mapped_column(String(50), default="Rainfed")
    detected_soil_type: Mapped[str] = mapped_column(String(50), default="Unknown")
    soil_calibration_m: Mapped[float] = mapped_column(Float, default=1.0)
    soil_calibration_c: Mapped[float] = mapped_column(Float, default=0.0)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending_review")
    verification_method: Mapped[str | None] = mapped_column(String(20))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Field(Base):
    __tablename__ = "fields"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farm_profile.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    crop_type: Mapped[str] = mapped_column(String(50), nullable=False)
    growth_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    dimensions_length: Mapped[float | None] = mapped_column(Float)
    dimensions_width: Mapped[float | None] = mapped_column(Float)
    gps_coordinates: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ThresholdProfile(Base):
    __tablename__ = "threshold_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crop_type: Mapped[str] = mapped_column(String(50), nullable=False)
    growth_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    moisture_min: Mapped[float | None] = mapped_column(Float)
    moisture_max: Mapped[float | None] = mapped_column(Float)
    ph_min: Mapped[float | None] = mapped_column(Float)
    ph_max: Mapped[float | None] = mapped_column(Float)
    n_min: Mapped[float | None] = mapped_column(Float)
    p_min: Mapped[float | None] = mapped_column(Float)
    k_min: Mapped[float | None] = mapped_column(Float)
    temp_min: Mapped[float | None] = mapped_column(Float)
    temp_max: Mapped[float | None] = mapped_column(Float)
    humidity_min: Mapped[float | None] = mapped_column(Float)
    humidity_max: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("crop_type", "growth_stage"),)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    soil_moisture: Mapped[float] = mapped_column(Float, nullable=False)
    ph: Mapped[float] = mapped_column(Float, nullable=False)
    raw_n: Mapped[float | None] = mapped_column(Float)
    raw_p: Mapped[float | None] = mapped_column(Float)
    raw_k: Mapped[float | None] = mapped_column(Float)
    calibrated_n: Mapped[float | None] = mapped_column(Float)
    calibrated_p: Mapped[float | None] = mapped_column(Float)
    calibrated_k: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    node_battery_voltage: Mapped[float | None] = mapped_column(Float)
    is_backlogged: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("field_id", "timestamp"),)


class FlaggedReading(Base):
    __tablename__ = "flagged_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    threshold_value: Mapped[float | None] = mapped_column(Float)
    actual_value: Mapped[float | None] = mapped_column(Float)
    is_disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    dispute_notes: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ActionLog(Base):
    __tablename__ = "action_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    fertilizer_kg_per_ha: Mapped[float | None] = mapped_column(Float)
    is_disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    reading_id: Mapped[int | None] = mapped_column(ForeignKey("sensor_readings.id"))
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compliance_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EnvironmentalEvent(Base):
    __tablename__ = "environmental_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey("farm_profile.id", ondelete="CASCADE"), nullable=False)
    source_field_id: Mapped[str | None] = mapped_column(ForeignKey("fields.id"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class CropCycleHistory(Base):
    __tablename__ = "crop_cycle_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    crop_grown: Mapped[str] = mapped_column(String(50), nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(Date)
    n_applied_kg_ha: Mapped[float | None] = mapped_column(Float)
    p_applied_kg_ha: Mapped[float | None] = mapped_column(Float)
    k_applied_kg_ha: Mapped[float | None] = mapped_column(Float)
    yield_achieved_kg_ha: Mapped[float | None] = mapped_column(Float)
    expert_label: Mapped[str | None] = mapped_column(String(50))
    within_compliance: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)
    rainfall_mm: Mapped[float | None] = mapped_column(Float)
    rain_probability: Mapped[float | None] = mapped_column(Float)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("field_id", "forecast_time"),)


class VerificationAuditLog(Base):
    __tablename__ = "verification_audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farm_profile.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    field_changed: Mapped[str | None] = mapped_column(String(100))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    farm_id: Mapped[str | None] = mapped_column(ForeignKey("farm_profile.id"))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    preferred_area_unit: Mapped[str] = mapped_column(String(20), default="hectare")
    voice_playback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuthUser(Base):
    __tablename__ = "auth_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    farm_id: Mapped[str | None] = mapped_column(ForeignKey("farm_profile.id"))
    email_verification_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))


def seed_defaults(session) -> None:
    if not session.query(FarmProfile).first():
        farm = FarmProfile(owner_name="Demo Farmer", phone_number="+910000000000", village="Demo Village", district="Demo District", cultivable_area=2.0)
        session.add(farm)
        session.flush()
        session.add(Field(id="field_demo", farm_id=farm.id, name="North Plot", crop_type="Rice", growth_stage="Vegetative", gps_coordinates={"lat": 15.3173, "lng": 75.7139}))
    if not session.query(ThresholdProfile).first():
        session.add(ThresholdProfile(crop_type="Rice", growth_stage="Vegetative", moisture_min=20, moisture_max=85, ph_min=5.5, ph_max=7.5, n_min=40, p_min=20, k_min=30, temp_min=10, temp_max=38, humidity_min=30, humidity_max=95))

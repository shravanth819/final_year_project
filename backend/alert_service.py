from datetime import datetime, timezone

from datetime import timedelta

from sqlalchemy import select

from .models import Alert, Field, SensorReading, ThresholdProfile


def evaluate_reading(session, reading: SensorReading) -> list[Alert]:
    field = session.get(Field, reading.field_id)
    profile = session.scalar(select(ThresholdProfile).where(ThresholdProfile.crop_type == field.crop_type, ThresholdProfile.growth_stage == field.growth_stage))
    if profile is None:
        return []
    checks = [("low_moisture", reading.soil_moisture, profile.moisture_min, "below"), ("high_moisture", reading.soil_moisture, profile.moisture_max, "above"), ("ph_low", reading.ph, profile.ph_min, "below"), ("ph_high", reading.ph, profile.ph_max, "above"), ("nitrogen_low", reading.calibrated_n, profile.n_min, "below"), ("phosphorus_low", reading.calibrated_p, profile.p_min, "below"), ("potassium_low", reading.calibrated_k, profile.k_min, "below"), ("temperature_low", reading.temperature, profile.temp_min, "below"), ("temperature_high", reading.temperature, profile.temp_max, "above")]
    alerts = []
    for alert_type, actual, threshold, direction in checks:
        breach = actual is not None and threshold is not None and ((direction == "below" and actual < threshold) or (direction == "above" and actual > threshold))
        if breach:
            alert = Alert(field_id=reading.field_id, reading_id=reading.id, alert_type=alert_type, compliance_notes=f"Value {actual:.2f} is {direction} threshold {threshold:.2f}")
            session.add(alert)
            alerts.append(alert)
    session.flush()
    return alerts


def acknowledge_alert(session, alert_id: str) -> Alert | None:
    alert = session.get(Alert, alert_id)
    if alert:
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.now(timezone.utc)
    return alert


def escalate_due_alerts(session, now=None, farm_id: str | None = None) -> list[Alert]:
    now = now or datetime.now(timezone.utc)
    query = select(Alert).join(Field, Field.id == Alert.field_id).where(Alert.status == "active")
    if farm_id:
        query = query.where(Field.farm_id == farm_id)
    else:
        return []
    alerts = session.scalars(query).all()
    changed = []
    for alert in alerts:
        created_at = alert.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age = now - created_at
        level = 2 if age >= timedelta(hours=2) else 1 if age >= timedelta(minutes=30) else 0
        if level > alert.escalation_level:
            alert.escalation_level = level
            alert.escalated_at = now
            changed.append(alert)
    session.flush()
    return changed

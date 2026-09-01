from datetime import datetime, timezone

from sqlalchemy import select

from .models import Field, FlaggedReading, SensorReading, now_utc

BOUNDS = {
    "ph": (0, 14),
    "soil_moisture": (0, 100),
    "temperature": (-40, 85),
    "raw_n": (0, 2000),
    "raw_p": (0, 2000),
    "raw_k": (0, 2000),
    "humidity": (0, 100),
}


def _number(payload, *names, default=None):
    for name in names:
        if payload.get(name) is not None:
            return float(payload[name])
    return default


def parse_timestamp(value) -> datetime:
    if value is None:
        return now_utc()
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def calibrate(value: float | None, temperature: float | None, multiplier=1.0, offset=0.0):
    if value is None:
        return None
    compensation = 1 + 0.0191 * ((temperature if temperature is not None else 25) - 25)
    return multiplier * (value / compensation) + offset


def ingest_reading(session, field_id: str, payload: dict) -> dict:
    field = session.get(Field, field_id)
    if field is None:
        return {"status": "rejected", "reason": "unknown_field"}
    timestamp = parse_timestamp(payload.get("timestamp"))
    existing = session.scalar(select(SensorReading).where(SensorReading.field_id == field_id, SensorReading.timestamp == timestamp))
    if existing:
        return {"status": "duplicate_ignored", "reading_id": existing.id}

    values = {
        "soil_moisture": _number(payload, "soil_moisture", "moisture", default=0),
        "ph": _number(payload, "ph", default=7),
        "temperature": _number(payload, "temperature", "temperature_c"),
        "humidity": _number(payload, "humidity", "humidity_pct"),
        "raw_n": _number(payload, "raw_n", "n", "nitrogen"),
        "raw_p": _number(payload, "raw_p", "p", "phosphorus"),
        "raw_k": _number(payload, "raw_k", "k", "potassium"),
    }
    for key, (minimum, maximum) in BOUNDS.items():
        value = values.get(key)
        if value is not None and not minimum <= value <= maximum:
            session.add(FlaggedReading(field_id=field_id, timestamp=timestamp, raw_payload=payload, reason=f"{key}_out_of_bounds", actual_value=value))
            return {"status": "quarantined", "reason": f"{key}_out_of_bounds", "actual_value": value}

    if values["soil_moisture"] < 20:
        session.add(FlaggedReading(field_id=field_id, timestamp=timestamp, raw_payload=payload, reason="moisture_below_quarantine", actual_value=values["soil_moisture"], threshold_value=20))
        return {"status": "quarantined", "reason": "moisture_below_quarantine", "actual_value": values["soil_moisture"]}

    reading = SensorReading(field_id=field_id, timestamp=timestamp, soil_moisture=values["soil_moisture"], ph=values["ph"], temperature=values["temperature"], humidity=values["humidity"], raw_n=values["raw_n"], raw_p=values["raw_p"], raw_k=values["raw_k"], is_backlogged=bool(payload.get("is_backlogged", False)))
    reading.calibrated_n = calibrate(reading.raw_n, reading.temperature)
    reading.calibrated_p = calibrate(reading.raw_p, reading.temperature)
    reading.calibrated_k = calibrate(reading.raw_k, reading.temperature)
    session.add(reading)
    session.flush()
    return {"status": "accepted", "reading_id": reading.id, "field_id": field_id, "timestamp": timestamp.isoformat(), "calibrated": {"n": reading.calibrated_n, "p": reading.calibrated_p, "k": reading.calibrated_k}}

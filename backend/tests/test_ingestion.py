from datetime import datetime, timezone

from backend.database import SessionLocal, init_db
from backend.ingestion_service import ingest_reading
from backend.models import FlaggedReading


def setup_module():
    init_db()


def test_low_moisture_is_quarantined():
    with SessionLocal() as session:
        result = ingest_reading(session, "field_demo", {"timestamp": datetime.now(timezone.utc).isoformat(), "soil_moisture": 15, "ph": 6.5})
        assert result["status"] == "quarantined"
        assert session.query(FlaggedReading).filter_by(reason="moisture_below_quarantine").count() >= 1


def test_out_of_bounds_is_quarantined():
    with SessionLocal() as session:
        result = ingest_reading(session, "field_demo", {"timestamp": datetime.now(timezone.utc).isoformat(), "soil_moisture": 50, "ph": 99})
        assert result["status"] == "quarantined"
        assert result["reason"] == "ph_out_of_bounds"


def test_duplicate_is_ignored():
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {"timestamp": timestamp, "soil_moisture": 50, "ph": 6.5, "raw_n": 100, "raw_p": 40, "raw_k": 80}
    with SessionLocal() as session:
        first = ingest_reading(session, "field_demo", payload)
        session.commit()
        second = ingest_reading(session, "field_demo", payload)
        assert first["status"] == "accepted"
        assert second["status"] == "duplicate_ignored"

import io
import json

from sqlalchemy import select

from .models import Alert, Field, SensorReading


def report_payload(session, field_id: str) -> dict:
    field = session.get(Field, field_id)
    readings = session.scalars(select(SensorReading).where(SensorReading.field_id == field_id).order_by(SensorReading.timestamp.desc()).limit(100)).all()
    alerts = session.scalars(select(Alert).where(Alert.field_id == field_id).order_by(Alert.created_at.desc()).limit(100)).all()
    return {"field": {"id": field.id, "name": field.name, "crop_type": field.crop_type, "growth_stage": field.growth_stage} if field else None, "reading_count": len(readings), "alert_count": len(alerts), "latest_reading": {"timestamp": readings[0].timestamp.isoformat(), "moisture": readings[0].soil_moisture, "ph": readings[0].ph} if readings else None, "alerts": [{"type": alert.alert_type, "status": alert.status, "created_at": alert.created_at.isoformat()} for alert in alerts], "compliance_score": max(0, round(100 - len(alerts) * 5, 1))}


def pdf_bytes(payload: dict) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return json.dumps(payload, indent=2).encode("utf-8")
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer, pagesize=A4)
    document.setTitle("Agri-Mitra Field Health Report")
    document.drawString(48, 800, "Agri-Mitra Field Health Report")
    y = 775
    for key, value in payload.items():
        document.drawString(48, y, f"{key}: {value}")
        y -= 18
        if y < 50:
            document.showPage()
            y = 800
    document.save()
    return buffer.getvalue()

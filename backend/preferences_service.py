from datetime import datetime, timezone

from .models import UserPreferences


def upsert_preferences(session, payload: dict) -> UserPreferences:
    preference = UserPreferences(farm_id=payload.get("farm_id"), preferred_language=payload.get("preferred_language", "en"), preferred_area_unit=payload.get("preferred_area_unit", "hectare"), voice_playback_enabled=payload.get("voice_playback_enabled", True), updated_at=datetime.now(timezone.utc))
    session.add(preference)
    session.flush()
    return preference

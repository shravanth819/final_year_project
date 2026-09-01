from dataclasses import dataclass

ROTATION_FAMILIES = {"tomato": "solanaceae", "potato": "solanaceae", "pepper": "solanaceae", "rice": "cereal", "maize": "cereal", "wheat": "cereal", "chickpea": "legume", "kidneybeans": "legume", "lentil": "legume"}


@dataclass
class Recommendation:
    crop: str
    confidence: float
    filtered_reason: str | None = None


def crop_family(crop: str) -> str:
    return ROTATION_FAMILIES.get(crop.strip().lower(), crop.strip().lower())


def apply_rotation_filter(crops: list[str], previous_crop: str | None, seasons_since_previous: int = 99) -> tuple[list[str], list[Recommendation]]:
    if not previous_crop or seasons_since_previous >= 2:
        return crops, []
    previous_family = crop_family(previous_crop)
    accepted = []
    filtered = []
    for crop in crops:
        if crop_family(crop) == previous_family:
            filtered.append(Recommendation(crop=crop, confidence=0.0, filtered_reason=f"Suppressed: {previous_family} rotation needs a two-season gap"))
        else:
            accepted.append(crop)
    return accepted, filtered


def build_feature_vector(sensor: dict, history: dict | None = None, static: dict | None = None) -> dict:
    history = history or {}
    static = static or {}
    return {"X_sensor": [sensor.get("temperature", 0), sensor.get("humidity", 0), sensor.get("ph", 0), sensor.get("rainfall", 0)], "X_history": [history.get("prev_crop", ""), history.get("n_applied", 0), history.get("p_applied", 0), history.get("k_applied", 0), history.get("yield_kg_ha", 0), history.get("seasons_count", 0)], "X_static": [static.get("soil_type", "Unknown"), static.get("cultivable_area", 0), static.get("irrigation_classification", "Rainfed"), static.get("district", "")], "cold_start": not bool(history)}

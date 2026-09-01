import re

AREA_FACTORS = {"guntha": 0.010117, "bigha": 0.25, "cent": 0.004047, "hectare": 1.0, "ha": 1.0}


def extract_pahani_text(text: str) -> dict:
    def find(pattern):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    area_value = find(r"(?:area|extent|ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)")
    area_unit = find(r"(?:area|extent|ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ)\s*[:\-]?\s*[0-9]+(?:\.[0-9]+)?\s*(guntha|bigha|cent|hectare|ha)") or "hectare"
    return {"survey_number": find(r"(?:survey|sy)\s*(?:number|no)?\s*[:\-]?\s*([A-Za-z0-9\-/]+)"), "owner_name": find(r"(?:owner|name)\s*[:\-]?\s*([A-Za-z .]+)"), "district": find(r"district\s*[:\-]?\s*([A-Za-z .]+)"), "taluk": find(r"taluk\s*[:\-]?\s*([A-Za-z .]+)"), "total_area": float(area_value) * AREA_FACTORS[area_unit.lower()] if area_value else None, "area_unit": area_unit.lower(), "verification_status": "pending_review", "verification_method": "ocr_upload"}

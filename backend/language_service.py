from .entity_normalization import lookup

FALLBACKS = {"en": "Data Not Available", "hi": "डेटा उपलब्ध नहीं है", "kn": "ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ", "ta": "தரவு கிடைக்கவில்லை", "te": "డేటా అందుబాటులో లేదు"}


def answer_query(query_text: str, language: str = "en", context: list[str] | None = None) -> dict:
    normalized = lookup(query_text)
    if not context:
        return {"answer_text": FALLBACKS.get(language, FALLBACKS["en"]), "citations": [], "confidence": 0.0, "normalized_term": normalized}
    return {"answer_text": f"Based on the available field context, review {normalized['canonical']} and follow the latest threshold alert before acting.", "citations": [{"id": index + 1, "source": source} for index, source in enumerate(context[:3])], "confidence": 0.72, "normalized_term": normalized}

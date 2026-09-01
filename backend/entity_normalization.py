TERMS = {
    "kari mannu": {"canonical": "black soil", "language": "kn"},
    "red soil": {"canonical": "red loamy soil", "language": "en"},
    "urea": {"canonical": "nitrogen fertilizer", "language": "en"},
    "ನೀರು": {"canonical": "irrigation water", "language": "kn"},
}


def lookup(term: str, language: str | None = None) -> dict:
    result = TERMS.get(term.strip().lower(), {"canonical": term.strip(), "language": language or "en"})
    return result

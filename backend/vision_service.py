from io import BytesIO
import logging


logger = logging.getLogger("agrimitra.vision")


def image_quality_gate(image_bytes: bytes, minimum_width: int = 640, minimum_height: int = 480) -> dict:
    try:
        from PIL import Image, ImageStat
        image = Image.open(BytesIO(image_bytes))
        contrast = ImageStat.Stat(image.convert("L")).stddev[0]
        accepted = image.width >= minimum_width and image.height >= minimum_height and contrast >= 8
        return {"accepted": accepted, "width": image.width, "height": image.height, "contrast": round(contrast, 2), "reason": None if accepted else "Image must be at least 640x480 with visible contrast"}
    except Exception:
        logger.exception("Image quality validation failed")
        return {"accepted": False, "reason": "Invalid or unsupported image"}


def classify_placeholder(image_bytes: bytes, classes: list[str]) -> dict:
    quality = image_quality_gate(image_bytes)
    return {**quality, "class": classes[0] if quality.get("accepted") and classes else None, "confidence": 0.0}

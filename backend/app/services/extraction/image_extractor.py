"""Local image metadata and OCR extraction."""

from pathlib import Path

from PIL import Image

from app.services.extraction.common import ExtractedItem, ExtractionResult
from app.services.ocr.ocr_engine import OCRUnavailable, extract_local_ocr


def extract_image(path: Path, tesseract_cmd: str | None = None, engine: str = "tesseract") -> ExtractionResult:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        width, height = image.size
        image_format = image.format or path.suffix.lstrip(".").upper()
    items = [ExtractedItem("metadata", f"Image format: {image_format}; dimensions: {width}x{height}", "pillow-metadata")]
    try:
        result = extract_local_ocr(path.read_bytes(), tesseract_cmd=tesseract_cmd, engine=engine)
        if result.text.strip():
            items.append(ExtractedItem("ocr_text", result.text, "tesseract", extraction_confidence=result.confidence))
        else:
            return ExtractionResult(items, ["OCR completed but did not detect readable text."])
        return ExtractionResult(items, [])
    except OCRUnavailable as exc:
        return ExtractionResult(items, [str(exc)])

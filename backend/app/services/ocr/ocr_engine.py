"""Local OCR adapter. It never downloads models or silently substitutes text."""

from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output


class OCRUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float | None


def extract_local_ocr(image_bytes: bytes, tesseract_cmd: str | None = None, engine: str = "tesseract") -> OCRResult:
    if engine.lower() != "tesseract":
        raise OCRUnavailable(f"The configured local OCR engine '{engine}' is not installed/configured. No model was downloaded.")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    try:
        image_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image_array is None:
            raise ValueError("The image could not be decoded for OCR.")
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        processed = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 31, 11)
        pil_image = Image.fromarray(processed)
        data = pytesseract.image_to_data(pil_image, output_type=Output.DICT, config="--psm 6")
    except (pytesseract.TesseractNotFoundError, OSError) as exc:
        raise OCRUnavailable("Local Tesseract OCR is unavailable. Install Tesseract or configure TESSERACT_CMD.") from exc
    except pytesseract.TesseractError as exc:
        raise OCRUnavailable("Local Tesseract OCR could not process this image.") from exc

    words = []
    confidences = []
    for text, confidence in zip(data.get("text", []), data.get("conf", [])):
        word = str(text).strip()
        if word:
            words.append(word)
        try:
            score = float(confidence)
            if score >= 0:
                confidences.append(score)
        except (TypeError, ValueError):
            continue
    confidence = (sum(confidences) / len(confidences) / 100) if confidences else None
    return OCRResult(" ".join(words), confidence)

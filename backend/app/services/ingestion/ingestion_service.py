"""Dispatch local documents to format-specific extractors."""

from pathlib import Path

from app.services.extraction.common import ExtractedItem, ExtractionResult
from app.services.extraction.csv_extractor import extract_csv
from app.services.extraction.docx_extractor import extract_docx
from app.services.extraction.excel_extractor import extract_excel
from app.services.extraction.image_extractor import extract_image
from app.services.extraction.pdf_extractor import extract_pdf
from app.services.extraction.text_extractor import extract_text


def extract_document(path: Path, extension: str, tesseract_cmd: str | None = None, ocr_engine: str = "tesseract") -> ExtractionResult:
    if extension == ".pdf":
        return extract_pdf(path, tesseract_cmd, ocr_engine)
    if extension == ".docx":
        return ExtractionResult(extract_docx(path), [])
    if extension == ".txt":
        return ExtractionResult(extract_text(path), [])
    if extension == ".csv":
        return ExtractionResult(extract_csv(path), [])
    if extension == ".xlsx":
        return ExtractionResult(extract_excel(path), [])
    if extension in {".png", ".jpg", ".jpeg"}:
        return extract_image(path, tesseract_cmd, ocr_engine)
    raise ValueError("Unsupported document format.")

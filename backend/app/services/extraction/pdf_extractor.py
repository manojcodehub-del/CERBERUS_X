"""Page-level PDF text, metadata, best-effort tables, and local OCR fallback."""

from pathlib import Path

import pymupdf as fitz

from app.services.extraction.common import ExtractedItem, ExtractionResult
from app.services.extraction.table_extractor import table_cell
from app.services.ocr.ocr_engine import OCRUnavailable, extract_local_ocr


def extract_pdf(path: Path, tesseract_cmd: str | None = None, engine: str = "tesseract") -> ExtractionResult:
    items: list[ExtractedItem] = []
    warnings: list[str] = []
    with fitz.open(path) as document:
        for key, value in (document.metadata or {}).items():
            if value and key not in {"format", "encryption"}:
                items.append(ExtractedItem("metadata", f"{key}: {value}", "pymupdf-metadata"))
        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text") or ""
            if text.strip():
                items.append(ExtractedItem("page_text", text.strip(), "pymupdf", page_number=page_index))
                heading = _heading_candidate(page)
                if heading and heading.strip() != text.strip():
                    items.append(ExtractedItem("heading", heading.strip(), "pymupdf-layout", page_number=page_index))
            if len(text.strip()) < 40:
                try:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    ocr = extract_local_ocr(pixmap.tobytes("png"), tesseract_cmd=tesseract_cmd, engine=engine)
                    if ocr.text.strip():
                        items.append(ExtractedItem("ocr_text", ocr.text.strip(), "tesseract-pdf-page",
                                                   page_number=page_index, extraction_confidence=ocr.confidence))
                    else:
                        warnings.append(f"OCR found no readable text on PDF page {page_index}.")
                except OCRUnavailable as exc:
                    warnings.append(f"PDF page {page_index}: {exc}")
            items.extend(_extract_tables(page, page_index, warnings))
    return ExtractionResult(items, warnings)


def _heading_candidate(page) -> str | None:
    try:
        spans = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    value = span.get("text", "").strip()
                    if value and span.get("size", 0) >= 16:
                        spans.append(value)
        candidate = " ".join(spans).strip()
        return candidate[:1000] or None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _extract_tables(page, page_number: int, warnings: list[str]) -> list[ExtractedItem]:
    find_tables = getattr(page, "find_tables", None)
    if not callable(find_tables):
        return []
    result = []
    try:
        tables = find_tables().tables
        for table_index, table in enumerate(tables):
            rows = table.extract() or []
            for row_index, row in enumerate(rows, start=1):
                values = [str(cell).strip() if cell is not None else "" for cell in row]
                context = " | ".join(value for value in values if value)
                for column_index, value in enumerate(values, start=1):
                    if value:
                        item = table_cell(value, "pymupdf-table", row_index, f"Column {column_index}",
                                          f"R{row_index}C{column_index}", page_number=page_number,
                                          table_index=table_index, context_text=context)
                        if item:
                            result.append(item)
    except Exception:
        warnings.append(f"PDF table extraction was unavailable on page {page_number}; page text remains available.")
    return result

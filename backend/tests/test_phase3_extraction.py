from datetime import datetime

import pymupdf as fitz
import cv2
import numpy as np
import pytest
from docx import Document as DocxDocument
from openpyxl import Workbook
from PIL import Image

from app.services.extraction.csv_extractor import extract_csv
from app.services.extraction.docx_extractor import extract_docx
from app.services.extraction.excel_extractor import extract_excel
from app.services.extraction.image_extractor import extract_image
from app.services.extraction.pdf_extractor import extract_pdf
from app.services.extraction.text_extractor import extract_text
from app.services.ocr.ocr_engine import OCRUnavailable


def test_txt_preserves_paragraph_order_and_original_text(tmp_path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("First line\n\nSecond line\n", encoding="utf-8")
    items = extract_text(source)
    assert [item.extracted_text for item in items] == ["First line", "Second line"]
    assert [item.paragraph_index for item in items] == [0, 2]
    assert items[0].original_text == "First line"


def test_docx_extracts_paragraph_heading_table_and_metadata(tmp_path) -> None:
    source = tmp_path / "record.docx"
    document = DocxDocument()
    document.add_heading("Project Record", level=1)
    document.add_paragraph("Approved budget: ₹10,00,000")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Item", "Cost"
    table.cell(1, 0).text, table.cell(1, 1).text = "Review", "1200"
    document.core_properties.title = "Phase 3 fixture"
    document.save(source)

    items = extract_docx(source)
    assert any(item.content_type == "heading" and item.extracted_text == "Project Record" for item in items)
    cells = [item for item in items if item.content_type == "table_cell"]
    assert any(item.extracted_text == "1200" and item.table_index == 0 and item.row_number == 2 for item in cells)
    assert any(item.content_type == "metadata" and "Phase 3 fixture" in item.extracted_text for item in items)


def test_csv_preserves_header_row_number_and_cell_coordinate(tmp_path) -> None:
    source = tmp_path / "records.csv"
    source.write_text("Project,Budget\nCERBERUS-X,₹10,00,000\n".replace("₹10,00,000", '"₹10,00,000"'), encoding="utf-8")
    items = extract_csv(source)
    budget = next(item for item in items if item.extracted_text == "₹10,00,000")
    assert budget.row_number == 2
    assert budget.column_name == "Budget"
    assert budget.cell_coordinate == "B2"
    assert "Project: CERBERUS-X" in (budget.context_text or "")


def test_excel_extracts_multiple_sheets_dates_and_cell_provenance(tmp_path) -> None:
    source = tmp_path / "records.xlsx"
    workbook = Workbook()
    first = workbook.active
    first.title = "Budget"
    first.append(["Project", "Amount"])
    first.append(["CERBERUS-X", 1000000])
    second = workbook.create_sheet("Dates")
    second.append(["Milestone", "Due"])
    second.append(["Review", datetime(2026, 11, 25)])
    workbook.save(source)

    items = extract_excel(source)
    amount = next(item for item in items if item.extracted_text == "1000000")
    due_date = next(item for item in items if item.sheet_name == "Dates" and item.cell_coordinate == "B2")
    assert amount.sheet_name == "Budget" and amount.cell_coordinate == "B2" and amount.row_number == 2
    assert due_date.extracted_text.startswith("2026-11-25")


def test_pdf_extracts_page_text_and_metadata(tmp_path) -> None:
    source = tmp_path / "record.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Approved project status remains active for all review milestones.")
        document.set_metadata({"title": "PDF fixture"})
        document.save(source)
    result = extract_pdf(source)
    assert any(item.content_type == "page_text" and item.page_number == 1 for item in result.items)
    assert any(item.content_type == "metadata" and "PDF fixture" in item.extracted_text for item in result.items)


def test_scanned_pdf_reports_ocr_unavailable_without_fake_text(tmp_path, monkeypatch) -> None:
    from app.services.extraction import pdf_extractor

    image_path = tmp_path / "source.png"
    Image.new("RGB", (200, 80), "white").save(image_path)
    source = tmp_path / "scan.pdf"
    with fitz.open() as document:
        page = document.new_page(width=200, height=80)
        page.insert_image(page.rect, filename=str(image_path))
        document.save(source)

    def unavailable(*_args, **_kwargs):
        raise OCRUnavailable("Local Tesseract OCR is unavailable. Install Tesseract or configure TESSERACT_CMD.")

    monkeypatch.setattr(pdf_extractor, "extract_local_ocr", unavailable)
    result = extract_pdf(source)
    assert not any(item.extraction_method == "tesseract-pdf-page" for item in result.items)
    assert any("Tesseract OCR is unavailable" in warning for warning in result.warnings)


def test_image_reports_missing_ocr_engine_and_keeps_metadata(tmp_path, monkeypatch) -> None:
    from app.services.extraction import image_extractor

    source = tmp_path / "scan.png"
    Image.new("RGB", (80, 40), "white").save(source)

    def unavailable(*_args, **_kwargs):
        raise OCRUnavailable("Local Tesseract OCR is unavailable. Install Tesseract or configure TESSERACT_CMD.")

    monkeypatch.setattr(image_extractor, "extract_local_ocr", unavailable)
    result = extract_image(source)
    assert result.items[0].content_type == "metadata"
    assert result.items[0].extracted_text.endswith("80x40")
    assert result.warnings and "Tesseract OCR is unavailable" in result.warnings[0]
    assert not any(item.content_type == "ocr_text" for item in result.items)


def test_local_image_ocr_when_tesseract_is_installed(tmp_path) -> None:
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract executable is not installed; OCR integration is an external prerequisite.")
    source = tmp_path / "ocr.png"
    canvas = np.full((240, 1200, 3), 255, dtype=np.uint8)
    cv2.putText(canvas, "CERBERUS PROJECT 12345", (30, 160), cv2.FONT_HERSHEY_SIMPLEX, 2.4,
                (0, 0, 0), 5, cv2.LINE_AA)
    Image.fromarray(canvas).save(source)
    result = extract_image(source)
    assert any("CERBERUS" in item.extracted_text.upper() for item in result.items if item.content_type == "ocr_text")


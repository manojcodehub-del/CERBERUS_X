"""DOCX paragraphs, headings, tables, and core metadata."""

from pathlib import Path

from docx import Document as DocxDocument

from app.services.extraction.common import ExtractedItem
from app.services.extraction.table_extractor import table_cell


def extract_docx(path: Path) -> list[ExtractedItem]:
    document = DocxDocument(path)
    items: list[ExtractedItem] = []
    for index, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()
        if text:
            style = (paragraph.style.name or "") if paragraph.style else ""
            kind = "heading" if style.lower().startswith("heading") or style.lower() == "title" else "paragraph"
            items.append(ExtractedItem(kind, text, "python-docx", paragraph_index=index))
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows, start=1):
            cell_values = [cell.text.strip() for cell in row.cells]
            row_context = " | ".join(value for value in cell_values if value)
            for column_index, value in enumerate(cell_values, start=1):
                if value:
                    item = table_cell(value, "python-docx", row_index, f"Column {column_index}",
                                      f"R{row_index}C{column_index}", table_index=table_index,
                                      context_text=row_context)
                    if item:
                        items.append(item)
    props = document.core_properties
    for key in ("title", "subject", "author", "keywords", "created", "modified"):
        value = getattr(props, key, None)
        if value:
            items.append(ExtractedItem("metadata", f"{key}: {value}", "python-docx-metadata"))
    return items

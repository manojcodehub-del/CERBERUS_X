"""Shared deterministic table cell and header records with exact provenance."""

from app.services.extraction.common import ExtractedItem


def table_cell(value: str, extraction_method: str, row_number: int, column_name: str,
               cell_coordinate: str, *, page_number: int | None = None, sheet_name: str | None = None,
               table_index: int | None = None, context_text: str | None = None) -> ExtractedItem | None:
    if not value:
        return None
    return ExtractedItem("table_cell", value, extraction_method, page_number=page_number,
                         sheet_name=sheet_name, row_number=row_number, column_name=column_name,
                         cell_coordinate=cell_coordinate, table_index=table_index, context_text=context_text)


def table_header(value: str, extraction_method: str, column_name: str, cell_coordinate: str,
                 *, sheet_name: str | None = None) -> ExtractedItem:
    return ExtractedItem("table_header", value, extraction_method, sheet_name=sheet_name, row_number=1,
                         column_name=column_name, cell_coordinate=cell_coordinate)

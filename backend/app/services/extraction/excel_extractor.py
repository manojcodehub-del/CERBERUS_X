"""Read-only XLSX extraction across every worksheet."""

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.services.extraction.common import ExtractedItem, normalize_cell
from app.services.extraction.table_extractor import table_cell, table_header


def extract_excel(path: Path) -> list[ExtractedItem]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    items: list[ExtractedItem] = []
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            headers = next(rows, ())
            header_names = [normalize_cell(value) or f"Column {index}" for index, value in enumerate(headers, start=1)]
            for column_index, name in enumerate(header_names, start=1):
                items.append(table_header(name, "openpyxl", name, f"{get_column_letter(column_index)}1",
                                          sheet_name=sheet.title))
            for row_number, values in enumerate(rows, start=2):
                context_values = [f"{header_names[i]}: {normalize_cell(value)}" for i, value in enumerate(values)
                                  if value is not None and str(value) != ""]
                context = " | ".join(context_values)
                for column_index, value in enumerate(values, start=1):
                    cell_value = normalize_cell(value)
                    if cell_value:
                        column = header_names[column_index - 1] if column_index <= len(header_names) else f"Column {column_index}"
                        item = table_cell(cell_value, "openpyxl", row_number, column,
                                          f"{get_column_letter(column_index)}{row_number}",
                                          sheet_name=sheet.title, context_text=context)
                        if item:
                            items.append(item)
    finally:
        workbook.close()
    return items

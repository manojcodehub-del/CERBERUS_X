"""Chunked CSV extraction with original cell values and row/column provenance."""

from pathlib import Path

import pandas as pd

from app.services.extraction.common import ExtractedItem
from app.services.extraction.table_extractor import table_cell, table_header


def extract_csv(path: Path) -> list[ExtractedItem]:
    items: list[ExtractedItem] = []
    encoding = None
    reader = None
    last_error: Exception | None = None
    for candidate in ("utf-8-sig", "cp1252"):
        try:
            reader = pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=500, encoding=candidate)
            first_chunk = next(reader, None)
            encoding = candidate
            if first_chunk is not None:
                columns = [str(column) for column in first_chunk.columns]
                for column_index, column in enumerate(columns, start=1):
                    items.append(table_header(column, f"pandas-csv:{encoding}", column,
                                              f"{_excel_column(column_index)}1"))
                items.extend(_chunk_items(first_chunk, columns, 2))
                next_row = 2 + len(first_chunk.index)
            else:
                next_row = 2
            for chunk in reader:
                columns = [str(column) for column in chunk.columns]
                items.extend(_chunk_items(chunk, columns, next_row))
                next_row += len(chunk.index)
            return items
        except (UnicodeDecodeError, pd.errors.ParserError, StopIteration) as exc:
            last_error = exc
            items.clear()
            continue
    raise ValueError("The CSV encoding or row structure is not supported.") from last_error


def _chunk_items(frame: pd.DataFrame, columns: list[str], first_row: int) -> list[ExtractedItem]:
    result = []
    for offset, values in enumerate(frame.itertuples(index=False, name=None)):
        row_number = first_row + offset
        context = " | ".join(f"{column}: {value}" for column, value in zip(columns, values) if value != "")
        for column_index, (column, value) in enumerate(zip(columns, values), start=1):
            if value != "":
                item = table_cell(str(value), "pandas-csv", row_number, column,
                                  f"{_excel_column(column_index)}{row_number}", context_text=context)
                if item:
                    result.append(item)
    return result


def _excel_column(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result

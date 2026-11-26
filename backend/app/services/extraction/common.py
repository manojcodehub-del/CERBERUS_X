"""Shared extraction records and stable idempotency keys."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExtractedItem:
    content_type: str
    extracted_text: str
    extraction_method: str
    page_number: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    column_name: str | None = None
    cell_coordinate: str | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    extraction_confidence: float | None = None
    context_text: str | None = None

    @property
    def original_text(self) -> str:
        return self.extracted_text

    def evidence_key(self, document_id: str, source_hash: str) -> str:
        payload = {"document_id": document_id, "source_hash": source_hash, **asdict(self)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass
class ExtractionResult:
    items: list[ExtractedItem]
    warnings: list[str]


def normalize_cell(value: object) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

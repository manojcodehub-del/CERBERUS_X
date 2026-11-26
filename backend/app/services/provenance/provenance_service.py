"""Persistence helpers that preserve exact source text and stable source keys."""

from app.models.document import Document
from app.models.evidence import Evidence
from app.services.extraction.common import ExtractedItem


def evidence_from_item(document: Document, item: ExtractedItem) -> Evidence:
    return Evidence(
        document_id=document.id,
        filename=document.original_filename,
        page_number=item.page_number,
        sheet_name=item.sheet_name,
        row_number=item.row_number,
        column_name=item.column_name,
        content_type=item.content_type,
        extracted_text=item.extracted_text,
        cell_coordinate=item.cell_coordinate,
        paragraph_index=item.paragraph_index,
        table_index=item.table_index,
        source_hash=document.sha256,
        evidence_key=item.evidence_key(document.id, document.sha256),
        original_text=item.original_text,
        extraction_method=item.extraction_method,
        extraction_confidence=item.extraction_confidence,
        context_text=item.context_text,
    )

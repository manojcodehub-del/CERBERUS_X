"""Document API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str
    processing_status: str
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int
    limit: int
    offset: int


class UploadBatchResponse(BaseModel):
    items: list[DocumentRead]
    total: int


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_type: str
    value: str
    normalized_value: str
    context: str | None
    confidence: float | None


class EvidenceRead(BaseModel):
    id: int
    document_id: str
    filename: str
    content_type: str | None
    extracted_text: str | None
    original_text: str
    page_number: int | None
    sheet_name: str | None
    row_number: int | None
    column_name: str | None
    cell_coordinate: str | None
    paragraph_index: int | None
    table_index: int | None
    context_text: str | None = None
    extraction_method: str
    extraction_confidence: float | None
    source_hash: str | None
    created_at: datetime
    claims: list[ClaimRead]


class EvidenceList(BaseModel):
    items: list[EvidenceRead]
    total: int


class ProcessRead(BaseModel):
    document_id: str
    job_id: str
    status: str
    evidence_count: int
    claim_count: int
    warnings: list[str]
    error: str | None


class DocumentStatusRead(BaseModel):
    document_id: str
    status: str
    job_id: str | None
    job_status: str | None
    progress: int | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

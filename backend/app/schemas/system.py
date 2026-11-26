"""System and analytics response schemas."""

from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    service: str
    database: str


class SystemStatusRead(BaseModel):
    status: str
    application: str
    environment: str
    database: str
    upload_storage: str
    document_processing: str
    ocr_engine: str
    storage_free_bytes: int | None = None
    offline_readiness: str = "not_verified"


class AnalyticsRead(BaseModel):
    total_documents: int
    uploaded_documents: int
    processing_documents: int
    processed_documents: int
    failed_documents: int
    total_evidence: int
    total_contradictions: int
    active_jobs: int

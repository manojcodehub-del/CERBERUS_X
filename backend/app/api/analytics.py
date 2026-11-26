"""Database-backed counts for the dashboard."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.processing_job import ProcessingJob
from app.schemas.system import AnalyticsRead

router = APIRouter(tags=["analytics"])


def _count(session: Session, model: type, condition=None) -> int:
    statement = select(func.count()).select_from(model)
    if condition is not None:
        statement = statement.where(condition)
    return session.scalar(statement) or 0


@router.get("/analytics", response_model=AnalyticsRead)
def analytics(session: Session = Depends(get_database_session)) -> AnalyticsRead:
    return AnalyticsRead(
        total_documents=_count(session, Document),
        uploaded_documents=_count(session, Document, Document.processing_status.in_(("uploaded", "UPLOADED"))),
        processing_documents=_count(session, Document, Document.processing_status.in_(("processing", "VALIDATING", "QUEUED", "PROCESSING"))),
        processed_documents=_count(session, Document, Document.processing_status.in_(("processed", "COMPLETED", "PARTIALLY_COMPLETED"))),
        failed_documents=_count(session, Document, Document.processing_status.in_(("failed", "PROCESSING_FAILED", "OCR_UNAVAILABLE", "VALIDATION_FAILED"))),
        total_evidence=_count(session, Evidence),
        total_contradictions=_count(session, Contradiction),
        active_jobs=_count(session, ProcessingJob, ProcessingJob.status.in_(("queued", "validating", "running"))),
    )

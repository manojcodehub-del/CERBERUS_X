"""Idempotent document extraction and source evidence persistence."""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.claim import Claim
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.processing_job import ProcessingJob
from app.services.extraction.common import ExtractedItem
from app.services.extraction.claim_extractor import extract_claim_candidates
from app.services.ingestion.ingestion_service import extract_document
from app.services.ingestion.file_validator import FileValidationError, validate_content
from app.services.provenance.provenance_service import evidence_from_item

logger = logging.getLogger(__name__)


def process_document(document: Document, session: Session, settings: Settings) -> dict:
    job = ProcessingJob(document_id=document.id, job_type="document_extraction", status="validating", progress=0)
    session.add(job)
    document.processing_status = "VALIDATING"
    session.commit()
    job = session.get(ProcessingJob, job.id)
    document = session.get(Document, document.id)
    if job is None or document is None:
        raise RuntimeError("The processing record could not be initialized.")

    job.started_at = datetime.now(timezone.utc)
    job.progress = 5
    session.commit()

    stored_path = (settings.resolved_upload_dir / document.stored_filename).resolve()
    if stored_path.parent != settings.resolved_upload_dir.resolve() or not stored_path.is_file():
        return _mark_failure(document, job, session, "The stored document file is missing or its storage reference is invalid.", "VALIDATION_FAILED")
    try:
        if stored_path.stat().st_size != document.size_bytes or document.size_bytes > settings.max_upload_mb * 1024 * 1024:
            return _mark_failure(document, job, session, "Stored file size does not match the validated upload.", "VALIDATION_FAILED")
        digest = hashlib.sha256()
        with stored_path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != document.sha256:
            return _mark_failure(document, job, session, "Stored file integrity check failed.", "VALIDATION_FAILED")
        validate_content(stored_path, document.extension, settings.max_upload_mb * 1024 * 1024)
    except FileValidationError as exc:
        return _mark_failure(document, job, session, str(exc), "VALIDATION_FAILED")
    except OSError:
        return _mark_failure(document, job, session, "The stored document could not be validated.", "VALIDATION_FAILED")

    job.status = "queued"
    job.progress = 10
    document.processing_status = "QUEUED"
    session.commit()
    job.status = "running"
    job.progress = 20
    document.processing_status = "PROCESSING"
    session.commit()

    try:
        result = extract_document(stored_path, document.extension, settings.tesseract_cmd, settings.ocr_engine)
        job.progress = 65
        session.commit()

        existing_keys = set(session.scalars(select(Evidence.evidence_key).where(
            Evidence.document_id == document.id, Evidence.evidence_key.is_not(None)
        )).all())
        newly_added: list[tuple[Evidence, ExtractedItem]] = []
        for item in result.items:
            key = item.evidence_key(document.id, document.sha256)
            if key in existing_keys:
                continue
            row = evidence_from_item(document, item)
            session.add(row)
            newly_added.append((row, item))
            existing_keys.add(key)
        session.flush()

        seen_claims: set[tuple[int, str, str]] = set()
        for row, item in newly_added:
            for candidate in extract_claim_candidates(item.extracted_text, item.context_text):
                normalized = candidate.value.casefold().strip()[:512]
                key = (row.id, candidate.claim_type, normalized)
                if key in seen_claims:
                    continue
                seen_claims.add(key)
                session.add(Claim(evidence_id=row.id, claim_type=candidate.claim_type, value=candidate.value,
                                  normalized_value=normalized, context=candidate.context,
                                  confidence=row.extraction_confidence))
        session.flush()

        evidence_count = session.scalar(select(func.count()).select_from(Evidence).where(Evidence.document_id == document.id)) or 0
        claim_count = session.scalar(select(func.count()).select_from(Claim).join(Evidence).where(Evidence.document_id == document.id)) or 0
        has_ocr_unavailable = any(
            "ocr" in warning.casefold()
            and ("unavailable" in warning.casefold() or "not installed/configured" in warning.casefold())
            for warning in result.warnings
        )
        has_content = any(item.content_type != "metadata" for item in result.items)
        if has_ocr_unavailable and not has_content:
            status, job_status = "OCR_UNAVAILABLE", "failed"
        elif not evidence_count:
            status, job_status = "PROCESSING_FAILED", "failed"
            result.warnings.append("No extractable content was found in the document.")
        elif result.warnings:
            status, job_status = "PARTIALLY_COMPLETED", "partial"
        else:
            status, job_status = "COMPLETED", "completed"
        document.processing_status = status
        job.status = job_status
        job.progress = 100
        job.error_message = "\n".join(result.warnings)[:4000] or None
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
        return {
            "document_id": document.id,
            "job_id": job.id,
            "status": status,
            "evidence_count": evidence_count,
            "claim_count": claim_count,
            "warnings": result.warnings,
            "error": job.error_message,
        }
    except Exception as exc:
        session.rollback()
        # Do not include parser exception text: third-party errors may echo sensitive document content.
        logger.warning("Document extraction failed (%s); document content was not logged.", type(exc).__name__)
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(ProcessingJob, job.id)
        if refreshed_document is None or refreshed_job is None:
            raise
        return _mark_failure(refreshed_document, refreshed_job, session,
                             f"Document extraction failed ({type(exc).__name__}). Check file integrity and local dependencies.")


def _mark_failure(document: Document, job: ProcessingJob, session: Session, message: str,
                  document_status: str = "PROCESSING_FAILED") -> dict:
    document.processing_status = document_status
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc)
    job.progress = 100
    session.commit()
    evidence_count = session.scalar(select(func.count()).select_from(Evidence).where(Evidence.document_id == document.id)) or 0
    claim_count = session.scalar(select(func.count()).select_from(Claim).join(Evidence).where(Evidence.document_id == document.id)) or 0
    return {"document_id": document.id, "job_id": job.id, "status": document.processing_status,
            "evidence_count": evidence_count, "claim_count": claim_count, "warnings": [message], "error": message}

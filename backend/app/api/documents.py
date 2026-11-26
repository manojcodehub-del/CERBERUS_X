"""Document metadata listing and local upload endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.database.dependencies import get_database_session
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.processing_job import ProcessingJob
from app.schemas.document import (ClaimRead, DocumentList, DocumentRead, DocumentStatusRead, EvidenceList,
                                  EvidenceRead, ProcessRead, UploadBatchResponse)
from app.services.document_storage import delete_stored_file, store_uploads
from app.services.ingestion.processing_service import process_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentList)
def list_documents(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_database_session),
) -> DocumentList:
    total = session.scalar(select(func.count()).select_from(Document)) or 0
    documents = session.scalars(
        select(Document).order_by(Document.created_at.desc(), Document.id).limit(limit).offset(offset)
    ).all()
    return DocumentList(items=documents, total=total, limit=limit, offset=offset)


@router.post("/upload", response_model=UploadBatchResponse, status_code=201)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(..., description="One or more supported local documents."),
    session: Session = Depends(get_database_session),
) -> UploadBatchResponse:
    if len(files) > request.app.state.settings.max_upload_files:
        raise APIException(413, "too_many_files", "The upload contains more files than the configured limit.")
    documents = await store_uploads(files, session, request.app.state.settings)
    return UploadBatchResponse(items=documents, total=len(documents))


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: str,
    session: Session = Depends(get_database_session),
) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    return document


@router.post("/{document_id}/process", response_model=ProcessRead)
def process_uploaded_document(
    document_id: str,
    request: Request,
    session: Session = Depends(get_database_session),
) -> dict:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    return process_document(document, session, request.app.state.settings)


@router.get("/{document_id}/evidence", response_model=EvidenceList)
def list_document_evidence(
    document_id: str,
    session: Session = Depends(get_database_session),
) -> EvidenceList:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    evidence = session.scalars(
        select(Evidence).options(joinedload(Evidence.claims)).where(Evidence.document_id == document_id)
        .order_by(Evidence.page_number, Evidence.sheet_name, Evidence.row_number, Evidence.id)
    ).unique().all()
    return EvidenceList(items=[EvidenceRead(
        id=row.id, document_id=row.document_id, filename=row.filename or document.original_filename,
        content_type=row.content_type, extracted_text=row.extracted_text, original_text=row.original_text,
        page_number=row.page_number, sheet_name=row.sheet_name, row_number=row.row_number,
        column_name=row.column_name, cell_coordinate=row.cell_coordinate, paragraph_index=row.paragraph_index,
        table_index=row.table_index, context_text=row.context_text, extraction_method=row.extraction_method,
        extraction_confidence=row.extraction_confidence, source_hash=row.source_hash, created_at=row.created_at,
        claims=[ClaimRead.model_validate(claim) for claim in row.claims],
    ) for row in evidence], total=len(evidence))


@router.get("/{document_id}/status", response_model=DocumentStatusRead)
def get_document_status(
    document_id: str,
    session: Session = Depends(get_database_session),
) -> DocumentStatusRead:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    job = session.scalar(select(ProcessingJob).where(ProcessingJob.document_id == document_id)
                         .order_by(ProcessingJob.created_at.desc()).limit(1))
    return DocumentStatusRead(
        document_id=document.id, status=document.processing_status,
        job_id=job.id if job else None, job_status=job.status if job else None,
        progress=job.progress if job else None, error=job.error_message if job else None,
        created_at=document.created_at, started_at=job.started_at if job else None,
        completed_at=job.completed_at if job else None,
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    request: Request,
    session: Session = Depends(get_database_session),
) -> Response:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    delete_stored_file(document, request.app.state.settings)
    session.delete(document)
    session.commit()
    return Response(status_code=204)

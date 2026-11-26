"""Evidence verification endpoint backed by existing local retrieval."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.document import Document
from app.schemas.verification import VerificationRead, VerificationRequest
from app.services.ollama.client import OllamaClient, OllamaError
from app.services.verification.verification_service import run_verification

router = APIRouter(tags=["evidence verification"])


@router.post("/verification/analyze", response_model=VerificationRead)
def analyze(payload: VerificationRequest, request: Request, session: Session = Depends(get_database_session)) -> VerificationRead:
    if payload.document_ids:
        found = set(session.scalars(select(Document.id).where(Document.id.in_(payload.document_ids))).all())
        if found != set(payload.document_ids):
            raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "One or more requested documents were not found."})
    try:
        client = OllamaClient(request.app.state.settings)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    result = run_verification(session, request.app.state.settings, client, payload.question,
                              payload.document_ids, payload.top_k)
    session.commit()
    return VerificationRead(**result)

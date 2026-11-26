"""Source evaluation endpoints with criterion-level explanations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.document import Document
from app.schemas.verification import SourceEvaluationList, SourceEvaluationRead
from app.services.reliability.source_reliability import SCORE_NOTICE, evaluate_source, evaluate_sources
from app.services.verification.serialization import source_read

router = APIRouter(tags=["source reliability"])


@router.get("/reliability/sources", response_model=SourceEvaluationList)
def list_source_evaluations(session: Session = Depends(get_database_session)) -> SourceEvaluationList:
    evaluations = evaluate_sources(session)
    documents = {item.id: item for item in session.scalars(select(Document)).all()}
    session.commit()
    return SourceEvaluationList(items=[source_read(item, documents[item.document_id]) for item in evaluations
                                      if item.document_id in documents],
                               total=len(evaluations), score_notice=SCORE_NOTICE)


@router.get("/reliability/sources/{document_id}", response_model=SourceEvaluationRead)
def get_source_evaluation(document_id: str, session: Session = Depends(get_database_session)) -> SourceEvaluationRead:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    evaluation = evaluate_source(session, document_id)
    session.commit()
    if evaluation is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    return source_read(evaluation, document)

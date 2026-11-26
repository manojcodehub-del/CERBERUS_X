"""Claim listing and deterministic normalization endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.claim import Claim
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.knowledge_graph import KnowledgeGraphEdge, KnowledgeGraphNode
from app.schemas.verification import ClaimList, ClaimNormalizeRequest, ClaimNormalizeResponse, ClaimRead
from app.services.contradiction.conflict_service import detect_conflicts
from app.services.knowledge_graph.graph_service import build_graph
from app.services.normalization.claim_normalizer import normalize_claim
from app.services.reliability.source_reliability import evaluate_sources
from app.services.verification.serialization import claim_read

router = APIRouter(tags=["evidence verification"])


@router.get("/claims", response_model=ClaimList)
def list_claims(
    document_id: str | None = None,
    normalized_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    session: Session = Depends(get_database_session),
) -> ClaimList:
    statement = select(Claim, Evidence, Document).join(Evidence, Evidence.id == Claim.evidence_id).join(Document, Document.id == Evidence.document_id)
    if document_id:
        statement = statement.where(Document.id == document_id)
    if normalized_only:
        statement = statement.where(Claim.normalization_method.is_not(None))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(statement.order_by(Claim.id).limit(limit).offset(offset)).all()
    items = [claim_read(claim, evidence, document) for claim, evidence, document in rows]
    return ClaimList(items=items, total=total, limit=limit, offset=offset)


@router.post("/claims/normalize", response_model=ClaimNormalizeResponse)
def normalize_claims(payload: ClaimNormalizeRequest, session: Session = Depends(get_database_session)) -> ClaimNormalizeResponse:
    if payload.document_ids:
        found = set(session.scalars(select(Document.id).where(Document.id.in_(payload.document_ids))).all())
        if found != set(payload.document_ids):
            raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "One or more requested documents were not found."})
    if payload.claim_ids:
        found = set(session.scalars(select(Claim.id).where(Claim.id.in_(payload.claim_ids))).all())
        if found != set(payload.claim_ids):
            raise HTTPException(status_code=404, detail={"code": "claim_not_found", "message": "One or more requested claims were not found."})

    statement = select(Claim, Evidence, Document).join(Evidence, Evidence.id == Claim.evidence_id).join(Document, Document.id == Evidence.document_id)
    if payload.claim_ids is not None:
        statement = statement.where(Claim.id.in_(payload.claim_ids))
    elif payload.document_ids:
        statement = statement.where(Document.id.in_(payload.document_ids), Claim.normalization_method.is_(None))
    else:
        statement = statement.where(Claim.normalization_method.is_(None))
    if payload.claim_ids is not None and payload.document_ids:
        statement = statement.where(Document.id.in_(payload.document_ids))
    rows = session.execute(statement.order_by(Claim.id)).all()
    target_ids = [claim.id for claim, _, _ in rows]
    changed_ids = []
    unchanged = 0
    for claim, evidence, document in rows:
        if normalize_claim(claim, evidence, document):
            changed_ids.append(claim.id)
        else:
            unchanged += 1
    session.flush()
    evaluate_sources(session)
    conflicts_created = detect_conflicts(session, changed_ids or target_ids)
    build_graph(session)
    session.flush()
    result_rows = session.execute(select(Claim, Evidence, Document)
                                  .join(Evidence, Evidence.id == Claim.evidence_id)
                                  .join(Document, Document.id == Evidence.document_id)
                                  .where(Claim.id.in_(target_ids)).order_by(Claim.id)).all() if target_ids else []
    session.commit()
    return ClaimNormalizeResponse(
        normalized=len(changed_ids), unchanged=unchanged,
        claims=[claim_read(claim, evidence, document) for claim, evidence, document in result_rows],
        conflicts_created=conflicts_created,
        graph_nodes=session.scalar(select(func.count()).select_from(KnowledgeGraphNode)) or 0,
        graph_edges=session.scalar(select(func.count()).select_from(KnowledgeGraphEdge)) or 0,
    )

"""Conflict review and append-only resolution history."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.claim import Claim
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.conflict_resolution import ConflictResolution
from app.schemas.verification import ConflictList, ConflictRead, ConflictResolutionRead, ConflictResolutionRequest
from app.services.verification.serialization import claim_read, conflict_read

router = APIRouter(tags=["evidence verification"])
CLASSIFICATIONS = "CONFIRMED_CONFLICT|POTENTIAL_CONFLICT|TEMPORAL_DIFFERENCE|CATEGORY_MISMATCH|UNIT_MISMATCH|UNRESOLVED|NO_CONFLICT|POSSIBLE_DUPLICATE"
STATUSES = "open|under_review|resolved|dismissed"


def _read(session: Session, conflict: Contradiction) -> dict:
    pair = []
    for claim_id, evidence_id in ((conflict.claim_a_id, conflict.evidence_a_id), (conflict.claim_b_id, conflict.evidence_b_id)):
        claim = session.get(Claim, claim_id) if claim_id else None
        evidence = session.get(Evidence, evidence_id)
        document = session.get(Document, evidence.document_id) if evidence else None
        pair.append(claim_read(claim, evidence, document) if claim and evidence and document else None)
    return conflict_read(conflict, pair[0], pair[1])


@router.get("/contradictions", response_model=ConflictList)
def list_contradictions(
    classification: str | None = Query(default=None, pattern=f"^({CLASSIFICATIONS})$"),
    status: str | None = Query(default=None, pattern=f"^({STATUSES})$"),
    document_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    session: Session = Depends(get_database_session),
) -> ConflictList:
    statement = select(Contradiction)
    if classification:
        statement = statement.where(Contradiction.classification == classification)
    if status:
        statement = statement.where(Contradiction.status == status)
    if document_id:
        evidence_ids = select(Evidence.id).where(Evidence.document_id == document_id)
        statement = statement.where(Contradiction.evidence_a_id.in_(evidence_ids) | Contradiction.evidence_b_id.in_(evidence_ids))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    conflicts = session.scalars(statement.order_by(Contradiction.id.desc()).limit(limit).offset(offset)).all()
    return ConflictList(items=[_read(session, item) for item in conflicts], total=total)


@router.get("/contradictions/{conflict_id}", response_model=ConflictRead)
def get_contradiction(conflict_id: int, session: Session = Depends(get_database_session)) -> ConflictRead:
    conflict = session.get(Contradiction, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=404, detail={"code": "conflict_not_found", "message": "Conflict finding not found."})
    return _read(session, conflict)


@router.post("/contradictions/{conflict_id}/resolve", response_model=ConflictResolutionRead)
def resolve_contradiction(conflict_id: int, payload: ConflictResolutionRequest,
                          session: Session = Depends(get_database_session)) -> ConflictResolutionRead:
    conflict = session.get(Contradiction, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=404, detail={"code": "conflict_not_found", "message": "Conflict finding not found."})
    now = datetime.now(timezone.utc)
    audit = ConflictResolution(conflict_id=conflict.id, status=payload.status, note=payload.note)
    session.add(audit)
    conflict.status = payload.status
    conflict.resolved_at = now if payload.status in {"resolved", "dismissed"} else None
    session.commit()
    session.refresh(audit)
    return ConflictResolutionRead(conflict_id=audit.conflict_id, status=audit.status,
                                  note=audit.note, created_at=audit.created_at.isoformat())

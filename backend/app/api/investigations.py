"""Persisted investigations with traceable local evidence reports."""

import json
import re
import textwrap
from datetime import datetime, timezone

import pymupdf as fitz
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.document import Document
from app.models.investigation import Investigation
from app.schemas.investigation import (
    InvestigationCreate, InvestigationGenerateRequest, InvestigationList,
    InvestigationListItem, InvestigationRead,
)
from app.services.investigation.investigation_service import generate_investigation
from app.services.ollama.client import OllamaClient, OllamaError

router = APIRouter(tags=["investigations"])


def _document_ids(row: Investigation) -> list[str] | None:
    return json.loads(row.document_ids_json) if row.document_ids_json else None


def _read(row: Investigation, include_report: bool = True):
    values = dict(id=row.id, title=row.title, question=row.question, status=row.status,
                  document_ids=_document_ids(row), top_k=row.top_k,
                  created_at=row.created_at, updated_at=row.updated_at)
    if include_report:
        values["report"] = json.loads(row.report_json) if row.report_json else None
        return InvestigationRead(**values)
    return InvestigationListItem(**values)


def _validate_documents(session: Session, document_ids: list[str] | None) -> None:
    if document_ids is None:
        return
    found = set(session.scalars(select(Document.id).where(Document.id.in_(document_ids))).all())
    if found != set(document_ids):
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "One or more selected documents were not found."})


@router.get("/investigations", response_model=InvestigationList)
def list_investigations(limit: int = Query(default=50, ge=1, le=100),
                        offset: int = Query(default=0, ge=0, le=10000),
                        session: Session = Depends(get_database_session)) -> InvestigationList:
    total = session.scalar(select(func.count()).select_from(Investigation)) or 0
    rows = session.scalars(select(Investigation).order_by(Investigation.updated_at.desc(), Investigation.id.desc())
                           .limit(limit).offset(offset)).all()
    return InvestigationList(items=[_read(row, include_report=False) for row in rows], total=total)


@router.post("/investigations", response_model=InvestigationRead, status_code=201)
def create_investigation(payload: InvestigationCreate, session: Session = Depends(get_database_session)) -> InvestigationRead:
    _validate_documents(session, payload.document_ids)
    row = Investigation(title=payload.title, question=payload.question,
                        document_ids_json=json.dumps(payload.document_ids) if payload.document_ids is not None else None,
                        top_k=payload.top_k, status="draft")
    session.add(row)
    session.commit()
    session.refresh(row)
    return _read(row)


@router.get("/investigations/{investigation_id}", response_model=InvestigationRead)
def get_investigation(investigation_id: int, session: Session = Depends(get_database_session)) -> InvestigationRead:
    row = session.get(Investigation, investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "investigation_not_found", "message": "Investigation not found."})
    return _read(row)


@router.post("/investigations/{investigation_id}/generate", response_model=InvestigationRead)
def generate_report(investigation_id: int, payload: InvestigationGenerateRequest, request: Request,
                    session: Session = Depends(get_database_session)) -> InvestigationRead:
    row = session.get(Investigation, investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "investigation_not_found", "message": "Investigation not found."})
    selected_ids = _document_ids(row)
    _validate_documents(session, selected_ids)
    try:
        client = OllamaClient(request.app.state.settings)
        report = generate_investigation(session, request.app.state.settings, client, row, payload.top_k)
    except OllamaError as exc:
        report = {"question": row.question, "scope": {"kind": "selected_documents" if selected_ids else "whole_collection",
                   "document_ids": selected_ids, "document_count": len(selected_ids or [])},
                  "executive_summary": {"text": "I cannot answer because the configured local model is unavailable.", "citations": [], "abstained": True},
                  "supporting_evidence": [], "opposing_evidence": [], "context_evidence": [], "relevant_evidence": [],
                  "relevant_claims": [], "supporting_claims": [], "opposing_claims": [], "context_claims": [], "contradictions": [], "source_reliability": [], "relevant_relationships": [],
                  "missing_evidence": [str(exc)], "conclusion": {"text": "Insufficient evidence; no conclusion was generated.", "citations": [], "abstained": True},
                  "limitations": ["Local model unavailable; report generation abstained."], "uncertainty": [str(exc)],
                  "diagnostics": [], "retrieval_method": "none", "normalized_claims": 0}
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    row.top_k = payload.top_k or row.top_k
    row.report_json = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    row.status = "ready"
    row.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(row)
    return _read(row)


def _location(item: dict) -> str:
    value = item.get("source_location") or item
    parts = []
    for key, label in (("page_number", "page"), ("sheet_name", "sheet"), ("row_number", "row"),
                       ("cell_coordinate", "cell"), ("paragraph_index", "paragraph"), ("table_index", "table")):
        if value.get(key) is not None:
            parts.append(f"{label} {value[key]}")
    return ", ".join(parts) if parts else "location not provided by the source"


def _pdf_lines(row: Investigation, report: dict) -> list[tuple[str, bool]]:
    lines: list[tuple[str, bool]] = [("CERBERUS-X INVESTIGATION REPORT", True), (row.title, True),
                                    ("Generated: " + str(report.get("generated_at") or ""), False),
                                    ("Investigation question", True), (row.question, False),
                                    ("Executive summary", True),
                                    (report.get("executive_summary", {}).get("text", "No summary generated."), False)]
    citations = report.get("executive_summary", {}).get("citations", [])
    if citations:
        lines.append(("Verified citations", True))
        for item in citations:
            lines.append((f"[E{item.get('evidence_id')}] {item.get('filename')} - {_location(item)}: {item.get('quoted_text', '')}", False))
    for section, title in (("supporting_evidence", "Supporting evidence"), ("opposing_evidence", "Opposing evidence"), ("context_evidence", "Context / uncertain evidence")):
        lines.append((title, True))
        items = report.get(section, [])
        if not items:
            lines.append(("No validated passages in this section.", False))
        for item in items:
            lines.append((f"[E{item.get('evidence_id')}] {item.get('filename')} - {_location(item)} ({item.get('stance', 'source')}): {item.get('quote', '')}", False))
    lines.append(("Relevant claims", True))
    claims = report.get("relevant_claims", [])
    if not claims:
        lines.append(("No normalized claims were linked to the retrieved evidence.", False))
    for item in claims:
        lines.append((f"[E{item.get('evidence_id')}] {item.get('filename')} / claim {item.get('id')} / {item.get('stance', 'claim')}: {item.get('value')} (normalized {item.get('object_value') or item.get('normalized_value')}; {_location(item)})", False))
    lines.append(("Contradictions and unresolved issues", True))
    conflicts = report.get("contradictions", [])
    if not conflicts:
        lines.append(("No comparison findings were returned for the retrieved evidence.", False))
    for item in conflicts:
        confidence = f" Heuristic confidence {item['confidence']:.0%}." if item.get("confidence") is not None else ""
        confidence_note = f" {item.get('confidence_note')}" if item.get("confidence_note") else ""
        lines.append((f"Finding #{item.get('id')} - {item.get('classification')} [{item.get('status')}]:{confidence}{confidence_note} {item.get('explanation') or ''}", False))
        for side in ("claim_a", "claim_b"):
            claim = item.get(side)
            if claim:
                lines.append((f"  [E{claim.get('evidence_id')}] {claim.get('filename')} / document {claim.get('document_id')} / claim {claim.get('id')}: {claim.get('value')} (normalized {claim.get('object_value') or claim.get('normalized_value')}; {_location(claim)})", False))
    lines.append(("Source reliability explanations", True))
    sources = report.get("source_reliability", [])
    if not sources:
        lines.append(("No source evaluation was available.", False))
    for item in sources:
        lines.append((f"{item.get('filename')}: {item.get('heuristic_score')} heuristic score. {item.get('explanation', '')}", False))
    lines.append(("Missing evidence", True))
    for item in report.get("missing_evidence", []) or ["No missing-evidence note was recorded."]:
        lines.append(("- " + item, False))
    lines.append(("Conclusion and limitations", True))
    conclusion = report.get("conclusion", {})
    lines.append((conclusion.get("text", "No conclusion generated."), False))
    if conclusion.get("citations"):
        lines.append(("Conclusion citations: " + ", ".join(f"[E{item.get('evidence_id')}]" for item in conclusion["citations"]), False))
    if conclusion.get("abstained"):
        lines.append(("Status: ABSTAINED - evidence did not support a safe conclusion.", True))
    for item in report.get("limitations", []):
        lines.append(("- " + str(item), False))
    lines.append(("Generated from local CERBERUS-X records. Heuristic reliability and stance labels require human review.", False))
    return lines


def _render_pdf(row: Investigation, report: dict) -> bytes:
    output = fitz.open()
    page = output.new_page(width=595, height=842)
    y = 48
    for text, heading in _pdf_lines(row, report):
        safe = text.encode("cp1252", "replace").decode("cp1252")
        width = 86 if heading else 96
        wrapped = textwrap.wrap(safe, width=width, replace_whitespace=True, drop_whitespace=True) or [""]
        for line in wrapped:
            if y > 790:
                page = output.new_page(width=595, height=842)
                y = 48
            page.insert_text((48, y), line, fontname="hebo" if heading else "helv",
                             fontsize=12 if heading else 9, color=(0.04, 0.20, 0.32) if heading else (0.12, 0.16, 0.20))
            y += 19 if heading else 13
        y += 3
    output.set_metadata({"title": row.title, "author": "CERBERUS-X local report generator", "subject": row.question})
    data = output.tobytes(garbage=4, deflate=True)
    output.close()
    return data


@router.get("/investigations/{investigation_id}/report.pdf")
def export_report_pdf(investigation_id: int, session: Session = Depends(get_database_session)) -> Response:
    row = session.get(Investigation, investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "investigation_not_found", "message": "Investigation not found."})
    if not row.report_json:
        raise HTTPException(status_code=409, detail={"code": "report_not_generated", "message": "Generate the investigation report before exporting PDF."})
    try:
        report = json.loads(row.report_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=409, detail={"code": "report_invalid", "message": "The saved report cannot be read."}) from exc
    pdf = _render_pdf(row, report)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="cerberus_x_investigation_{row.id}.pdf"'})


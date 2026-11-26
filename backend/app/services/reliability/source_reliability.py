"""Transparent source-quality heuristics; scores are not validated probabilities."""

import hashlib
import json
import os
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.source_evaluation import SourceEvaluation

WEIGHTS = {
    "authority": 0.20,
    "approval_status": 0.20,
    "recency": 0.10,
    "directness": 0.20,
    "completeness": 0.10,
    "extraction_quality": 0.15,
    "independent_corroboration": 0.05,
}
SCORE_NOTICE = "Heuristic review aid only; not a scientifically validated reliability probability. Default weights are configured in source_reliability.py and can be overridden with CERBERUS_RELIABILITY_WEIGHTS JSON. Distinct text fingerprints are only a proxy for source independence. Recency uses a neutral score because a trusted source-publication date is not currently stored."


def _configured_weights() -> dict[str, float]:
    raw = os.getenv("CERBERUS_RELIABILITY_WEIGHTS")
    if not raw:
        return dict(WEIGHTS)
    try:
        configured = json.loads(raw)
        if set(configured) != set(WEIGHTS):
            raise ValueError
        values = {key: float(configured[key]) for key in WEIGHTS}
        if any(value < 0 for value in values.values()) or abs(sum(values.values()) - 1.0) > 0.001:
            raise ValueError
        return values
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("CERBERUS_RELIABILITY_WEIGHTS must be a JSON object with all criteria, nonnegative weights, and a sum of 1.") from exc


def _source_fingerprint(rows: list[Evidence], fallback: str) -> str:
    body = "\n".join(re.sub(r"\s+", " ", (item.original_text or "").casefold()).strip() for item in rows)
    return hashlib.sha256((body or fallback).encode("utf-8")).hexdigest()


def _approval_status(document: Document, content: str) -> tuple[str, str]:
    title = document.original_filename.casefold()
    text = f"{title} {content.casefold()}"
    if re.search(r"\b(draft|preliminary|proposal)\b", text):
        return "draft", "Explicit draft, preliminary or proposal language was found."
    if re.search(r"\b(superseded|obsolete|archived|historical)\b", text):
        return "historical", "The source labels itself as superseded, obsolete, archived or historical."
    if re.search(r"\b(approved|signed|final)\b", text):
        return "approved", "Explicit approval, signature or final-state language was found; this is a textual signal only."
    return "unverified", "No explicit approval or draft state was detected in the stored filename or extracted text."


def _authority(document: Document, content: str) -> tuple[float, str]:
    text = f"{document.original_filename} {content[:4000]}".casefold()
    if re.search(r"\b(government|official|signed contract|purchase order|approved by)\b", text):
        return 0.85, "Official, signed or government wording was detected; authenticity is not independently verified."
    return 0.50, "No source authority metadata is available; authority remains neutral."


def _evaluate_rows(session: Session) -> list[SourceEvaluation]:
    weights = _configured_weights()
    documents = session.scalars(select(Document).order_by(Document.created_at, Document.id)).all()
    evidence_by_doc: dict[str, list[Evidence]] = defaultdict(list)
    evidence_rows = session.scalars(select(Evidence).order_by(Evidence.document_id, Evidence.id)).all()
    for row in evidence_rows:
        evidence_by_doc[row.document_id].append(row)
    claims = session.scalars(select(Claim).where(Claim.normalization_method == "phase5-deterministic-v1")).all()
    claims_by_doc: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        # document_identifier is assigned by the normalizer and points to the existing document row.
        if claim.document_identifier:
            claims_by_doc[claim.document_identifier].append(claim)

    fingerprints = {
        document.id: _source_fingerprint(evidence_by_doc[document.id], document.sha256)
        for document in documents
    }
    first_by_fingerprint: dict[str, str] = {}
    for document in documents:
        first_by_fingerprint.setdefault(fingerprints[document.id], document.id)

    claim_sources: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for document_id, doc_claims in claims_by_doc.items():
        for claim in doc_claims:
            if claim.project_identifier and claim.predicate and claim.object_value:
                claim_sources[(claim.project_identifier.casefold(), claim.predicate, claim.object_value)].add(document_id)

    result = []
    for document in documents:
        rows = evidence_by_doc[document.id]
        content = "\n".join(item.original_text or "" for item in rows)
        fingerprint = fingerprints[document.id]
        duplicate_of = first_by_fingerprint[fingerprint]
        duplicate = duplicate_of != document.id
        approval, approval_reason = _approval_status(document, content)
        authority, authority_reason = _authority(document, content)
        directness = 0.85 if claims_by_doc[document.id] else (0.45 if rows else 0.0)
        directness_reason = "Deterministic claims link directly to extracted source evidence." if claims_by_doc[document.id] else "No normalized claim is linked to this source yet."
        completeness = (sum(bool((item.original_text or "").strip()) for item in rows) / len(rows)) if rows else 0.0
        completeness_reason = f"{sum(bool((item.original_text or '').strip()) for item in rows)} of {len(rows)} evidence records contain original text."
        known_confidence = [item.extraction_confidence for item in rows if item.extraction_confidence is not None]
        extraction = sum(known_confidence) / len(known_confidence) if known_confidence else (0.5 if rows else 0.0)
        ocr_only = bool(rows) and all("ocr" in (item.extraction_method or "").casefold() for item in rows)
        if ocr_only:
            extraction = min(extraction, 0.65)
        extraction_reason = "OCR-derived extraction is present; verify critical values against the original." if ocr_only else "Based on recorded extraction confidence; missing confidence values are treated neutrally."
        corroborating_docs: set[str] = set()
        for claim in claims_by_doc[document.id]:
            if not (claim.project_identifier and claim.predicate and claim.object_value):
                continue
            key = (claim.project_identifier.casefold(), claim.predicate, claim.object_value)
            for other_id in claim_sources.get(key, set()):
                if other_id != document.id and fingerprints[other_id] != fingerprint:
                    corroborating_docs.add(other_id)
        corroboration = min(1.0, 0.5 + 0.2 * len(corroborating_docs)) if corroborating_docs else 0.5
        corroboration_reason = (f"{len(corroborating_docs)} distinct source fingerprint(s) repeat a normalized assertion; document independence is not verified." if corroborating_docs
                                else "No independent source repeats a normalized assertion; copies are not counted as corroboration.")
        criteria = {
            "authority": {"score": authority, "reason": authority_reason},
            "approval_status": {"score": {"approved": 0.95, "draft": 0.30, "historical": 0.40, "unverified": 0.55}[approval], "reason": approval_reason},
            "recency": {"score": 0.5, "reason": "Neutral: trusted source-publication date is not stored; upload time is not treated as publication time."},
            "directness": {"score": directness, "reason": directness_reason},
            "completeness": {"score": completeness, "reason": completeness_reason},
            "extraction_quality": {"score": extraction, "reason": extraction_reason},
            "independent_corroboration": {"score": corroboration, "reason": corroboration_reason},
        }
        score = round(sum(criteria[key]["score"] * weight for key, weight in weights.items()), 4)
        if ocr_only:
            source_type = "OCR_DERIVED"
        elif re.search(r"\b(cited|citation|reference|references|bibliography|secondary source)\b", content, re.I):
            source_type = "SECONDARY_REFERENCE"
        elif approval == "historical":
            source_type = "HISTORICAL_RECORD"
        elif authority > 0.5:
            source_type = "OFFICIAL_RECORD"
        else:
            source_type = "STRUCTURED_DATA" if document.extension in {".csv", ".xlsx"} else "DOCUMENT"
        explanations = [f"{key.replace('_', ' ').title()}: {criteria[key]['reason']}" for key in weights]
        if duplicate:
            explanations.append(f"Exact extracted-text duplicate of document {duplicate_of}; not counted as independent corroboration.")
        existing = session.scalar(select(SourceEvaluation).where(
            SourceEvaluation.document_id == document.id,
            SourceEvaluation.source_fingerprint == fingerprint,
        ))
        values = dict(source_type=source_type, approval_status=approval, duplicate_source=duplicate,
                      duplicate_of_document_id=duplicate_of if duplicate else None, heuristic_score=score,
                      criteria_json=json.dumps(criteria, ensure_ascii=False, sort_keys=True),
                      weights_json=json.dumps(weights, sort_keys=True), explanation=" ".join(explanations))
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            result.append(existing)
        else:
            item = SourceEvaluation(document_id=document.id, source_fingerprint=fingerprint, **values)
            session.add(item)
            result.append(item)
    session.flush()
    return result


def evaluate_sources(session: Session) -> list[SourceEvaluation]:
    return _evaluate_rows(session)


def evaluate_source(session: Session, document_id: str) -> SourceEvaluation | None:
    results = _evaluate_rows(session)
    return next((item for item in results if item.document_id == document_id), None)

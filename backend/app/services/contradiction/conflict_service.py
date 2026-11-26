"""Compare normalized assertions without deciding which source is correct."""

from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.source_evaluation import SourceEvaluation


def _family(claim: Claim) -> str | None:
    return {
        "monetary_amount": "money", "date": "date", "status_phrase": "status",
        "quantity": "quantity", "invoice_number": "invoice_number",
        "approval_reference": "approval_reference", "project_id": "project_id",
    }.get(claim.claim_type)


def _approval_state(text: str) -> str | None:
    lowered = text.casefold()
    if any(word in lowered for word in ("draft", "preliminary", "proposal")):
        return "draft"
    if any(word in lowered for word in ("approved", "signed", "final")):
        return "approved"
    return None


def _possible_duplicate(evidence_left: Evidence, evidence_right: Evidence) -> tuple[str, str] | None:
    left_text = re.sub(r"\s+", " ", evidence_left.original_text or "").strip().casefold()
    right_text = re.sub(r"\s+", " ", evidence_right.original_text or "").strip().casefold()
    if min(len(left_text), len(right_text)) < 64:
        return None
    similarity = SequenceMatcher(None, left_text[:6000], right_text[:6000], autojunk=False).ratio()
    if similarity < 0.96:
        return None
    return ("POSSIBLE_DUPLICATE",
            f"The source passages are highly similar ({similarity:.0%}) and assert the same normalized value; they may be copied records or independent corroboration. Review both sources. This is not a contradiction.")


def _classify(left: Claim, right: Claim, evidence_left: Evidence, evidence_right: Evidence) -> tuple[str, str] | None:
    family_left, family_right = _family(left), _family(right)
    if not family_left or family_left != family_right:
        return None
    if family_left == "money" and left.category != right.category:
        return "CATEGORY_MISMATCH", "The values describe different financial categories; they are not directly comparable as a contradiction."
    if family_left == "money" and left.currency and right.currency and left.currency != right.currency:
        return "UNIT_MISMATCH", f"Currencies differ ({left.currency} versus {right.currency}); no exchange-rate conversion was applied."
    if family_left == "quantity" and left.unit and right.unit and left.unit != right.unit:
        return "UNIT_MISMATCH", f"Measurement units differ ({left.unit} versus {right.unit}); no unit conversion was applied."
    if left.predicate != right.predicate:
        return None

    value_left = left.object_value or left.normalized_value
    value_right = right.object_value or right.normalized_value
    if value_left == value_right:
        return None if family_left == "project_id" else _possible_duplicate(evidence_left, evidence_right)
    if family_left == "status":
        if left.claim_date and right.claim_date and left.claim_date != right.claim_date:
            return "TEMPORAL_DIFFERENCE", "Different statuses are attached to different dates and may represent a legitimate change over time."
        return "POTENTIAL_CONFLICT", "Status assertions differ, but the source records do not establish whether they refer to the same point in time."
    if family_left == "date":
        return "POTENTIAL_CONFLICT", "Dates for the same normalized field differ; confirm that both refer to the same event and time period."

    text_left = " ".join(filter(None, (left.context, evidence_left.context_text, evidence_left.original_text)))
    text_right = " ".join(filter(None, (right.context, evidence_right.context_text, evidence_right.original_text)))
    if _approval_state(text_left) != _approval_state(text_right) and { _approval_state(text_left), _approval_state(text_right) } & {"draft", "approved"}:
        return "POTENTIAL_CONFLICT", "The records have different draft/approval states; assertions are retained for review without selecting a winner."
    if family_left in {"money", "quantity"} and (left.time_period or right.time_period) and left.time_period != right.time_period:
        return "TEMPORAL_DIFFERENCE", "The values refer to different or incomplete time periods and need human context review."
    if family_left == "money" and left.currency != right.currency:
        return "UNRESOLVED", "One or both monetary assertions have no explicit currency, so comparability is uncertain."
    if family_left in {"money", "quantity"} and left.unit != right.unit:
        return "UNIT_MISMATCH", "The numeric values have different or missing units; no conversion was assumed."
    if family_left in {"money", "quantity"}:
        return "CONFIRMED_CONFLICT", "The sources assert different values for the same normalized field, entity, category and available time context. This confirms disagreement between assertions, not which value is true."
    return "POTENTIAL_CONFLICT", "The sources assert different values for the same normalized field; additional context is needed to establish whether they conflict."


def _location(evidence: Evidence) -> str:
    parts = []
    if evidence.page_number is not None:
        parts.append(f"page {evidence.page_number}")
    if evidence.sheet_name:
        parts.append(f"sheet {evidence.sheet_name}")
    if evidence.row_number is not None:
        parts.append(f"row {evidence.row_number}")
    if evidence.cell_coordinate:
        parts.append(f"cell {evidence.cell_coordinate}")
    return ", ".join(parts) or "source location unavailable"


def detect_conflicts(session: Session, changed_claim_ids: list[int] | None = None,
                     document_ids: list[str] | None = None) -> int:
    """Compare claims with a known shared project; optionally restrict both sides to a document scope."""
    statement = select(Claim, Evidence, Document).join(Evidence, Evidence.id == Claim.evidence_id).join(Document, Document.id == Evidence.document_id)
    statement = statement.where(Claim.normalization_method == "phase5-deterministic-v1")
    if document_ids is not None:
        statement = statement.where(Document.id.in_(document_ids))
    rows = session.execute(statement.order_by(Claim.id)).all()
    groups: dict[tuple[str, str], list[tuple[Claim, Evidence, Document]]] = {}
    for claim, evidence, document in rows:
        family = _family(claim)
        if claim.project_identifier and family:
            groups.setdefault((claim.project_identifier.casefold(), family), []).append((claim, evidence, document))

    focus = set(changed_claim_ids) if changed_claim_ids is not None else {claim.id for claim, _, _ in rows}
    if not focus:
        return 0
    duplicate_docs = set(session.scalars(select(SourceEvaluation.document_id).where(SourceEvaluation.duplicate_source.is_(True))).all())
    existing_pairs = {
        (min(left, right), max(left, right))
        for left, right in session.execute(select(Contradiction.claim_a_id, Contradiction.claim_b_id).where(
            Contradiction.claim_a_id.is_not(None), Contradiction.claim_b_id.is_not(None)
        )).all()
    }
    created = 0
    examined: set[tuple[int, int]] = set()
    duplicate_evidence_pairs: set[tuple[int, int]] = set()
    for group in groups.values():
        focused = [record for record in group if record[0].id in focus]
        for first in focused:
            for second in group:
                claim_a, evidence_a, document_a = first
                claim_b, evidence_b, document_b = second
                if claim_a.id == claim_b.id or evidence_a.document_id == evidence_b.document_id:
                    continue
                pair = tuple(sorted((claim_a.id, claim_b.id)))
                if pair in examined or pair in existing_pairs:
                    continue
                examined.add(pair)
                result = _classify(claim_a, claim_b, evidence_a, evidence_b)
                if result is None:
                    continue
                classification, explanation = result
                if document_a.id in duplicate_docs and document_b.id in duplicate_docs and document_a.sha256 == document_b.sha256:
                    continue
                if classification == "POSSIBLE_DUPLICATE":
                    source_pair = tuple(sorted((evidence_a.id, evidence_b.id)))
                    if source_pair in duplicate_evidence_pairs:
                        continue
                    duplicate_evidence_pairs.add(source_pair)
                left, right = (first, second) if claim_a.id < claim_b.id else (second, first)
                a_claim, a_evidence, _ = left
                b_claim, b_evidence, _ = right
                explanation += f" Source A: {_location(a_evidence)}. Source B: {_location(b_evidence)}. No source is automatically preferred."
                session.add(Contradiction(
                    evidence_a_id=a_evidence.id, evidence_b_id=b_evidence.id,
                    claim_a_id=a_claim.id, claim_b_id=b_claim.id,
                    classification=classification, conflict_category=_family(a_claim),
                    severity=classification.casefold(), status="open", explanation=explanation,
                    confidence=0.78 if classification == "CONFIRMED_CONFLICT" else 0.62,
                    detection_method="deterministic-field-comparison",
                    original_value_a=a_claim.value, original_value_b=b_claim.value,
                    normalized_value_a=a_claim.object_value, normalized_value_b=b_claim.object_value,
                    source_location_a=a_claim.source_location, source_location_b=b_claim.source_location,
                ))
                created += 1
    session.flush()
    return created

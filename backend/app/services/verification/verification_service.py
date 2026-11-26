"""Combine local retrieval, source-linked claims, conflict findings and graph context."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.claim import Claim
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.knowledge_graph import KnowledgeGraphEdge, KnowledgeGraphNode
from app.models.source_evaluation import SourceEvaluation
from app.services.knowledge_graph.graph_service import build_graph
from app.services.reliability.source_reliability import evaluate_sources
from app.services.retrieval.retrieval_service import retrieve
from app.services.verification.serialization import claim_read, conflict_read, edge_read, source_read


def run_verification(session: Session, settings: Settings, client, question: str,
                     document_ids: list[str] | None, top_k: int) -> dict:
    result = retrieve(session, client, settings, question, top_k=max(1, min(top_k, 30)),
                      document_ids=document_ids)
    diagnostics = list(result.diagnostics)
    methods = {result.method}
    results = result.items[:top_k]
    evidence_ids = {item.evidence.id for item in results}
    document_map = {item.id: item for item in session.scalars(select(Document)).all()}
    claim_rows = session.execute(select(Claim, Evidence).join(Evidence, Evidence.id == Claim.evidence_id)
                                 .where(Claim.evidence_id.in_(evidence_ids))
                                 .order_by(Claim.id)).all() if evidence_ids else []
    claim_data = [claim_read(claim, evidence, document_map[evidence.document_id])
                  for claim, evidence in claim_rows if evidence.document_id in document_map]
    claim_ids = {claim.id for claim, _ in claim_rows}
    conflict_statement = select(Contradiction).where(or_(
        Contradiction.evidence_a_id.in_(evidence_ids), Contradiction.evidence_b_id.in_(evidence_ids),
        Contradiction.claim_a_id.in_(claim_ids), Contradiction.claim_b_id.in_(claim_ids),
    )) if evidence_ids or claim_ids else select(Contradiction).where(False)
    conflicts = session.scalars(conflict_statement.order_by(Contradiction.id)).all()
    conflicts_data = []
    for conflict in conflicts:
        pair_data = []
        for claim_id in (conflict.claim_a_id, conflict.claim_b_id):
            claim = session.get(Claim, claim_id) if claim_id else None
            evidence = session.get(Evidence, claim.evidence_id) if claim else None
            if claim and evidence and evidence.document_id in document_map:
                pair_data.append(claim_read(claim, evidence, document_map[evidence.document_id]))
            else:
                pair_data.append(None)
        if document_ids is not None and not all(
            claim is not None and claim["document_id"] in document_ids for claim in pair_data
        ):
            continue
        conflicts_data.append(conflict_read(conflict, pair_data[0], pair_data[1]))
    blocking_classes = {"CONFIRMED_CONFLICT", "POTENTIAL_CONFLICT", "TEMPORAL_DIFFERENCE", "UNIT_MISMATCH", "UNRESOLVED"}
    contradictory_data = [item for item in conflicts_data if item["classification"] in blocking_classes]

    all_evaluations = evaluate_sources(session)
    wanted_doc_ids = {item.document.id for item in results}
    for conflict in conflicts:
        for evidence_id in (conflict.evidence_a_id, conflict.evidence_b_id):
            evidence = session.get(Evidence, evidence_id)
            if evidence:
                wanted_doc_ids.add(evidence.document_id)
    evaluation_by_doc = {item.document_id: item for item in all_evaluations if item.document_id in wanted_doc_ids}
    reliability_data = [source_read(evaluation, document_map[doc_id]) for doc_id, evaluation in evaluation_by_doc.items()
                        if doc_id in document_map]

    build_graph(session)
    relevant_edges = []
    if evidence_ids:
        relevant_edges = session.scalars(select(KnowledgeGraphEdge).where(KnowledgeGraphEdge.evidence_id.in_(evidence_ids))
                                         .order_by(KnowledgeGraphEdge.id).limit(200)).all()
    relationships_data = [edge_read(item) for item in relevant_edges]
    evidence_data = [{
        "evidence_id": item.evidence.id, "document_id": item.document.id,
        "filename": item.evidence.filename or item.document.original_filename,
        "text": item.evidence.original_text, "context_text": item.evidence.context_text,
        "page_number": item.evidence.page_number, "sheet_name": item.evidence.sheet_name,
        "row_number": item.evidence.row_number, "column_name": item.evidence.column_name,
        "cell_coordinate": item.evidence.cell_coordinate,
        "extraction_method": item.evidence.extraction_method,
        "extraction_confidence": item.evidence.extraction_confidence,
        "retrieval_score": round(item.score, 4), "retrieval_method": item.retrieval_method,
    } for item in results]

    uncertainty = []
    if not results:
        uncertainty.append("No stored source evidence matched this question.")
    if not claim_data and results:
        uncertainty.append("Relevant text was retrieved, but no deterministic claim was linked to that evidence.")
    if contradictory_data:
        uncertainty.append("Retrieved claims have an unresolved disagreement; no source was selected as correct.")
    elif any(item["classification"] == "CATEGORY_MISMATCH" for item in conflicts_data):
        uncertainty.append("Some retrieved values describe different categories and should not be compared as one value.")
    if any(item.get("duplicate_source") for item in reliability_data):
        uncertainty.append("At least one retrieved source is an exact text duplicate and does not count as independent corroboration.")
    if results and results[0].score < settings.retrieval_min_score:
        uncertainty.append("Retrieval score is below the configured heuristic threshold.")
    abstained = (not results or not claim_data or bool(contradictory_data)
                 or results[0].score < settings.retrieval_min_score)
    distinct_claims = []
    seen_values = set()
    for item in claim_data:
        key = (item["predicate"], item["object_value"], item["currency"], item["unit"])
        if key not in seen_values:
            seen_values.add(key)
            distinct_claims.append(item)
    if abstained:
        answer = "Insufficient or conflicting evidence; review the cited source records before reaching a conclusion."
    elif distinct_claims:
        answer = "Retrieved evidence states: " + "; ".join(
            f"{item['predicate'] or item['claim_type']} = {item['value']}" for item in distinct_claims[:5]
        ) + "."
    else:
        answer = "Relevant evidence was retrieved, but no normalized claim directly answers this question."
        abstained = True
        uncertainty.append("No supported normalized claim is available for a direct answer.")
    if not conflicts_data and claim_data:
        conflict_assessment = "NO_CONFLICT"
    elif not conflicts_data:
        conflict_assessment = "UNRESOLVED"
    else:
        priority = ("CONFIRMED_CONFLICT", "POTENTIAL_CONFLICT", "UNRESOLVED", "UNIT_MISMATCH", "TEMPORAL_DIFFERENCE", "CATEGORY_MISMATCH", "POSSIBLE_DUPLICATE", "NO_CONFLICT")
        conflict_assessment = next((label for label in priority if any(item["classification"] == label for item in conflicts_data)), "UNRESOLVED")
    limitations = ["Verification uses deterministic normalization and field comparison; it does not determine which conflicting source is true.",
                   "Retrieval scores and source evaluations are heuristics, not calibrated probabilities."]
    if diagnostics:
        limitations.append("Some retrieval diagnostics indicate that semantic search was unavailable or degraded.")
    return {
        "question": question, "answer": answer, "evidence": evidence_data,
        "relevant_claims": claim_data, "contradictory_evidence": contradictory_data,
        "comparison_findings": conflicts_data, "conflict_assessment": conflict_assessment,
        "source_reliability": reliability_data, "relevant_relationships": relationships_data,
        "uncertainty": uncertainty, "limitations": limitations, "abstained": abstained,
        "confidence": "limited" if abstained else "evidence-linked; heuristic retrieval",
        "retrieval_method": "+".join(sorted(methods)) if methods else "none",
        "diagnostics": list(dict.fromkeys(diagnostics)),
    }

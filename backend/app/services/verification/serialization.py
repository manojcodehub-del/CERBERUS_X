"""Small response serializers that expose provenance, not private storage paths."""

import json

from app.models.claim import Claim
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.knowledge_graph import KnowledgeGraphEdge, KnowledgeGraphNode
from app.models.source_evaluation import SourceEvaluation


def claim_read(claim: Claim, evidence: Evidence, document: Document) -> dict:
    try:
        location = json.loads(claim.source_location or "{}")
    except json.JSONDecodeError:
        location = {}
    return {
        "id": claim.id, "evidence_id": evidence.id, "document_id": document.id,
        "filename": evidence.filename or document.original_filename,
        "claim_type": claim.claim_type, "value": claim.value,
        "normalized_value": claim.normalized_value, "subject": claim.subject,
        "predicate": claim.predicate, "object_value": claim.object_value,
        "entity": claim.entity, "category": claim.category, "unit": claim.unit,
        "currency": claim.currency, "claim_date": claim.claim_date,
        "time_period": claim.time_period, "project_identifier": claim.project_identifier,
        "document_identifier": claim.document_identifier, "source_location": location,
        "extraction_confidence": evidence.extraction_confidence,
        "normalization_method": claim.normalization_method,
    }


def conflict_read(conflict: Contradiction, claim_a_data: dict | None, claim_b_data: dict | None) -> dict:
    return {
        "id": conflict.id, "classification": conflict.classification,
        "conflict_category": conflict.conflict_category, "status": conflict.status,
        "explanation": conflict.explanation, "confidence": conflict.confidence,
        "confidence_note": "Rule-based comparison heuristic; not a calibrated probability.",
        "detection_method": conflict.detection_method, "claim_a": claim_a_data,
        "claim_b": claim_b_data, "evidence_a_id": conflict.evidence_a_id,
        "evidence_b_id": conflict.evidence_b_id, "created_at": conflict.created_at.isoformat(),
        "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
    }


def source_read(evaluation: SourceEvaluation, document: Document) -> dict:
    try:
        criteria = json.loads(evaluation.criteria_json)
        weights = json.loads(evaluation.weights_json)
    except json.JSONDecodeError:
        criteria, weights = {}, {}
    return {
        "document_id": document.id, "filename": document.original_filename,
        "source_type": evaluation.source_type, "approval_status": evaluation.approval_status,
        "duplicate_source": evaluation.duplicate_source,
        "duplicate_of_document_id": evaluation.duplicate_of_document_id,
        "heuristic_score": evaluation.heuristic_score, "criteria": criteria,
        "weights": weights, "explanation": evaluation.explanation,
        "evaluated_at": evaluation.evaluated_at.isoformat(),
    }


def node_read(node: KnowledgeGraphNode) -> dict:
    try:
        metadata = json.loads(node.metadata_json or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {"id": node.id, "key": node.node_key, "type": node.node_type,
            "label": node.label, "document_id": node.document_id,
            "claim_id": node.claim_id, "evidence_id": node.evidence_id,
            "conflict_id": node.conflict_id, "entity_type": node.entity_type,
            "metadata": metadata}


def edge_read(edge: KnowledgeGraphEdge) -> dict:
    return {"id": edge.id, "source": edge.source_node_id,
            "target": edge.target_node_id, "relationship": edge.relationship_type,
            "evidence_id": edge.evidence_id, "explanation": edge.explanation}

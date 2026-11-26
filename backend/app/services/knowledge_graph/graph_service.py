"""Build stable graph records incrementally from persisted evidence and claims."""

import json

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.knowledge_graph import KnowledgeGraphEdge, KnowledgeGraphNode


def _node(session: Session, graph: nx.MultiDiGraph, node_map: dict[str, KnowledgeGraphNode], *,
          key: str, node_type: str, label: str, document_id: str | None = None,
          claim_id: int | None = None, evidence_id: int | None = None,
          conflict_id: int | None = None, entity_type: str | None = None,
          metadata: dict | None = None) -> KnowledgeGraphNode:
    attrs = metadata or {}
    graph.add_node(key, type=node_type, label=label, **attrs)
    node = node_map.get(key) or session.scalar(select(KnowledgeGraphNode).where(KnowledgeGraphNode.node_key == key))
    if node is None:
        node = KnowledgeGraphNode(node_key=key, node_type=node_type, label=label,
                                  document_id=document_id, claim_id=claim_id,
                                  evidence_id=evidence_id, conflict_id=conflict_id,
                                  entity_type=entity_type,
                                  normalized_name=label.casefold() if node_type in {"project", "person", "organization"} else None,
                                  metadata_json=json.dumps(attrs, ensure_ascii=False, sort_keys=True))
        session.add(node)
        session.flush()
    else:
        node.node_type = node_type
        node.label = label
        node.document_id = document_id
        node.claim_id = claim_id
        node.evidence_id = evidence_id
        node.conflict_id = conflict_id
        node.entity_type = entity_type
        node.normalized_name = label.casefold() if node_type in {"project", "person", "organization"} else None
        node.metadata_json = json.dumps(attrs, ensure_ascii=False, sort_keys=True)
    node_map[key] = node
    return node


def _edge(session: Session, graph: nx.MultiDiGraph, source: KnowledgeGraphNode,
          target: KnowledgeGraphNode, relationship: str, evidence_id: int,
          explanation: str) -> None:
    key = f"{source.node_key}|{relationship}|{target.node_key}|evidence:{evidence_id}"
    graph.add_edge(source.node_key, target.node_key, key=key, relationship=relationship, evidence_id=evidence_id)
    edge = session.scalar(select(KnowledgeGraphEdge).where(KnowledgeGraphEdge.edge_key == key))
    if edge is None:
        session.add(KnowledgeGraphEdge(edge_key=key, source_node_id=source.id,
                                       target_node_id=target.id, relationship_type=relationship,
                                       evidence_id=evidence_id, explanation=explanation))
    else:
        edge.explanation = explanation


def build_graph(session: Session) -> nx.MultiDiGraph:
    """Upsert a traceable graph. Every edge carries a real evidence foreign key."""
    graph = nx.MultiDiGraph()
    node_map: dict[str, KnowledgeGraphNode] = {}
    docs = {item.id: item for item in session.scalars(select(Document)).all()}
    evidence_rows = session.scalars(select(Evidence).order_by(Evidence.id)).all()
    evidence_by_id = {item.id: item for item in evidence_rows}
    evidence_nodes: dict[int, KnowledgeGraphNode] = {}
    for evidence in evidence_rows:
        doc = docs.get(evidence.document_id)
        if not doc:
            continue
        doc_node = _node(session, graph, node_map, key=f"document:{doc.id}", node_type="document",
                         label=doc.original_filename, document_id=doc.id,
                         metadata={"extension": doc.extension, "processing_status": doc.processing_status})
        ev_node = _node(session, graph, node_map, key=f"evidence:{evidence.id}", node_type="evidence",
                         label=(evidence.original_text or "Evidence")[:120], document_id=doc.id,
                         evidence_id=evidence.id,
                         metadata={"filename": evidence.filename or doc.original_filename,
                                   "page_number": evidence.page_number, "sheet_name": evidence.sheet_name,
                                   "row_number": evidence.row_number, "column_name": evidence.column_name,
                                   "cell_coordinate": evidence.cell_coordinate,
                                   "paragraph_index": evidence.paragraph_index, "table_index": evidence.table_index,
                                   "source_location": {"page_number": evidence.page_number,
                                                       "sheet_name": evidence.sheet_name,
                                                       "row_number": evidence.row_number,
                                                       "column_name": evidence.column_name,
                                                       "cell_coordinate": evidence.cell_coordinate,
                                                       "paragraph_index": evidence.paragraph_index,
                                                       "table_index": evidence.table_index},
                                   "extraction_method": evidence.extraction_method})
        evidence_nodes[evidence.id] = ev_node
        _edge(session, graph, doc_node, ev_node, "DOCUMENT_CONTAINS_EVIDENCE", evidence.id,
              "Evidence was extracted from this document record.")

    claims = session.scalars(select(Claim).where(Claim.normalization_method == "phase5-deterministic-v1").order_by(Claim.id)).all()
    claim_nodes: dict[int, KnowledgeGraphNode] = {}
    for claim in claims:
        evidence = evidence_by_id.get(claim.evidence_id)
        if evidence is None or claim.evidence_id not in evidence_nodes:
            continue
        doc = docs[evidence.document_id]
        claim_node = _node(session, graph, node_map, key=f"claim:{claim.id}", node_type="claim",
                           label=f"{claim.predicate or claim.claim_type}: {claim.value}"[:512],
                           document_id=doc.id, claim_id=claim.id,
                           metadata={"predicate": claim.predicate, "category": claim.category,
                                     "normalized_value": claim.object_value, "currency": claim.currency,
                                     "unit": claim.unit, "project_identifier": claim.project_identifier,
                                     "source_location": json.loads(claim.source_location or "{}")})
        claim_nodes[claim.id] = claim_node
        evidence_node = evidence_nodes[claim.evidence_id]
        _edge(session, graph, doc_node := node_map[f"document:{doc.id}"], claim_node,
              "DOCUMENT_CONTAINS_CLAIM", evidence.id, "The claim was extracted from evidence in this document.")
        _edge(session, graph, claim_node, evidence_node, "CLAIM_SUPPORTED_BY_EVIDENCE", evidence.id,
              "The claim retains a direct foreign-key link to original extracted text.")
        if claim.claim_date:
            event_key = f"event:{(claim.project_identifier or doc.id).casefold()}:{(claim.predicate or claim.claim_type).casefold()}:{claim.claim_date}"
            event = _node(session, graph, node_map, key=event_key, node_type="event",
                           label=f"{claim.predicate or claim.claim_type} on {claim.claim_date}"[:512],
                           document_id=doc.id, claim_id=claim.id, evidence_id=evidence.id,
                           entity_type="dated_assertion",
                           metadata={"date": claim.claim_date, "predicate": claim.predicate,
                                     "project_identifier": claim.project_identifier,
                                     "source_location": json.loads(claim.source_location or "{}")})
            _edge(session, graph, claim_node, event, "CLAIM_REFERENCES_EVENT", evidence.id,
                  "This dated event marker is derived from the claim and linked to its original evidence.")
            _edge(session, graph, event, evidence_nodes[evidence.id], "EVENT_DERIVED_FROM_EVIDENCE", evidence.id,
                  "The event date and claim come from this source evidence.")
        if claim.project_identifier:
            project = _node(session, graph, node_map, key=f"project:{claim.project_identifier.casefold()}",
                            node_type="project", label=claim.project_identifier,
                            entity_type="project_identifier", metadata={"normalized_name": claim.project_identifier.casefold()})
            _edge(session, graph, claim_node, project, "CLAIM_REFERENCES_ENTITY", evidence.id,
                  "The project identifier is present in the same source evidence.")
            _edge(session, graph, project, doc_node, "ENTITY_BELONGS_TO_PROJECT", evidence.id,
                  "This document contains evidence mentioning the project identifier.")
        if claim.claim_type == "named_entity_candidate" and claim.value.strip():
            entity_type = "organization" if any(token in (claim.context or "").casefold() for token in ("company", "organization", "vendor", "agency")) else "person"
            entity = _node(session, graph, node_map, key=f"{entity_type}:{claim.value.casefold()}",
                           node_type=entity_type, label=claim.value, entity_type=entity_type)
            _edge(session, graph, claim_node, entity, "CLAIM_REFERENCES_ENTITY", evidence.id,
                  "The named entity was detected in the claim's source context.")

    conflicts = session.scalars(select(Contradiction).where(Contradiction.claim_a_id.is_not(None), Contradiction.claim_b_id.is_not(None))).all()
    for conflict in conflicts:
        claim_a = claim_nodes.get(conflict.claim_a_id)
        claim_b = claim_nodes.get(conflict.claim_b_id)
        if not claim_a or not claim_b:
            continue
        conflict_node = _node(session, graph, node_map, key=f"conflict:{conflict.id}", node_type="conflict",
                              label=f"{conflict.classification.replace('_', ' ').title()} #{conflict.id}",
                              conflict_id=conflict.id,
                              metadata={"classification": conflict.classification, "status": conflict.status})
        for claim_node, evidence_id in ((claim_a, conflict.evidence_a_id), (claim_b, conflict.evidence_b_id)):
            _edge(session, graph, claim_node, conflict_node, "CLAIM_CONTRADICTS_CLAIM", evidence_id,
                  conflict.explanation or "This conflict finding preserves both source assertions for review.")
        relationship = "CLAIM_MAY_DUPLICATE" if conflict.classification == "POSSIBLE_DUPLICATE" else "CLAIM_CONTRADICTS_CLAIM"
        _edge(session, graph, claim_a, claim_b, relationship, conflict.evidence_a_id,
              conflict.explanation or "Potential disagreement; neither assertion is automatically selected.")

    session.flush()
    return graph


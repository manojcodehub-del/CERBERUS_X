"""Persistent NetworkX graph read APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.knowledge_graph import KnowledgeGraphEdge, KnowledgeGraphNode
from app.schemas.verification import GraphEdgeRead, GraphNodeRead, KnowledgeGraphRead
from app.services.knowledge_graph.graph_service import build_graph
from app.services.verification.serialization import edge_read, node_read

router = APIRouter(tags=["knowledge graph"])


@router.get("/knowledge-graph", response_model=KnowledgeGraphRead)
def read_graph(limit: int = Query(default=500, ge=1, le=2000),
               session: Session = Depends(get_database_session)) -> KnowledgeGraphRead:
    build_graph(session)
    nodes = session.scalars(select(KnowledgeGraphNode).order_by(KnowledgeGraphNode.id).limit(limit)).all()
    node_ids = [node.id for node in nodes]
    edges = session.scalars(select(KnowledgeGraphEdge).where(
        KnowledgeGraphEdge.source_node_id.in_(node_ids), KnowledgeGraphEdge.target_node_id.in_(node_ids)
    ).order_by(KnowledgeGraphEdge.id).limit(limit * 4)).all() if node_ids else []
    session.commit()
    return KnowledgeGraphRead(nodes=[node_read(node) for node in nodes], edges=[edge_read(edge) for edge in edges],
                              node_count=len(nodes), edge_count=len(edges))


@router.get("/knowledge-graph/entities/{entity_id}", response_model=KnowledgeGraphRead)
def read_graph_entity(entity_id: int, session: Session = Depends(get_database_session)) -> KnowledgeGraphRead:
    if entity_id < 1:
        raise HTTPException(status_code=422, detail={"code": "invalid_entity_id", "message": "Entity ID must be positive."})
    build_graph(session)
    node = session.get(KnowledgeGraphNode, entity_id)
    if node is None:
        raise HTTPException(status_code=404, detail={"code": "entity_not_found", "message": "Graph entity not found."})
    edges = session.scalars(select(KnowledgeGraphEdge).where(
        (KnowledgeGraphEdge.source_node_id == node.id) | (KnowledgeGraphEdge.target_node_id == node.id)
    ).order_by(KnowledgeGraphEdge.id).limit(200)).all()
    node_ids = {node.id}
    for edge in edges:
        node_ids.update((edge.source_node_id, edge.target_node_id))
    nodes = session.scalars(select(KnowledgeGraphNode).where(KnowledgeGraphNode.id.in_(node_ids)).order_by(KnowledgeGraphNode.id)).all()
    session.commit()
    return KnowledgeGraphRead(nodes=[node_read(item) for item in nodes], edges=[edge_read(edge) for edge in edges],
                              node_count=len(nodes), edge_count=len(edges))

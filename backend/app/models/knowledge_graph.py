"""Persistent, deduplicated nodes and evidence-backed edges for graph views."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.document import utc_now


class KnowledgeGraphNode(Base):
    __tablename__ = "knowledge_graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    conflict_id: Mapped[int | None] = mapped_column(ForeignKey("contradictions.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    normalized_name: Mapped[str | None] = mapped_column(String(512), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeGraphEdge(Base):
    __tablename__ = "knowledge_graph_edges"
    __table_args__ = (UniqueConstraint("edge_key", name="uq_knowledge_graph_edge_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edge_key: Mapped[str] = mapped_column(String(768), nullable=False, index=True)
    source_node_id: Mapped[int] = mapped_column(ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id: Mapped[int] = mapped_column(ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

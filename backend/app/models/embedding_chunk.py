"""Search chunks linked to authoritative source evidence and cached vectors."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.document import utc_now


class EmbeddingChunk(Base):
    __tablename__ = "embedding_chunks"
    __table_args__ = (
        UniqueConstraint("evidence_id", "model_name", "chunk_index", name="uq_embedding_chunk_source_order"),
        Index("ix_embedding_chunks_document_model", "document_id", "model_name"),
        Index("ix_embedding_chunks_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding_id: Mapped[int] = mapped_column(ForeignKey("embedding_cache.id", ondelete="RESTRICT"), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    evidence: Mapped["Evidence"] = relationship(back_populates="embedding_chunks")
    embedding: Mapped["EmbeddingCache"] = relationship(back_populates="chunks")

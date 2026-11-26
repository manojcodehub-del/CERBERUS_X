"""Extracted evidence records with source provenance."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.document import utc_now


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_document_created", "document_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer)
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    row_number: Mapped[int | None] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(64))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    cell_coordinate: Mapped[str | None] = mapped_column(String(32))
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    table_index: Mapped[int | None] = mapped_column(Integer)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    evidence_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    context_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    document: Mapped["Document"] = relationship(back_populates="evidence")
    citations: Mapped[list["AnswerCitation"]] = relationship(back_populates="evidence", passive_deletes=True)
    claims: Mapped[list["Claim"]] = relationship(back_populates="evidence", cascade="all, delete-orphan")
    embedding_chunks: Mapped[list["EmbeddingChunk"]] = relationship(back_populates="evidence", cascade="all, delete-orphan")

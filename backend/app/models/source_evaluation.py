"""Explainable, explicitly heuristic source evaluation records."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.document import utc_now


class SourceEvaluation(Base):
    __tablename__ = "source_evaluations"
    __table_args__ = (UniqueConstraint("document_id", "source_fingerprint", name="uq_source_evaluation_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    duplicate_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    heuristic_score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_json: Mapped[str] = mapped_column(Text, nullable=False)
    weights_json: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

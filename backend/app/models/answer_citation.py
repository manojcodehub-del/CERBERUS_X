"""Provenance links from future answers back to source evidence."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.document import utc_now


class AnswerCitation(Base):
    __tablename__ = "answer_citations"
    __table_args__ = (UniqueConstraint("question_id", "citation_order", name="uq_question_citation_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    citation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    question: Mapped["Question"] = relationship(back_populates="citations")
    evidence: Mapped["Evidence"] = relationship(back_populates="citations")

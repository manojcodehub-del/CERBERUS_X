"""Potential conflicts between claims, kept for later verification phases."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.document import utc_now


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_a_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_b_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(24), nullable=False, default="unreviewed")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", index=True)
    explanation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    claim_a_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"), index=True)
    claim_b_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"), index=True)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="POTENTIAL_CONFLICT", index=True)
    conflict_category: Mapped[str | None] = mapped_column(String(64), index=True)
    detection_method: Mapped[str | None] = mapped_column(String(64))
    original_value_a: Mapped[str | None] = mapped_column(Text)
    original_value_b: Mapped[str | None] = mapped_column(Text)
    normalized_value_a: Mapped[str | None] = mapped_column(Text)
    normalized_value_b: Mapped[str | None] = mapped_column(Text)
    source_location_a: Mapped[str | None] = mapped_column(Text)
    source_location_b: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    evidence_a: Mapped["Evidence"] = relationship(foreign_keys=[evidence_a_id])
    evidence_b: Mapped["Evidence"] = relationship(foreign_keys=[evidence_b_id])
    claim_a: Mapped["Claim | None"] = relationship(foreign_keys=[claim_a_id])
    claim_b: Mapped["Claim | None"] = relationship(foreign_keys=[claim_b_id])

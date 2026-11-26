"""Deterministic candidate claims linked to source evidence."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.document import utc_now


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("evidence_id", "claim_type", "normalized_value", name="uq_claim_evidence_type_value"),
        Index("ix_claims_type_value", "claim_type", "normalized_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(512), nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    # Phase 5 normalized fields are additive; value/context remain the original Phase 3 data.
    subject: Mapped[str | None] = mapped_column(String(512))
    predicate: Mapped[str | None] = mapped_column(String(256), index=True)
    object_value: Mapped[str | None] = mapped_column(String(512))
    entity: Mapped[str | None] = mapped_column(String(512), index=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    unit: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(12))
    claim_date: Mapped[str | None] = mapped_column(String(32))
    time_period: Mapped[str | None] = mapped_column(String(128))
    project_identifier: Mapped[str | None] = mapped_column(String(128), index=True)
    document_identifier: Mapped[str | None] = mapped_column(String(36))
    source_location: Mapped[str | None] = mapped_column(Text)
    normalization_method: Mapped[str | None] = mapped_column(String(64))
    normalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    evidence: Mapped["Evidence"] = relationship(back_populates="claims")

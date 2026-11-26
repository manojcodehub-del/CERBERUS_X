"""People, organizations, and other entities linked to source documents."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.document import utc_now


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (Index("ix_entities_type_name", "entity_type", "normalized_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    document: Mapped["Document"] = relationship(back_populates="entities")
    outgoing_relationships: Mapped[list["Relationship"]] = relationship(
        foreign_keys="Relationship.source_entity_id", back_populates="source_entity", passive_deletes=True
    )
    incoming_relationships: Mapped[list["Relationship"]] = relationship(
        foreign_keys="Relationship.target_entity_id", back_populates="target_entity", passive_deletes=True
    )

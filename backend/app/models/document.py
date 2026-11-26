"""Uploaded document metadata."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    extension: Mapped[str] = mapped_column(String(12), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(24), nullable=False, default="uploaded", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="document", passive_deletes=True)
    entities: Mapped[list["Entity"]] = relationship(back_populates="document", passive_deletes=True)
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="document", passive_deletes=True)

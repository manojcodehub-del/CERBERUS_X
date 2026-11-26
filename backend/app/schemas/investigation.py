"""Validated API contracts for persisted investigations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[str] | None = Field(default=None, max_length=50)
    top_k: int = Field(default=12, ge=1, le=20)

    @field_validator("title", "question")
    @classmethod
    def trim_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned

    @model_validator(mode="after")
    def validate_scope(self):
        if self.document_ids is not None:
            if not self.document_ids:
                raise ValueError("Use null for the whole collection; an explicit document scope must not be empty.")
            if len(set(self.document_ids)) != len(self.document_ids):
                raise ValueError("Document IDs must not contain duplicates.")
            if any(not item.strip() or len(item) > 36 for item in self.document_ids):
                raise ValueError("Document IDs must be non-empty IDs no longer than 36 characters.")
        return self


class InvestigationGenerateRequest(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=20)


class InvestigationListItem(BaseModel):
    id: int
    title: str
    question: str
    status: Literal["draft", "ready"]
    document_ids: list[str] | None
    top_k: int
    created_at: datetime
    updated_at: datetime


class InvestigationRead(InvestigationListItem):
    report: dict | None


class InvestigationList(BaseModel):
    items: list[InvestigationListItem]
    total: int

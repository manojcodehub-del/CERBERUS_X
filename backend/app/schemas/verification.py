"""Contracts for deterministic claim, conflict, reliability and verification APIs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClaimNormalizeRequest(BaseModel):
    claim_ids: list[int] | None = Field(default=None, max_length=1000)
    document_ids: list[str] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def positive_claim_ids(self):
        if self.claim_ids is not None and any(item < 1 for item in self.claim_ids):
            raise ValueError("Claim IDs must be positive integers.")
        return self


class ConflictResolutionRequest(BaseModel):
    status: Literal["open", "under_review", "resolved", "dismissed"]
    note: str | None = Field(default=None, max_length=2000)


class VerificationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[str] | None = Field(default=None, max_length=100)
    top_k: int = Field(default=8, ge=1, le=30)


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    document_id: str
    filename: str
    claim_type: str
    value: str
    normalized_value: str
    subject: str | None
    predicate: str | None
    object_value: str | None
    entity: str | None
    category: str | None
    unit: str | None
    currency: str | None
    claim_date: str | None
    time_period: str | None
    project_identifier: str | None
    document_identifier: str | None
    source_location: dict
    extraction_confidence: float | None
    normalization_method: str | None


class ClaimNormalizeResponse(BaseModel):
    normalized: int
    unchanged: int
    claims: list[ClaimRead]
    conflicts_created: int
    graph_nodes: int
    graph_edges: int


class ClaimList(BaseModel):
    items: list[ClaimRead]
    total: int
    limit: int
    offset: int


class ConflictRead(BaseModel):
    id: int
    classification: str
    conflict_category: str | None
    status: str
    explanation: str | None
    confidence: float | None
    confidence_note: str
    detection_method: str | None
    claim_a: ClaimRead | None
    claim_b: ClaimRead | None
    evidence_a_id: int
    evidence_b_id: int
    created_at: str
    resolved_at: str | None


class ConflictList(BaseModel):
    items: list[ConflictRead]
    total: int


class ConflictResolutionRead(BaseModel):
    conflict_id: int
    status: str
    note: str | None
    created_at: str


class SourceEvaluationRead(BaseModel):
    document_id: str
    filename: str
    source_type: str
    approval_status: str
    duplicate_source: bool
    duplicate_of_document_id: str | None
    heuristic_score: float
    criteria: dict
    weights: dict
    explanation: str
    evaluated_at: str


class SourceEvaluationList(BaseModel):
    items: list[SourceEvaluationRead]
    total: int
    score_notice: str


class GraphNodeRead(BaseModel):
    id: int
    key: str
    type: str
    label: str
    document_id: str | None
    claim_id: int | None
    evidence_id: int | None
    conflict_id: int | None
    entity_type: str | None
    metadata: dict


class GraphEdgeRead(BaseModel):
    id: int
    source: int
    target: int
    relationship: str
    evidence_id: int
    explanation: str


class KnowledgeGraphRead(BaseModel):
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
    node_count: int
    edge_count: int


class VerificationRead(BaseModel):
    question: str
    answer: str
    evidence: list[dict]
    relevant_claims: list[ClaimRead]
    contradictory_evidence: list[ConflictRead]
    comparison_findings: list[ConflictRead]
    conflict_assessment: str
    source_reliability: list[SourceEvaluationRead]
    relevant_relationships: list[GraphEdgeRead]
    uncertainty: list[str]
    limitations: list[str]
    abstained: bool
    confidence: str
    retrieval_method: str
    diagnostics: list[str]

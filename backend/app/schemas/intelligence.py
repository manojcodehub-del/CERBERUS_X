"""Request and response contracts for evidence retrieval and local answers."""

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    document_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=30)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=30)


class EvidenceReference(BaseModel):
    evidence_id: int
    document_id: str
    filename: str
    content_type: str | None
    text: str
    context_text: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    column_name: str | None = None
    cell_coordinate: str | None = None
    paragraph_index: int | None = None
    table_index: int | None = None
    extraction_method: str
    extraction_confidence: float | None = None
    score: float | None = None
    retrieval_method: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    items: list[EvidenceReference]
    retrieval_method: str
    diagnostics: list[str] = Field(default_factory=list)


class CitationRead(EvidenceReference):
    citation_order: int
    quoted_text: str


class AskResponse(BaseModel):
    question_id: str | None
    answer: str
    evidence: list[EvidenceReference]
    citations: list[CitationRead]
    confidence: str
    limitations: list[str]
    abstained: bool
    model_used: str
    retrieval_method: str


class IndexRequest(BaseModel):
    document_ids: list[str] | None = None
    force: bool = False


class IndexDocumentResult(BaseModel):
    document_id: str
    status: str
    evidence_count: int
    chunk_count: int
    message: str | None = None


class IndexResponse(BaseModel):
    status: str
    model: str
    documents: list[IndexDocumentResult]
    total_chunks: int
    reused_embeddings: int
    generated_embeddings: int


class OllamaModelStatus(BaseModel):
    name: str
    installed: bool


class EmbeddingStatus(BaseModel):
    ollama_reachable: bool
    embedding_model: str
    embedding_model_installed: bool
    indexed_chunks: int
    cached_vectors: int
    vector_dimension: int | None
    diagnostic: str | None


class RetrievalStatus(BaseModel):
    strategy: str
    indexed_documents: int
    indexed_chunks: int
    available_evidence: int
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    chat_model: str
    minimum_score: float

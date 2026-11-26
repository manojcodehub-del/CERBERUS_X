"""Hybrid local retrieval while keeping SQLite evidence as citation authority."""

import json
import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.document import Document
from app.models.embedding_cache import EmbeddingCache
from app.models.embedding_chunk import EmbeddingChunk
from app.models.evidence import Evidence
from app.services.ollama.client import OllamaClient, OllamaError

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
STOP_WORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from", "how", "i", "in", "is", "it", "of", "on", "or", "the", "this", "to", "was", "what", "when", "which", "who", "with"}


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence: Evidence
    document: Document
    score: float
    retrieval_method: str
    matched_text: str


@dataclass(frozen=True)
class RetrievalResult:
    items: list[RetrievedEvidence]
    method: str
    diagnostics: list[str]


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(value) if len(token) > 1 and token.casefold() not in STOP_WORDS}


def _keyword_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    body = text.casefold()
    overlap = len(query_tokens.intersection(_tokens(text))) / len(query_tokens)
    phrase = 1.0 if query.casefold().strip() in body else 0.0
    return min(1.0, overlap * 0.85 + phrase * 0.15)


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embedding dimensions do not match.")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def retrieve(session: Session, client: OllamaClient, settings: Settings, query: str,
             document_id: str | None = None, top_k: int | None = None,
             document_ids: list[str] | None = None) -> RetrievalResult:
    limit = top_k or settings.retrieval_top_k
    diagnostics: list[str] = []
    chunk_statement = (
        select(EmbeddingChunk, Evidence, Document, EmbeddingCache)
        .join(Evidence, Evidence.id == EmbeddingChunk.evidence_id)
        .join(Document, Document.id == EmbeddingChunk.document_id)
        .join(EmbeddingCache, EmbeddingCache.id == EmbeddingChunk.embedding_id)
    )
    # Untagged and :latest names identify the same Ollama model.
    model_name = settings.ollama_embed_model
    try:
        model_name = client.require_model(settings.ollama_embed_model)
    except OllamaError as exc:
        diagnostics.append(str(exc))
    chunk_statement = chunk_statement.where(EmbeddingChunk.model_name == model_name)
    if document_id:
        chunk_statement = chunk_statement.where(EmbeddingChunk.document_id == document_id)
    if document_ids is not None:
        chunk_statement = chunk_statement.where(EmbeddingChunk.document_id.in_(document_ids))
    records = session.execute(chunk_statement).all()

    query_vector: list[float] | None = None
    if records:
        try:
            query_vector = client.embed([query], model_name)[0]
        except (OllamaError, IndexError) as exc:
            diagnostics.append(str(exc) if isinstance(exc, OllamaError) else "Local query embedding was empty.")

    if records and query_vector:
        by_evidence: dict[int, RetrievedEvidence] = {}
        for chunk, evidence, document, cached in records:
            try:
                vector = json.loads(cached.vector_json)
                semantic = max(0.0, _cosine(query_vector, [float(value) for value in vector]))
            except (ValueError, TypeError, json.JSONDecodeError):
                diagnostics.append("An indexed vector is malformed or has a mismatched dimension; keyword ranking was used for that record.")
                semantic = 0.0
            keyword = _keyword_score(query, chunk.chunk_text)
            score = 0.72 * semantic + 0.28 * keyword
            candidate = RetrievedEvidence(evidence, document, score, "hybrid", chunk.chunk_text)
            prior = by_evidence.get(evidence.id)
            if prior is None or candidate.score > prior.score:
                by_evidence[evidence.id] = candidate
        ranked = sorted(by_evidence.values(), key=lambda item: (-item.score, item.evidence.id))
        return RetrievalResult(ranked[:limit], "hybrid", diagnostics)

    # Without an indexed matching model, deterministic local keyword retrieval remains useful.
    statement = select(Evidence, Document).join(Document, Document.id == Evidence.document_id)
    if document_id:
        statement = statement.where(Evidence.document_id == document_id)
    if document_ids is not None:
        statement = statement.where(Evidence.document_id.in_(document_ids))
    rows = session.execute(statement.order_by(Evidence.id)).all()
    ranked_fallback: list[RetrievedEvidence] = []
    for evidence, document in rows:
        searchable = "\n".join(part for part in (evidence.context_text, evidence.extracted_text, evidence.original_text) if part)
        score = _keyword_score(query, searchable)
        if score > 0:
            excerpt = _keyword_excerpt(query, searchable)
            ranked_fallback.append(RetrievedEvidence(evidence, document, score, "keyword", excerpt))
    ranked_fallback.sort(key=lambda item: (-item.score, item.evidence.id))
    method = "keyword_only" if records else "unindexed_keyword"
    if not rows and not diagnostics:
        diagnostics.append("No extracted evidence is available. Upload and process a document first.")
    elif not records:
        diagnostics.append("No current embedding index was found; results use local keyword matching.")
    return RetrievalResult(ranked_fallback[:limit], method, diagnostics)


def _keyword_excerpt(query: str, text: str, limit: int = 2400) -> str:
    if len(text) <= limit:
        return text
    folded = text.casefold()
    positions = [folded.find(token) for token in _tokens(query) if folded.find(token) >= 0]
    center = min(positions) if positions else 0
    start = max(0, min(center - limit // 3, len(text) - limit))
    return text[start:start + limit]

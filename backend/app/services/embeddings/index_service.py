"""Incremental, persistent indexing of local evidence embeddings."""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.document import Document, utc_now
from app.models.embedding_cache import EmbeddingCache
from app.models.embedding_chunk import EmbeddingChunk
from app.models.evidence import Evidence
from app.models.processing_job import ProcessingJob
from app.services.embeddings.chunker import chunk_evidence
from app.services.ollama.client import OllamaClient, OllamaError


@dataclass(frozen=True)
class IndexedDocument:
    document_id: str
    status: str
    evidence_count: int
    chunk_count: int
    reused_embeddings: int = 0
    generated_embeddings: int = 0
    message: str | None = None


def index_document(session: Session, document: Document, client: OllamaClient, settings: Settings,
                   force: bool = False) -> IndexedDocument:
    evidence_rows = session.scalars(
        select(Evidence).where(Evidence.document_id == document.id).order_by(Evidence.id)
    ).all()
    expected = []
    for evidence in evidence_rows:
        for chunk in chunk_evidence(evidence, settings.retrieval_chunk_size, settings.retrieval_chunk_overlap):
            digest = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            expected.append((chunk, digest))
    if not expected:
        return IndexedDocument(document.id, "skipped", len(evidence_rows), 0, message="No non-empty evidence is available to index.")

    model_name = client.require_model(settings.ollama_embed_model)
    existing = session.scalars(select(EmbeddingChunk).where(
        EmbeddingChunk.document_id == document.id,
        EmbeddingChunk.model_name == model_name,
    )).all()
    expected_keys = {(chunk.evidence_id, chunk.chunk_index, digest) for chunk, digest in expected}
    existing_keys = {(chunk.evidence_id, chunk.chunk_index, chunk.content_hash) for chunk in existing}
    if not force and existing_keys == expected_keys:
        return IndexedDocument(document.id, "unchanged", len(evidence_rows), len(expected), message="Stored chunks and source hashes are current.")

    job = ProcessingJob(document_id=document.id, job_type="embedding_index", status="running", progress=5,
                        started_at=utc_now())
    session.add(job)
    session.commit()
    job_id = job.id
    try:
        hashes = {digest for _, digest in expected}
        cache_rows = session.scalars(select(EmbeddingCache).where(
            EmbeddingCache.model_name == model_name,
            EmbeddingCache.content_hash.in_(hashes),
        )).all()
        vector_by_hash = {row.content_hash: row for row in cache_rows}
        unique_text_by_hash: dict[str, str] = {}
        for chunk, digest in expected:
            if digest not in vector_by_hash:
                unique_text_by_hash.setdefault(digest, chunk.text)

        generated = 0
        missing = list(unique_text_by_hash.items())
        for offset in range(0, len(missing), settings.embedding_batch_size):
            batch = missing[offset:offset + settings.embedding_batch_size]
            vectors = client.embed([content for _, content in batch], model_name)
            for (content_hash, _), vector in zip(batch, vectors, strict=True):
                if not vector:
                    raise OllamaError("ollama_invalid_embedding", "Ollama returned an empty embedding.")
                cache = EmbeddingCache(model_name=model_name, content_hash=content_hash, dimension=len(vector),
                                       vector_json=json.dumps(vector, separators=(",", ":")))
                session.add(cache)
                vector_by_hash[content_hash] = cache
                generated += 1
            job.progress = min(75, 10 + int((offset + len(batch)) / max(1, len(missing)) * 65))
            session.commit()

        dimensions = {row.dimension for row in vector_by_hash.values() if row.content_hash in hashes}
        if len(dimensions) != 1:
            raise OllamaError("embedding_dimension_mismatch", "Stored and newly generated vectors have inconsistent dimensions.")

        session.execute(delete(EmbeddingChunk).where(
            EmbeddingChunk.document_id == document.id,
            EmbeddingChunk.model_name == model_name,
        ))
        for chunk, digest in expected:
            cache = vector_by_hash[digest]
            session.add(EmbeddingChunk(
                document_id=document.id,
                evidence_id=chunk.evidence_id,
                embedding_id=cache.id,
                model_name=model_name,
                content_hash=digest,
                source_hash=chunk.source_hash,
                chunk_index=chunk.chunk_index,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                chunk_text=chunk.text,
            ))
        job = session.get(ProcessingJob, job_id)
        if job:
            job.status = "completed"
            job.progress = 100
            job.completed_at = utc_now()
            job.error_message = None
        session.commit()
        reused = len({digest for _, digest in expected}) - generated
        return IndexedDocument(document.id, "completed", len(evidence_rows), len(expected),
                               reused_embeddings=max(0, reused), generated_embeddings=generated)
    except Exception as exc:
        session.rollback()
        failed_job = session.get(ProcessingJob, job_id)
        if failed_job:
            failed_job.status = "failed"
            failed_job.progress = 100
            failed_job.completed_at = utc_now()
            failed_job.error_message = str(exc)[:1000] if isinstance(exc, OllamaError) else "Local embedding indexing failed."
            session.commit()
        if isinstance(exc, OllamaError):
            raise
        raise OllamaError("embedding_index_failed", "Local embedding indexing failed; evidence remains unchanged.") from exc

"""Provenance-preserving text chunking for extracted evidence records."""

from dataclasses import dataclass

from app.models.evidence import Evidence


@dataclass(frozen=True)
class EvidenceChunk:
    evidence_id: int
    document_id: str
    source_hash: str | None
    chunk_index: int
    start_offset: int
    end_offset: int
    text: str


def chunk_evidence(evidence: Evidence, size: int, overlap: int) -> list[EvidenceChunk]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be positive and overlap must be smaller than size.")
    body = (evidence.extracted_text or evidence.original_text or "").strip()
    if not body:
        return []
    context = (evidence.context_text or "").strip()
    source_text = f"Context: {context}\nEvidence: {body}" if context and context not in body else body
    chunks: list[EvidenceChunk] = []
    start = 0
    while start < len(source_text):
        end = min(start + size, len(source_text))
        if end < len(source_text):
            boundary = max(source_text.rfind("\n", start + int(size * 0.65), end),
                           source_text.rfind(" ", start + int(size * 0.65), end))
            if boundary > start:
                end = boundary
        chunk_text = source_text[start:end].strip()
        if chunk_text:
            chunks.append(EvidenceChunk(
                evidence_id=evidence.id,
                document_id=evidence.document_id,
                source_hash=evidence.source_hash,
                chunk_index=len(chunks),
                start_offset=start,
                end_offset=end,
                text=chunk_text,
            ))
        if end >= len(source_text):
            break
        next_start = max(start + 1, end - overlap)
        start = next_start
    return chunks

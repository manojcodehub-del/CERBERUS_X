"""Local indexing, retrieval, and evidence-grounded answer endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.dependencies import get_database_session
from app.models.document import Document
from app.models.embedding_cache import EmbeddingCache
from app.models.embedding_chunk import EmbeddingChunk
from app.models.evidence import Evidence
from app.schemas.intelligence import (
    AskRequest,
    AskResponse,
    EmbeddingStatus,
    IndexDocumentResult,
    IndexRequest,
    IndexResponse,
    RetrievalStatus,
    SearchRequest,
    SearchResponse,
)
from app.services.embeddings.index_service import IndexedDocument, index_document
from app.services.ollama.client import OllamaClient, OllamaError
from app.services.reasoning.answer_service import answer_question
from app.services.retrieval.retrieval_service import retrieve

router = APIRouter(tags=["local intelligence"])


def _model_aliases(name: str) -> list[str]:
    return [name, f"{name}:latest"] if ":" not in name else [name]


def _client(request: Request) -> OllamaClient:
    try:
        return OllamaClient(request.app.state.settings)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc


def _to_index_response(results: list[IndexedDocument], model: str) -> IndexResponse:
    failed = any(item.status == "failed" for item in results)
    return IndexResponse(
        status="partial" if failed else "completed",
        model=model,
        documents=[IndexDocumentResult(
            document_id=item.document_id,
            status=item.status,
            evidence_count=item.evidence_count,
            chunk_count=item.chunk_count,
            message=item.message,
        ) for item in results],
        total_chunks=sum(item.chunk_count for item in results),
        reused_embeddings=sum(item.reused_embeddings for item in results),
        generated_embeddings=sum(item.generated_embeddings for item in results),
    )


def _index_one(session: Session, document: Document, client: OllamaClient, request: Request,
               force: bool) -> IndexedDocument:
    try:
        return index_document(session, document, client, request.app.state.settings, force)
    except OllamaError as exc:
        return IndexedDocument(document.id, "failed", 0, 0, message=str(exc))


@router.post("/embeddings/index", response_model=IndexResponse)
def index_evidence(
    payload: IndexRequest,
    request: Request,
    session: Session = Depends(get_database_session),
) -> IndexResponse:
    client = _client(request)
    if payload.document_ids:
        documents = session.scalars(select(Document).where(Document.id.in_(payload.document_ids))).all()
        found_ids = {document.id for document in documents}
        missing_ids = [document_id for document_id in payload.document_ids if document_id not in found_ids]
        if missing_ids:
            raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "One or more requested documents were not found."})
    else:
        documents = session.scalars(select(Document).join(Evidence, Evidence.document_id == Document.id)
                                    .distinct().order_by(Document.created_at, Document.id)).all()
    model_name = request.app.state.settings.ollama_embed_model
    if documents:
        try:
            model_name = client.require_model(model_name)
        except OllamaError as exc:
            raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    results = [_index_one(session, document, client, request, payload.force) for document in documents]
    return _to_index_response(results, model_name)


@router.post("/documents/{document_id}/reindex", response_model=IndexResponse)
def reindex_document(
    document_id: str,
    request: Request,
    session: Session = Depends(get_database_session),
) -> IndexResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    client = _client(request)
    try:
        model_name = client.require_model(request.app.state.settings.ollama_embed_model)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.code, "message": str(exc)}) from exc
    result = _index_one(session, document, client, request, force=True)
    response = _to_index_response([result], model_name)
    if result.status == "failed":
        raise HTTPException(status_code=503, detail={"code": "embedding_index_failed", "message": result.message})
    return response


@router.get("/embeddings/status", response_model=EmbeddingStatus)
def embedding_status(
    request: Request,
    session: Session = Depends(get_database_session),
) -> EmbeddingStatus:
    settings = request.app.state.settings
    indexed_chunks = 0
    cached_vectors = session.scalar(select(func.count()).select_from(EmbeddingCache).where(
        EmbeddingCache.model_name.in_(_model_aliases(settings.ollama_embed_model))
    )) or 0
    dimensions = []
    diagnostic = None
    installed = False
    reachable = False
    actual_model_name = settings.ollama_embed_model
    aliases = _model_aliases(actual_model_name)
    try:
        client = _client(request)
        reachable = True
        try:
            actual_model_name = client.require_model(settings.ollama_embed_model)
            installed = True
            aliases = [actual_model_name]
        except OllamaError as exc:
            diagnostic = str(exc)
    except (OllamaError, HTTPException) as exc:
        diagnostic = str(exc.detail.get("message")) if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) else str(exc)
    indexed_chunks = session.scalar(select(func.count()).select_from(EmbeddingChunk).where(
        EmbeddingChunk.model_name.in_(aliases)
    )) or 0
    dimensions = session.scalars(select(EmbeddingCache.dimension).where(
        EmbeddingCache.model_name.in_(aliases)
    ).distinct()).all()
    dimension = dimensions[0] if len(dimensions) == 1 else None
    if len(dimensions) > 1:
        diagnostic = "The database contains more than one vector dimension for the configured embedding model."
    return EmbeddingStatus(ollama_reachable=reachable, embedding_model=settings.ollama_embed_model,
                           embedding_model_installed=installed, indexed_chunks=indexed_chunks,
                           cached_vectors=cached_vectors, vector_dimension=dimension, diagnostic=diagnostic)


@router.get("/retrieval/status", response_model=RetrievalStatus)
def retrieval_status(
    request: Request,
    session: Session = Depends(get_database_session),
) -> RetrievalStatus:
    settings = request.app.state.settings
    aliases = _model_aliases(settings.ollama_embed_model)
    indexed_docs = session.scalar(select(func.count(func.distinct(EmbeddingChunk.document_id))).where(
        EmbeddingChunk.model_name.in_(aliases)
    )) or 0
    indexed_chunks = session.scalar(select(func.count()).select_from(EmbeddingChunk).where(
        EmbeddingChunk.model_name.in_(aliases)
    )) or 0
    available_evidence = session.scalar(select(func.count()).select_from(Evidence)) or 0
    return RetrievalStatus(strategy="semantic + keyword hybrid with keyword fallback",
                           indexed_documents=indexed_docs, indexed_chunks=indexed_chunks,
                           available_evidence=available_evidence, chunk_size=settings.retrieval_chunk_size,
                           chunk_overlap=settings.retrieval_chunk_overlap,
                           embedding_model=settings.ollama_embed_model, chat_model=settings.ollama_chat_model,
                           minimum_score=settings.retrieval_min_score)


@router.post("/search", response_model=SearchResponse)
def search_evidence(
    payload: SearchRequest,
    request: Request,
    session: Session = Depends(get_database_session),
) -> SearchResponse:
    client = _client(request)
    result = retrieve(session, client, request.app.state.settings, payload.query, payload.document_id, payload.top_k)
    return SearchResponse(query=payload.query, items=[
        {
            "evidence_id": item.evidence.id,
            "document_id": item.evidence.document_id,
            "filename": item.evidence.filename or item.document.original_filename,
            "content_type": item.evidence.content_type,
            "text": item.evidence.original_text,
            "context_text": item.evidence.context_text,
            "page_number": item.evidence.page_number,
            "sheet_name": item.evidence.sheet_name,
            "row_number": item.evidence.row_number,
            "column_name": item.evidence.column_name,
            "cell_coordinate": item.evidence.cell_coordinate,
            "paragraph_index": item.evidence.paragraph_index,
            "table_index": item.evidence.table_index,
            "extraction_method": item.evidence.extraction_method,
            "extraction_confidence": item.evidence.extraction_confidence,
            "score": round(item.score, 4),
            "retrieval_method": item.retrieval_method,
        } for item in result.items], retrieval_method=result.method, diagnostics=result.diagnostics)


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    request: Request,
    session: Session = Depends(get_database_session),
) -> AskResponse:
    client = _client(request)
    return answer_question(session, client, request.app.state.settings, payload.question,
                           payload.document_id, payload.top_k)

import json
import re

import httpx
import pytest
from sqlalchemy import select, func
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.models.answer_citation import AnswerCitation
from app.models.embedding_cache import EmbeddingCache
from app.models.embedding_chunk import EmbeddingChunk
from app.models.question import Question
from app.services.embeddings.chunker import chunk_evidence
from app.services.ollama.client import OllamaClient, OllamaError
from app.main import create_app


class FakeOllama:
    def __init__(self, settings, response=None):
        self.settings = settings
        self.chat_response = response
        self.embed_calls = 0
        self.chat_calls = 0

    @staticmethod
    def _model_key(value):
        return value if ":" in value else f"{value}:latest"

    def require_model(self, name):
        if "nomic" in name:
            return "nomic-embed-text:latest"
        return "qwen3.5:4b"

    def embed(self, texts, model=None):
        self.embed_calls += 1
        vectors = []
        for text in texts:
            vector = [0.0] * 32
            for token in re.findall(r"[\w₹]+", text.casefold()):
                vector[sum(token.encode("utf-8")) % len(vector)] += 1.0
            vectors.append(vector)
        return vectors

    def chat_json(self, messages, model=None):
        self.chat_calls += 1
        if isinstance(self.chat_response, Exception):
            raise self.chat_response
        if self.chat_response is not None:
            return self.chat_response, "qwen3.5:4b"
        content = messages[1]["content"]
        match = re.search(r"EVIDENCE_ID: (\d+).*?MATCHED_EVIDENCE_TEXT.*?\n(.*?)(?=\n\n---|\Z)", content, re.S)
        assert match, "the QA context must include source IDs and original text"
        evidence_id, source_text = int(match.group(1)), match.group(2)
        return {
            "answer": "The approved project budget is ₹10,00,000.",
            "abstained": False,
            "citations": [{"evidence_id": evidence_id, "quote": source_text}],
            "limitations": [],
        }, "qwen3.5:4b"


def _upload_and_process(client, text="Approved project budget is ₹10,00,000. The approval date is 2026-11-25."):
    uploaded = client.post("/api/documents/upload", files=[("files", ("phase4-sample.txt", text.encode(), "text/plain"))])
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()["items"][0]
    processed = client.post(f"/api/documents/{document['id']}/process")
    assert processed.status_code == 200, processed.text
    assert processed.json()["evidence_count"] > 0
    return document


def test_chunker_preserves_source_ids_offsets_and_table_context(test_app):
    from app.models.evidence import Evidence

    evidence = Evidence(id=51, document_id="doc-1", source_hash="abc", original_text="Approved: ₹10,00,000",
                        extracted_text="Approved: ₹10,00,000", extraction_method="csv:row", context_text="Field: Project budget")
    chunks = chunk_evidence(evidence, size=200, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].evidence_id == 51
    assert chunks[0].document_id == "doc-1"
    assert "Field: Project budget" in chunks[0].text
    assert "₹10,00,000" in chunks[0].text


def test_local_ollama_http_client_validates_model_and_embedding_response():
    def responder(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "nomic-embed-text:latest"}]})
        if request.url.path == "/api/embed":
            payload = json.loads(request.content)
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2] for _ in payload["input"]]})
        return httpx.Response(404)

    client = OllamaClient(Settings(_env_file=None), transport=httpx.MockTransport(responder))
    assert client.require_model("nomic-embed-text") == "nomic-embed-text:latest"
    assert client.embed(["one", "two"]) == [[0.1, 0.2], [0.1, 0.2]]
    with pytest.raises(OllamaError, match="not installed"):
        client.require_model("qwen3.5:4b")
    with pytest.raises(OllamaError, match="loopback"):
        OllamaClient(Settings(_env_file=None, ollama_base_url="http://example.com:11434"))


def test_index_search_and_answer_use_persisted_evidence(client, test_app, monkeypatch):
    document = _upload_and_process(client)
    fake = FakeOllama(test_app.state.settings)
    monkeypatch.setattr("app.api.intelligence._client", lambda _request: fake)

    indexed = client.post("/api/embeddings/index", json={"document_ids": [document["id"]]})
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["total_chunks"] >= 1
    assert indexed.json()["generated_embeddings"] >= 1
    assert indexed.json()["model"] == "nomic-embed-text:latest"
    embedding_status = client.get("/api/embeddings/status")
    assert embedding_status.status_code == 200
    assert embedding_status.json()["embedding_model_installed"] is True
    assert embedding_status.json()["vector_dimension"] == 32

    search = client.post("/api/search", json={"query": "approved project budget", "document_id": document["id"]})
    assert search.status_code == 200, search.text
    assert search.json()["retrieval_method"] == "hybrid"
    assert search.json()["items"][0]["filename"] == "phase4-sample.txt"

    answer = client.post("/api/ask", json={"question": "What is the approved project budget?", "document_id": document["id"]})
    assert answer.status_code == 200, answer.text
    result = answer.json()
    assert result["abstained"] is False
    assert result["model_used"] == "qwen3.5:4b"
    assert "₹10,00,000" in result["answer"]
    citation = result["citations"][0]
    assert citation["filename"] == "phase4-sample.txt"
    assert "Approved project budget" in citation["quoted_text"]

    with test_app.state.database.session_factory() as session:
        question = session.get(Question, result["question_id"])
        saved_citation = session.scalar(select(AnswerCitation).where(AnswerCitation.question_id == question.id))
        assert question.abstained is False
        assert saved_citation.evidence_id == citation["evidence_id"]
        assert saved_citation.quoted_text == citation["quoted_text"]
        assert session.scalar(select(func.count()).select_from(EmbeddingChunk)) >= 1
        assert session.scalar(select(func.count()).select_from(EmbeddingCache)) >= 1

    repeated = client.post("/api/embeddings/index", json={"document_ids": [document["id"]]})
    assert repeated.status_code == 200
    assert repeated.json()["documents"][0]["status"] == "unchanged"
    assert fake.embed_calls == 3  # index, search query, and answer query; unchanged reindex adds none

    with TestClient(create_app(test_app.state.settings)) as restarted_client:
        persisted = restarted_client.get("/api/retrieval/status").json()
        assert persisted["indexed_chunks"] >= 1
        assert persisted["available_evidence"] >= 1


def test_model_cannot_persist_a_fabricated_citation(client, test_app, monkeypatch):
    document = _upload_and_process(client)
    fake = FakeOllama(test_app.state.settings)
    monkeypatch.setattr("app.api.intelligence._client", lambda _request: fake)
    assert client.post("/api/embeddings/index", json={"document_ids": [document["id"]]}).status_code == 200
    fake.chat_response = {
        "answer": "The budget is ₹99,00,000.",
        "abstained": False,
        "citations": [{"evidence_id": 999999, "quote": "fabricated"}],
        "limitations": [],
    }
    response = client.post("/api/ask", json={"question": "What is the approved project budget?"})
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["citations"] == []
    with test_app.state.database.session_factory() as session:
        question = session.get(Question, response.json()["question_id"])
        assert question.abstained is True
        assert not session.scalars(select(AnswerCitation).where(AnswerCitation.question_id == question.id)).all()

    real_evidence_id = client.get(f"/api/documents/{document['id']}/evidence").json()["items"][0]["id"]
    fake.chat_response = {
        "answer": "The project budget is INR 99,000.",
        "abstained": False,
        "citations": [{"evidence_id": real_evidence_id, "quote": "The budget is INR 99,000."}],
        "limitations": [],
    }
    wrong_quote = client.post("/api/ask", json={"question": "What is the approved project budget?"})
    assert wrong_quote.status_code == 200
    assert wrong_quote.json()["abstained"] is True
    assert wrong_quote.json()["citations"] == []


def test_missing_qwen_abstains_without_cloud_fallback(client, test_app, monkeypatch):
    document = _upload_and_process(client)
    fake = FakeOllama(test_app.state.settings)
    monkeypatch.setattr("app.api.intelligence._client", lambda _request: fake)
    assert client.post("/api/embeddings/index", json={"document_ids": [document["id"]]}).status_code == 200
    fake.chat_response = OllamaError("ollama_model_missing", "Local model 'qwen3.5:4b' is not installed; no model was downloaded.")
    response = client.post("/api/ask", json={"question": "What is the approved project budget?"})
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["citations"] == []
    assert "unavailable" in response.json()["limitations"][0]


def test_question_with_no_relevant_evidence_abstains_without_calling_qwen(client, test_app, monkeypatch):
    _upload_and_process(client, "The document describes a local software project and its installation steps.")
    fake = FakeOllama(test_app.state.settings)
    monkeypatch.setattr("app.api.intelligence._client", lambda _request: fake)
    response = client.post("/api/ask", json={"question": "Which aircraft flew to Mars?"})
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["model_used"] == "not_called"
    assert fake.chat_calls == 0

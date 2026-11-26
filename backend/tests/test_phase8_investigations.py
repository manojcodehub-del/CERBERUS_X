"""Temporary-database coverage for persisted Phase 8 investigations."""

import json
from types import SimpleNamespace

from sqlalchemy import select

from app.models.document import Document
from app.models.evidence import Evidence
from app.models.investigation import Investigation
from app.schemas.intelligence import CitationRead
from app.services.ollama.client import OllamaError


def _upload_text(client, filename: str, body: str) -> dict:
    uploaded = client.post("/api/documents/upload", files=[("files", (filename, body.encode("utf-8"), "text/plain"))])
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()["items"][0]
    processed = client.post(f"/api/documents/{document['id']}/process")
    assert processed.status_code == 200, processed.text
    return document


def _install_local_fakes(monkeypatch, stance="supporting"):
    class FakeLocalClient:
        def __init__(self, _settings):
            pass

        def require_model(self, name):
            raise OllamaError("ollama_unavailable", f"Local embedding model {name} unavailable; keyword fallback used.")

        def chat_json(self, messages, model=None):
            request = json.loads(messages[-1]["content"])
            evidence = request["evidence"][0]
            source = evidence["text"]
            quote = source.splitlines()[-1].strip() or source[:80]
            return ({"items": [{"evidence_id": evidence["evidence_id"], "stance": stance, "quote": quote}]}, model or "local-test-model")

    def fake_answer(session, _client, _settings, _question, document_id=None, top_k=None, document_ids=None):
        statement = select(Evidence).order_by(Evidence.id)
        if document_ids is not None:
            statement = statement.where(Evidence.document_id.in_(document_ids))
        elif document_id:
            statement = statement.where(Evidence.document_id == document_id)
        evidence = session.scalars(statement).first()
        document = session.get(Document, evidence.document_id)
        quote = evidence.original_text.splitlines()[-1].strip() or evidence.original_text[:80]
        citation = CitationRead(
            evidence_id=evidence.id, document_id=document.id, filename=document.original_filename,
            content_type=evidence.content_type, text=evidence.original_text, context_text=evidence.context_text,
            page_number=evidence.page_number, sheet_name=evidence.sheet_name, row_number=evidence.row_number,
            column_name=evidence.column_name, cell_coordinate=evidence.cell_coordinate,
            paragraph_index=evidence.paragraph_index, table_index=evidence.table_index,
            extraction_method=evidence.extraction_method, extraction_confidence=evidence.extraction_confidence,
            score=0.9, retrieval_method="keyword", citation_order=1, quoted_text=quote,
        )
        return SimpleNamespace(answer="The stored record states INR 1,250,000.", abstained=False,
                               limitations=["Test double for the local Qwen answer."] , citations=[citation])

    monkeypatch.setattr("app.api.investigations.OllamaClient", FakeLocalClient)
    monkeypatch.setattr("app.services.investigation.investigation_service.answer_question", fake_answer)


def test_investigation_report_is_scoped_cited_saved_and_exported(client, test_app, monkeypatch):
    _install_local_fakes(monkeypatch)
    source = _upload_text(client, "orion_investigation.txt",
                          "Project ORION-204 approved budget is INR 1,250,000.\n")
    other = _upload_text(client, "unrelated_investigation.txt",
                         "Project VEGA-91 office relocation is scheduled for 2027-04-15.\n")
    created = client.post("/api/investigations", json={
        "title": "Orion budget review",
        "question": "What approved budget does the ORION-204 record state?",
        "document_ids": [source["id"]],
        "top_k": 8,
    })
    assert created.status_code == 201, created.text
    investigation_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    generated = client.post(f"/api/investigations/{investigation_id}/generate", json={})
    assert generated.status_code == 200, generated.text
    body = generated.json()
    report = body["report"]
    assert body["status"] == "ready"
    assert report["scope"]["document_ids"] == [source["id"]]
    assert report["scope"]["document_count"] == 1
    assert report["executive_summary"]["abstained"] is False
    assert report["executive_summary"]["citations"]
    assert all(item["document_id"] == source["id"] for item in report["relevant_evidence"])
    assert other["id"] not in {item["document_id"] for item in report["relevant_evidence"]}
    assert report["supporting_evidence"]
    assert report["supporting_evidence"][0]["quote"] in report["relevant_evidence"][0]["text"]
    assert report["relevant_claims"]
    assert report["source_reliability"]

    listed = client.get("/api/investigations")
    assert listed.status_code == 200 and listed.json()["total"] == 1
    fetched = client.get(f"/api/investigations/{investigation_id}")
    assert fetched.status_code == 200 and fetched.json()["report"] == report
    with test_app.state.database.session_factory() as session:
        saved = session.get(Investigation, investigation_id)
        assert saved.status == "ready" and json.loads(saved.report_json)["question"] == body["question"]

    pdf = client.get(f"/api/investigations/{investigation_id}/report.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app(test_app.state.settings)) as restarted_client:
        persisted = restarted_client.get(f"/api/investigations/{investigation_id}")
        assert persisted.status_code == 200
        assert persisted.json()["report"] == report
        persisted_pdf = restarted_client.get(f"/api/investigations/{investigation_id}/report.pdf")
        assert persisted_pdf.status_code == 200 and persisted_pdf.content.startswith(b"%PDF")


def test_answer_citation_does_not_override_opposing_stance_label(client, monkeypatch):
    _install_local_fakes(monkeypatch, stance="opposing")
    source = _upload_text(client, "opposing_record.txt", "Project ORION-204 approved budget is INR 1,250,000.\n")
    created = client.post("/api/investigations", json={
        "title": "Opposing-source review",
        "question": "What approved budget does the ORION-204 record state?",
        "document_ids": [source["id"]],
    })
    assert created.status_code == 201
    generated = client.post(f"/api/investigations/{created.json()['id']}/generate", json={})
    assert generated.status_code == 200, generated.text
    report = generated.json()["report"]
    assert report["opposing_evidence"]
    assert report["supporting_evidence"] == []
    assert report["opposing_claims"]
    assert report["supporting_claims"] == []

def test_missing_local_answer_model_preserves_evidence_and_abstains(client, monkeypatch):
    _install_local_fakes(monkeypatch)

    def unavailable_answer(*_args, **_kwargs):
        raise OllamaError("model_not_found", "Configured local chat model is not installed.")

    monkeypatch.setattr("app.services.investigation.investigation_service.answer_question", unavailable_answer)
    source = _upload_text(client, "local_model_missing.txt", "Project ORION-204 approved budget is INR 1,250,000.\n")
    created = client.post("/api/investigations", json={
        "title": "Local model availability review",
        "question": "What approved budget does the ORION-204 record state?",
        "document_ids": [source["id"]],
    })
    generated = client.post(f"/api/investigations/{created.json()['id']}/generate", json={})
    assert generated.status_code == 200, generated.text
    report = generated.json()["report"]
    assert report["relevant_evidence"]
    assert report["relevant_claims"]
    assert report["conclusion"]["abstained"] is True
    assert report["conclusion"]["citations"] == []
    assert any("Configured local chat model is not installed" in item for item in report["diagnostics"])

def test_investigation_validation_and_insufficient_evidence_abstention(client, monkeypatch):
    _install_local_fakes(monkeypatch)
    invalid = client.post("/api/investigations", json={"title": "  ", "question": "hi"})
    assert invalid.status_code == 422
    missing_doc = client.post("/api/investigations", json={
        "title": "Missing source", "question": "What happened?", "document_ids": ["not-a-document"],
    })
    assert missing_doc.status_code == 404

    created = client.post("/api/investigations", json={
        "title": "Empty source review", "question": "What does the collection establish?",
    })
    assert created.status_code == 201, created.text
    generated = client.post(f"/api/investigations/{created.json()['id']}/generate", json={})
    assert generated.status_code == 200, generated.text
    report = generated.json()["report"]
    assert report["executive_summary"]["abstained"] is True
    assert report["conclusion"]["citations"] == []
    assert report["supporting_evidence"] == []
    assert any("No stored source evidence" in value for value in report["missing_evidence"] + report["uncertainty"])


def test_investigation_not_found_and_pdf_before_generation_errors(client):
    assert client.get("/api/investigations/9999").status_code == 404
    assert client.post("/api/investigations/9999/generate", json={}).status_code == 404
    created = client.post("/api/investigations", json={"title": "Draft report", "question": "What is known?"})
    assert created.status_code == 201
    pdf = client.get(f"/api/investigations/{created.json()['id']}/report.pdf")
    assert pdf.status_code == 409


def test_common_length_units_normalize_to_same_canonical_value(client):
    _upload_text(client, "orion_quantity_km.txt", "Project ORION-204 planned distance is 3 km.\n")
    _upload_text(client, "orion_quantity_meters.txt", "Project ORION-204 planned distance is 3000 meters.\n")
    normalized = client.post("/api/claims/normalize", json={})
    assert normalized.status_code == 200, normalized.text
    claims = client.get("/api/claims?normalized_only=true").json()["items"]
    distance_claims = [item for item in claims if item["claim_type"] == "quantity"]
    assert len(distance_claims) == 2
    assert {(item["object_value"], item["unit"]) for item in distance_claims} == {("3000", "m")}
    assert not any(item["classification"] == "CONFIRMED_CONFLICT" for item in client.get("/api/contradictions").json()["items"])


def test_high_similarity_same_claim_is_possible_duplicate_not_conflict(client):
    common = ("Project ORION-204 approved budget is INR 1,000,000. "
              "This signed record states the approved project authorization for the current fiscal year "
              "and remains in force throughout the review period.")
    _upload_text(client, "orion_record_a.txt", common + " Source marker Alpha.\n")
    _upload_text(client, "orion_record_b.txt", common + " Source marker Bravo.\n")
    normalized = client.post("/api/claims/normalize", json={})
    assert normalized.status_code == 200, normalized.text
    findings = client.get("/api/contradictions?classification=POSSIBLE_DUPLICATE")
    assert findings.status_code == 200, findings.text
    assert findings.json()["total"] == 1
    item = findings.json()["items"][0]
    assert item["classification"] == "POSSIBLE_DUPLICATE"
    assert "not a contradiction" in item["explanation"]
    assert item["claim_a"]["value"] == item["claim_b"]["value"]


def test_dated_claims_create_evidence_backed_event_graph_nodes(client):
    _upload_text(client, "orion_event.txt", "Project ORION-204 approval date is 2026-04-01.\n")
    normalized = client.post("/api/claims/normalize", json={})
    assert normalized.status_code == 200, normalized.text
    graph = client.get("/api/knowledge-graph?limit=500").json()
    event_nodes = [node for node in graph["nodes"] if node["type"] == "event"]
    assert event_nodes
    evidence_nodes = [node for node in graph["nodes"] if node["type"] == "evidence"]
    evidence_node = next(node for node in evidence_nodes if node.get("document_id"))
    assert evidence_node["metadata"]["filename"] == "orion_event.txt"
    assert evidence_node["metadata"]["source_location"]["paragraph_index"] is not None
    event = next(node for node in event_nodes if node["metadata"].get("date") == "2026-04-01")
    assert event["metadata"]["source_location"]["paragraph_index"] is not None
    edges = [edge for edge in graph["edges"] if edge["target"] == event["id"] or edge["source"] == event["id"]]
    assert any(edge["relationship"] == "CLAIM_REFERENCES_EVENT" for edge in edges)
    assert all(edge["evidence_id"] is not None for edge in edges)


def test_diagnostics_reports_actual_storage_and_never_claims_offline_ready(client):
    result = client.get("/api/system/status")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["storage_free_bytes"] is None or body["storage_free_bytes"] > 0
    assert body["offline_readiness"] == "not_verified"






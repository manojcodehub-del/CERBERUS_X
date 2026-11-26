"""Deterministic Phase 5 tests using temporary SQLite and synthetic records."""

import sqlite3

from sqlalchemy import func, select

from app.models.claim import Claim
from app.models.conflict_resolution import ConflictResolution
from app.models.contradiction import Contradiction
from app.models.knowledge_graph import KnowledgeGraphEdge, KnowledgeGraphNode
from app.models.source_evaluation import SourceEvaluation
from app.database.session import Database
from app.services.knowledge_graph.graph_service import build_graph


def _upload_text(client, filename: str, text: str) -> dict:
    response = client.post("/api/documents/upload", files=[("files", (filename, text.encode("utf-8"), "text/plain"))])
    assert response.status_code == 201, response.text
    document = response.json()["items"][0]
    processed = client.post(f"/api/documents/{document['id']}/process")
    assert processed.status_code == 200, processed.text
    return document


def _normalize(client):
    response = client.post("/api/claims/normalize", json={})
    assert response.status_code == 200, response.text
    return response.json()


def test_same_field_conflict_is_explainable_and_preserves_provenance(client, test_app):
    _upload_text(client, "orion_approved_a.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _upload_text(client, "orion_approved_b.txt", "Project ORION-204 approved budget is ₹12,00,000.\n")

    normalized = _normalize(client)
    assert normalized["normalized"] >= 2
    assert normalized["conflicts_created"] >= 1
    conflicts = client.get("/api/contradictions?classification=CONFIRMED_CONFLICT")
    assert conflicts.status_code == 200, conflicts.text
    conflict = conflicts.json()["items"][0]
    assert conflict["claim_a"]["project_identifier"] == "ORION-204"
    assert conflict["claim_a"]["predicate"] == "approved_budget"
    assert conflict["claim_a"]["source_location"]["paragraph_index"] == 0
    assert conflict["claim_a"]["value"] != conflict["claim_b"]["value"]
    assert "not which value is true" in conflict["explanation"]

    with test_app.state.database.session_factory() as session:
        original_values = session.scalars(select(Claim.value).order_by(Claim.id)).all()
        assert "₹10,00,000" in original_values
        assert "₹12,00,000" in original_values
        saved = session.get(Contradiction, conflict["id"])
        before = session.scalar(select(func.count()).select_from(Contradiction))
        assert saved.original_value_a and saved.original_value_b
        assert saved.source_location_a and saved.source_location_b

    repeated = _normalize(client)
    assert repeated["conflicts_created"] == 0
    with test_app.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Contradiction)) == before


def test_distinct_financial_categories_are_not_flagged_as_conflicts(client):
    _upload_text(client, "orion_budget.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _upload_text(client, "orion_quote.txt", "Project ORION-204 procurement estimate is ₹12,00,000.\n")
    _normalize(client)
    classifications = {item["classification"] for item in client.get("/api/contradictions").json()["items"]}
    assert "CATEGORY_MISMATCH" in classifications
    assert "CONFIRMED_CONFLICT" not in classifications


def test_alpha_project_ids_detect_budget_conflicts_and_keep_vendor_quotes_separate(client):
    sample_text = (
        "SYNTHETIC DEMONSTRATION DATA — invented values for local CERBERUS-X testing only.\n"
        "Project ID: DEMO-ALPHA\n"
        "The approved project budget for Project DEMO-ALPHA is INR 1,250,000.\n"
        "Approval date: 2026-11-24.\n"
        "The vendor quotation is INR 1,400,000 and is not the approved budget.\n"
    )
    sample = _upload_text(client, "demo_alpha_sample.txt", sample_text)
    amendment = _upload_text(
        client,
        "demo_alpha_amendment.txt",
        "Project ID: DEMO-ALPHA\nThe revised approved project budget is INR 1,850,000.\n",
    )

    normalized = _normalize(client)
    assert normalized["conflicts_created"] >= 1
    sample_claims = client.get(
        "/api/claims", params={"document_id": sample["id"], "normalized_only": "true"}
    ).json()["items"]
    money = {claim["value"]: claim for claim in sample_claims if claim["claim_type"] == "monetary_amount"}
    assert money["INR 1,250,000"]["project_identifier"] == "DEMO-ALPHA"
    assert money["INR 1,250,000"]["predicate"] == "approved_budget"
    assert money["INR 1,400,000"]["project_identifier"] == "DEMO-ALPHA"
    assert money["INR 1,400,000"]["predicate"] == "procurement_estimate"

    amendment_claims = client.get(
        "/api/claims", params={"document_id": amendment["id"], "normalized_only": "true"}
    ).json()["items"]
    revised = next(claim for claim in amendment_claims if claim["value"] == "INR 1,850,000")
    assert revised["project_identifier"] == "DEMO-ALPHA"
    assert revised["predicate"] == "approved_budget"

    conflicts = client.get("/api/contradictions").json()["items"]
    target = next(
        item for item in conflicts
        if item["claim_a"] and item["claim_b"]
        and {item["claim_a"]["document_id"], item["claim_b"]["document_id"]} == {sample["id"], amendment["id"]}
        and {item["claim_a"]["value"], item["claim_b"]["value"]} == {"INR 1,250,000", "INR 1,850,000"}
    )
    assert target["classification"] == "CONFIRMED_CONFLICT"
    assert target["claim_a"]["source_location"]["paragraph_index"] is not None
    assert target["claim_b"]["source_location"]["paragraph_index"] is not None


def test_two_financial_categories_in_one_source_keep_their_local_context(client):
    _upload_text(client, "orion_mixed_categories.txt",
                 "Project ORION-204 approved budget is ₹10,00,000; procurement estimate is ₹12,00,000.\n")
    _upload_text(client, "orion_budget_confirm.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _normalize(client)
    claims = client.get("/api/claims?normalized_only=true").json()["items"]
    money = [item for item in claims if item["claim_type"] == "monetary_amount"]
    values_by_original = {item["value"]: item["predicate"] for item in money}
    assert values_by_original["₹10,00,000"] == "approved_budget"
    assert values_by_original["₹12,00,000"] == "procurement_estimate"
    classifications = {item["classification"] for item in client.get("/api/contradictions").json()["items"]}
    assert "CONFIRMED_CONFLICT" not in classifications


def test_status_changes_with_dates_are_temporal_not_confirmed_conflicts(client):
    _upload_text(client, "orion_january.txt", "Project ORION-204 project status is In Progress on 2026-01-10.\n")
    _upload_text(client, "orion_march.txt", "Project ORION-204 project status is Completed on 2026-03-10.\n")
    _normalize(client)
    conflicts = client.get("/api/contradictions").json()["items"]
    statuses = [item for item in conflicts if item["conflict_category"] == "status"]
    assert any(item["classification"] == "TEMPORAL_DIFFERENCE" for item in statuses)


def test_date_disagreement_and_draft_versus_approved_remain_reviewable(client):
    _upload_text(client, "orion_deadline_a.txt", "Project ORION-204 deadline date is 2026-06-01.\n")
    _upload_text(client, "orion_deadline_b.txt", "Project ORION-204 deadline date is 2026-06-15.\n")
    _upload_text(client, "orion_draft.txt", "Project ORION-204 draft approved budget is ₹20,00,000.\n")
    _upload_text(client, "orion_final.txt", "Project ORION-204 approved budget is ₹22,00,000.\n")
    _normalize(client)
    items = client.get("/api/contradictions").json()["items"]
    assert any(item["classification"] == "POTENTIAL_CONFLICT" and item["conflict_category"] == "date" for item in items)
    approved_budget = [item for item in items if item["conflict_category"] == "money" and
                       item["claim_a"] and item["claim_a"]["predicate"] == "approved_budget"]
    assert any(item["classification"] == "POTENTIAL_CONFLICT" for item in approved_budget)


def test_currency_and_measurement_units_are_explicit_mismatches(client):
    _upload_text(client, "orion_inr.txt", "Project ORION-204 approved budget is INR 1000.\n")
    _upload_text(client, "orion_usd.txt", "Project ORION-204 approved budget is USD 1000.\n")
    _upload_text(client, "orion_kg.txt", "Project ORION-204 quantity is 5 kg.\n")
    _upload_text(client, "orion_liters.txt", "Project ORION-204 quantity is 5 liters.\n")
    _normalize(client)
    items = client.get("/api/contradictions").json()["items"]
    assert any(item["classification"] == "UNIT_MISMATCH" and item["conflict_category"] == "money" for item in items)
    assert any(item["classification"] == "UNIT_MISMATCH" and item["conflict_category"] == "quantity" for item in items)


def test_duplicate_sources_are_not_independent_corroboration(client):
    _upload_text(client, "orion_source_original.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _upload_text(client, "orion_source_copy.txt", "  Project ORION-204   approved budget is ₹10,00,000.  \n")
    _normalize(client)
    sources = client.get("/api/reliability/sources").json()
    duplicate_rows = [item for item in sources["items"] if item["duplicate_source"]]
    assert len(duplicate_rows) == 1
    assert "not counted as independent corroboration" in duplicate_rows[0]["explanation"]
    assert "not a scientifically validated" in sources["score_notice"]


def test_independent_source_support_is_explained_separately_from_duplicates(client):
    _upload_text(client, "orion_record_a.txt", "Project ORION-204 approved budget is ₹10,00,000.\nSigned by finance.\n")
    _upload_text(client, "orion_record_b.txt", "Project ORION-204 approved budget is ₹10,00,000.\nRecorded in finance register.\n")
    _normalize(client)
    sources = client.get("/api/reliability/sources").json()["items"]
    assert len(sources) == 2
    assert all(not item["duplicate_source"] for item in sources)
    assert all(item["criteria"]["independent_corroboration"]["score"] >= 0.7 for item in sources)
    assert all("distinct source fingerprint" in item["criteria"]["independent_corroboration"]["reason"] for item in sources)


def test_reliability_weights_can_be_overridden_with_valid_configuration(client, monkeypatch):
    import json

    weights = {"authority": 0.10, "approval_status": 0.20, "recency": 0.10,
               "directness": 0.20, "completeness": 0.10,
               "extraction_quality": 0.15, "independent_corroboration": 0.15}
    monkeypatch.setenv("CERBERUS_RELIABILITY_WEIGHTS", json.dumps(weights))
    _upload_text(client, "orion_weights.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _normalize(client)
    response = client.get("/api/reliability/sources")
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["weights"] == weights


def test_graph_is_evidence_backed_and_idempotent(client, test_app):
    _upload_text(client, "orion_graph.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _normalize(client)
    first = client.get("/api/knowledge-graph").json()
    with test_app.state.database.session_factory() as session:
        nodes_before = session.scalar(select(func.count()).select_from(KnowledgeGraphNode))
        edges_before = session.scalar(select(func.count()).select_from(KnowledgeGraphEdge))
        assert edges_before > 0
        assert session.scalar(select(func.count()).select_from(KnowledgeGraphEdge).where(KnowledgeGraphEdge.evidence_id.is_(None))) == 0
        graph = build_graph(session)
        assert graph.number_of_nodes() == nodes_before
        assert graph.number_of_edges() == edges_before
        session.commit()
    second = client.get("/api/knowledge-graph").json()
    assert first["node_count"] == second["node_count"]
    assert first["edge_count"] == second["edge_count"]
    entity_id = next(item["id"] for item in first["nodes"] if item["type"] == "project")
    assert client.get(f"/api/knowledge-graph/entities/{entity_id}").status_code == 200


def test_resolution_keeps_audit_and_both_original_claims(client, test_app):
    _upload_text(client, "orion_resolution_a.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _upload_text(client, "orion_resolution_b.txt", "Project ORION-204 approved budget is ₹12,00,000.\n")
    _normalize(client)
    conflict = client.get("/api/contradictions?classification=CONFIRMED_CONFLICT").json()["items"][0]
    response = client.post(f"/api/contradictions/{conflict['id']}/resolve", json={"status": "under_review", "note": "Compare signed approval records."})
    assert response.status_code == 200, response.text
    with test_app.state.database.session_factory() as session:
        finding = session.get(Contradiction, conflict["id"])
        assert finding.status == "under_review"
        audit = session.scalar(select(ConflictResolution).where(ConflictResolution.conflict_id == finding.id))
        assert audit.note == "Compare signed approval records."
        assert session.get(Claim, finding.claim_a_id).value == conflict["claim_a"]["value"]
        assert session.get(Claim, finding.claim_b_id).value == conflict["claim_b"]["value"]


def test_verification_uses_retrieved_sources_and_abstains_on_conflict(client, test_app, monkeypatch):
    _upload_text(client, "orion_verify_a.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _upload_text(client, "orion_verify_b.txt", "Project ORION-204 approved budget is ₹12,00,000.\n")
    _normalize(client)

    class NoLocalEmbeddingModel:
        def __init__(self, _settings):
            pass

        def require_model(self, name):
            from app.services.ollama.client import OllamaError
            raise OllamaError("ollama_unavailable", f"Local model {name} is unavailable.")

        def embed(self, *_args, **_kwargs):
            raise AssertionError("Keyword fallback should not call embeddings when no index exists.")

    monkeypatch.setattr("app.api.verification.OllamaClient", NoLocalEmbeddingModel)
    result = client.post("/api/verification/analyze", json={"question": "What approved budget is recorded for Project ORION-204?", "top_k": 1})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["abstained"] is True
    assert body["evidence"]
    assert body["contradictory_evidence"]
    assert body["contradictory_evidence"][0]["claim_a"]
    assert body["contradictory_evidence"][0]["claim_b"]
    assert len(body["source_reliability"]) == 2
    assert any(item["evidence_id"] for item in body["evidence"])


def test_verification_abstains_when_no_source_evidence_matches(client, monkeypatch):
    class NoLocalEmbeddingModel:
        def __init__(self, _settings):
            pass

        def require_model(self, name):
            from app.services.ollama.client import OllamaError
            raise OllamaError("ollama_unavailable", f"Local model {name} is unavailable.")

    monkeypatch.setattr("app.api.verification.OllamaClient", NoLocalEmbeddingModel)
    result = client.post("/api/verification/analyze", json={"question": "Is the final project cost approved?"})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["abstained"] is True
    assert body["evidence"] == []
    assert "No stored source evidence matched" in body["uncertainty"][0]


def test_category_mismatch_is_reported_without_being_misrepresented_as_a_contradiction(client, monkeypatch):
    _upload_text(client, "orion_mixed_verify.txt",
                 "Project ORION-204 approved budget is ₹10,00,000; procurement estimate is ₹12,00,000.\n")
    _upload_text(client, "orion_same_budget.txt", "Project ORION-204 approved budget is ₹10,00,000.\n")
    _normalize(client)

    class NoLocalEmbeddingModel:
        def __init__(self, _settings):
            pass

        def require_model(self, name):
            from app.services.ollama.client import OllamaError
            raise OllamaError("ollama_unavailable", f"Local model {name} is unavailable.")

    monkeypatch.setattr("app.api.verification.OllamaClient", NoLocalEmbeddingModel)
    result = client.post("/api/verification/analyze", json={"question": "What approved budget is recorded for Project ORION-204?"})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["abstained"] is False
    assert body["contradictory_evidence"] == []
    assert body["conflict_assessment"] == "CATEGORY_MISMATCH"
    assert any(item["classification"] == "CATEGORY_MISMATCH" for item in body["comparison_findings"])


def test_invalid_and_missing_phase5_ids_return_clear_errors(client):
    assert client.post("/api/claims/normalize", json={"claim_ids": [0]}).status_code == 422
    assert client.get("/api/contradictions/999999").status_code == 404
    assert client.get("/api/reliability/sources/not-a-document-id").status_code == 404
    assert client.get("/api/knowledge-graph/entities/0").status_code == 422


def test_existing_phase4_claim_and_conflict_rows_survive_additive_migration(tmp_path):
    path = tmp_path / "phase4-existing.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE documents (
          id VARCHAR(36) PRIMARY KEY, original_filename VARCHAR(255) NOT NULL,
          stored_filename VARCHAR(64) NOT NULL UNIQUE, extension VARCHAR(12) NOT NULL,
          media_type VARCHAR(120) NOT NULL, size_bytes BIGINT NOT NULL, sha256 VARCHAR(64) NOT NULL UNIQUE,
          processing_status VARCHAR(24) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
        );
        CREATE TABLE evidence (
          id INTEGER PRIMARY KEY AUTOINCREMENT, document_id VARCHAR(36) NOT NULL,
          filename VARCHAR(255), page_number INTEGER, sheet_name VARCHAR(255), row_number INTEGER,
          column_name VARCHAR(255), content_type VARCHAR(64), extracted_text TEXT, cell_coordinate VARCHAR(32),
          paragraph_index INTEGER, table_index INTEGER, source_hash VARCHAR(64), evidence_key VARCHAR(64),
          original_text TEXT NOT NULL, extraction_method VARCHAR(64) NOT NULL, extraction_confidence FLOAT,
          context_text TEXT, created_at DATETIME NOT NULL
        );
        CREATE TABLE claims (
          id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_id INTEGER NOT NULL, claim_type VARCHAR(64) NOT NULL,
          value TEXT NOT NULL, normalized_value VARCHAR(512) NOT NULL, context TEXT, confidence FLOAT,
          created_at DATETIME NOT NULL
        );
        CREATE TABLE contradictions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_a_id INTEGER NOT NULL, evidence_b_id INTEGER NOT NULL,
          severity VARCHAR(24) NOT NULL, status VARCHAR(24) NOT NULL, explanation TEXT, confidence FLOAT,
          created_at DATETIME NOT NULL, resolved_at DATETIME
        );
        INSERT INTO documents VALUES ('kept-doc', 'orion.txt', 'stored.txt', '.txt', 'text/plain', 12, 'abc', 'COMPLETED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        INSERT INTO evidence (document_id, original_text, extraction_method, created_at) VALUES ('kept-doc', 'Project ORION-204 approved budget is ₹10,00,000.', 'text:utf-8', CURRENT_TIMESTAMP);
        INSERT INTO claims (evidence_id, claim_type, value, normalized_value, context, confidence, created_at) VALUES (1, 'monetary_amount', '₹10,00,000', '₹10,00,000', 'approved budget', 1, CURRENT_TIMESTAMP);
        INSERT INTO contradictions (evidence_a_id, evidence_b_id, severity, status, explanation, confidence, created_at) VALUES (1, 1, 'unreviewed', 'open', 'legacy row', 0.4, CURRENT_TIMESTAMP);
    """)
    connection.commit()
    connection.close()

    database = Database(f"sqlite:///{path.as_posix()}")
    try:
        database.create_tables()
        with database.session_factory() as session:
            assert session.get(Claim, 1).value == "₹10,00,000"
            assert session.get(Contradiction, 1).explanation == "legacy row"
            assert session.scalar(select(func.count()).select_from(SourceEvaluation)) == 0
        inspector = __import__("sqlalchemy").inspect(database.engine)
        claim_columns = {item["name"] for item in inspector.get_columns("claims")}
        assert "predicate" in claim_columns
        assert "source_evaluations" in inspector.get_table_names()
    finally:
        database.dispose()

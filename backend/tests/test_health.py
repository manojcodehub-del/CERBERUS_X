from sqlalchemy import inspect


def test_application_startup_creates_database_and_all_tables(client, test_app) -> None:
    engine = test_app.state.database.engine
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1

    tables = set(inspect(engine).get_table_names())
    assert {
        "documents",
        "evidence",
        "entities",
        "relationships",
        "contradictions",
        "processing_jobs",
        "questions",
        "answer_citations",
    }.issubset(tables)


def test_health_endpoint_reports_database_connection(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CERBERUS-X API",
        "database": "connected",
    }


def test_health_endpoint_allows_configured_local_frontend(client) -> None:
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})

    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_validation_errors_use_safe_structured_envelope(client) -> None:
    response = client.get("/api/documents", params={"limit": "not-a-number"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "issues" in response.json()["error"]


def test_openapi_describes_phase_two_routes(client) -> None:
    schema = client.get("/openapi.json")

    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/api/system/status" in paths
    assert "/api/documents/upload" in paths
    assert "/api/analytics" in paths

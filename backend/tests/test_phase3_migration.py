import sqlite3

from sqlalchemy import inspect

from app.database.session import Database


def test_phase2_sqlite_schema_gets_only_additive_phase3_columns(tmp_path) -> None:
    path = tmp_path / "phase2.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE documents (
            id VARCHAR(36) PRIMARY KEY, original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(64) NOT NULL UNIQUE, extension VARCHAR(12) NOT NULL,
            media_type VARCHAR(120) NOT NULL, size_bytes BIGINT NOT NULL, sha256 VARCHAR(64) NOT NULL UNIQUE,
            processing_status VARCHAR(24) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
        );
        CREATE TABLE evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id VARCHAR(36) NOT NULL,
            page_number INTEGER, sheet_name VARCHAR(255), row_number INTEGER, column_name VARCHAR(255),
            original_text TEXT NOT NULL, extraction_method VARCHAR(64) NOT NULL,
            extraction_confidence FLOAT, created_at DATETIME NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        ("kept-document", "kept.txt", "kept.txt", ".txt", "text/plain", 4, "a" * 64, "uploaded"),
    )
    connection.commit()
    connection.close()

    database = Database(f"sqlite:///{path.as_posix()}")
    try:
        database.create_tables()
        inspector = inspect(database.engine)
        evidence_columns = {column["name"] for column in inspector.get_columns("evidence")}
        assert {"filename", "content_type", "extracted_text", "cell_coordinate", "paragraph_index", "table_index", "source_hash", "evidence_key"}.issubset(evidence_columns)
        assert "claims" in inspector.get_table_names()
        claim_columns = {column["name"] for column in inspector.get_columns("claims")}
        assert {"subject", "predicate", "object_value", "entity", "category", "unit", "currency", "claim_date", "time_period", "project_identifier", "document_identifier", "source_location", "normalization_method"}.issubset(claim_columns)
        contradiction_columns = {column["name"] for column in inspector.get_columns("contradictions")}
        assert {"claim_a_id", "claim_b_id", "classification", "conflict_category", "detection_method"}.issubset(contradiction_columns)
        assert {"source_evaluations", "conflict_resolutions", "knowledge_graph_nodes", "knowledge_graph_edges"}.issubset(set(inspector.get_table_names()))
        with database.engine.connect() as migrated:
            assert migrated.exec_driver_sql("SELECT id FROM documents").scalar_one() == "kept-document"
    finally:
        database.dispose()

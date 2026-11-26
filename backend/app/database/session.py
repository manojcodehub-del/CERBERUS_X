"""SQLite engine and session factory."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import PROJECT_ROOT
from app.database.base import Base


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {"pool_pre_ping": True}

    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if url.database in (None, "", ":memory:"):
            engine_options["poolclass"] = StaticPool
        else:
            database_path = Path(url.database)
            if not database_path.is_absolute():
                database_path = PROJECT_ROOT / database_path
            database_path = database_path.resolve()
            database_path.parent.mkdir(parents=True, exist_ok=True)
            url = URL.create(
                drivername=url.drivername,
                username=url.username,
                password=url.password,
                host=url.host,
                port=url.port,
                database=str(database_path),
                query=url.query,
            )

    engine = create_engine(url, connect_args=connect_args, **engine_options)

    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine = build_engine(database_url)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

    def create_tables(self) -> None:
        # Importing registers every model on the shared Base metadata.
        import app.models  # noqa: F401

        self._migrate_existing_sqlite_schema()
        Base.metadata.create_all(bind=self.engine)
        if self.engine.dialect.name == "sqlite":
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_evidence_key "
                    "ON evidence (evidence_key) WHERE evidence_key IS NOT NULL"
                )
                connection.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_conflict_claim_pair "
                    "ON contradictions (claim_a_id, claim_b_id, classification) "
                    "WHERE claim_a_id IS NOT NULL AND claim_b_id IS NOT NULL"
                )
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_claims_predicate ON claims (predicate)")
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_claims_entity ON claims (entity)")
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_claims_category ON claims (category)")
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_claims_project_identifier ON claims (project_identifier)")
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_contradictions_claim_a_id ON contradictions (claim_a_id)")
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_contradictions_claim_b_id ON contradictions (claim_b_id)")
                connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_contradictions_class_status ON contradictions (classification, status)")

    def _migrate_existing_sqlite_schema(self) -> None:
        """Apply only additive columns before ORM metadata creates new indexes."""
        if self.engine.dialect.name != "sqlite":
            return
        additions = {
            "evidence": {
                "filename": "VARCHAR(255)",
                "content_type": "VARCHAR(64)",
                "extracted_text": "TEXT",
                "cell_coordinate": "VARCHAR(32)",
                "paragraph_index": "INTEGER",
                "table_index": "INTEGER",
                "source_hash": "VARCHAR(64)",
                "evidence_key": "VARCHAR(64)",
                "context_text": "TEXT",
            },
            "questions": {
                "answer_text": "TEXT",
                "answer_payload": "TEXT",
                "model_used": "VARCHAR(255)",
                "abstained": "BOOLEAN NOT NULL DEFAULT 0",
            },
            "claims": {
                "subject": "VARCHAR(512)",
                "predicate": "VARCHAR(256)",
                "object_value": "VARCHAR(512)",
                "entity": "VARCHAR(512)",
                "category": "VARCHAR(64)",
                "unit": "VARCHAR(64)",
                "currency": "VARCHAR(12)",
                "claim_date": "VARCHAR(32)",
                "time_period": "VARCHAR(128)",
                "project_identifier": "VARCHAR(128)",
                "document_identifier": "VARCHAR(36)",
                "source_location": "TEXT",
                "normalization_method": "VARCHAR(64)",
                "normalized_at": "DATETIME",
            },
            "contradictions": {
                "claim_a_id": "INTEGER REFERENCES claims(id) ON DELETE SET NULL",
                "claim_b_id": "INTEGER REFERENCES claims(id) ON DELETE SET NULL",
                "classification": "VARCHAR(32) NOT NULL DEFAULT 'POTENTIAL_CONFLICT'",
                "conflict_category": "VARCHAR(64)",
                "detection_method": "VARCHAR(64)",
                "original_value_a": "TEXT",
                "original_value_b": "TEXT",
                "normalized_value_a": "TEXT",
                "normalized_value_b": "TEXT",
                "source_location_a": "TEXT",
                "source_location_b": "TEXT",
            },
        }
        existing_tables = set(inspect(self.engine).get_table_names())
        with self.engine.begin() as connection:
            for table, columns in additions.items():
                if table not in existing_tables:
                    continue
                existing_columns = {column["name"] for column in inspect(connection).get_columns(table)}
                for name, column_type in columns.items():
                    if name not in existing_columns:
                        connection.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {column_type}')

    def check_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self.engine.dispose()

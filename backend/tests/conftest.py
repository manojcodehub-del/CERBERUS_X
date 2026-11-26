from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_app(tmp_path) -> FastAPI:
    database_path = (tmp_path / "cerberus_test.db").as_posix()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{database_path}",
        upload_dir=tmp_path / "uploads",
        processed_dir=tmp_path / "processed",
        max_upload_mb=1,
        max_upload_files=3,
        backend_cors_origins="http://127.0.0.1:5173,http://localhost:5173",
    )
    return create_app(settings)


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as test_client:
        yield test_client

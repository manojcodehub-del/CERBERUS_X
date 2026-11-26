"""Typed settings and project-local path resolution."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CERBERUS-X"
    app_env: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/cerberus_x.db"
    upload_dir: Path = Path("./data/uploads")
    processed_dir: Path = Path("./data/processed")
    max_upload_mb: int = Field(default=50, ge=1, le=1024)
    max_upload_files: int = Field(default=20, ge=1, le=100)
    tesseract_cmd: str | None = None
    ocr_engine: str = "tesseract"
    backend_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "qwen3.5:4b"
    ollama_embed_model: str = "nomic-embed-text"
    embedding_batch_size: int = Field(default=16, ge=1, le=128)
    retrieval_chunk_size: int = Field(default=1200, ge=200, le=8000)
    retrieval_chunk_overlap: int = Field(default=160, ge=0, le=2000)
    retrieval_top_k: int = Field(default=8, ge=1, le=30)
    retrieval_min_score: float = Field(default=0.08, ge=0, le=1)

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        if self.retrieval_chunk_overlap >= self.retrieval_chunk_size:
            raise ValueError("RETRIEVAL_CHUNK_OVERLAP must be smaller than RETRIEVAL_CHUNK_SIZE.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @property
    def resolved_upload_dir(self) -> Path:
        return self.resolve_path(self.upload_dir)

    @property
    def resolved_processed_dir(self) -> Path:
        return self.resolve_path(self.processed_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

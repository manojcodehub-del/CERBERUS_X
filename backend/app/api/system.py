"""Health and local runtime status endpoints."""

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.system import HealthRead, SystemStatusRead

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthRead)
def health(request: Request) -> HealthRead:
    settings = request.app.state.settings
    try:
        request.app.state.database.check_connection()
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "The local database is unavailable."},
        ) from exc
    return HealthRead(status="ok", service=f"{settings.app_name} API", database="connected")


@router.get("/system/status", response_model=SystemStatusRead)
def system_status(request: Request) -> SystemStatusRead:
    settings = request.app.state.settings
    try:
        request.app.state.database.check_connection()
        database_status = "connected"
    except SQLAlchemyError:
        logger.exception("System status could not connect to the local database")
        database_status = "unavailable"

    upload_dir = settings.resolved_upload_dir
    storage_free_bytes = None
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_status = "ready" if upload_dir.is_dir() else "unavailable"
        if storage_status == "ready":
            storage_free_bytes = shutil.disk_usage(upload_dir).free
    except OSError:
        logger.exception("System status could not access local upload storage")
        storage_status = "unavailable"

    overall_status = "ok" if database_status == "connected" and storage_status == "ready" else "degraded"
    return SystemStatusRead(
        status=overall_status,
        application=settings.app_name,
        environment=settings.app_env,
        database=database_status,
        upload_storage=storage_status,
        document_processing="available",
        ocr_engine=(
            "available"
            if settings.ocr_engine.lower() == "tesseract"
            and ((settings.tesseract_cmd and Path(settings.tesseract_cmd).is_file()) or shutil.which("tesseract"))
            else "unavailable"
        ),
        storage_free_bytes=storage_free_bytes,
        offline_readiness="not_verified",
    )

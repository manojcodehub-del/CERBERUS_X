"""FastAPI application factory and cross-cutting middleware."""

import logging
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import APIException
from app.core.logging_config import configure_logging
from app.database.session import Database

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    database = Database(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(app_settings.log_level)
        app_settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
        app_settings.resolved_processed_dir.mkdir(parents=True, exist_ok=True)
        database.create_tables()
        yield
        database.dispose()

    application = FastAPI(
        title=f"{app_settings.app_name} API",
        description="Local-first multimodal evidence intelligence API.",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.database = database
    application.include_router(api_router, prefix=app_settings.api_prefix)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(APIException)
    async def handle_api_exception(_request: Request, exc: APIException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and {"code", "message"}.issubset(exc.detail):
            error = {"code": exc.detail["code"], "message": exc.detail["message"]}
        else:
            try:
                code = HTTPStatus(exc.status_code).name.lower()
            except ValueError:
                code = "http_error"
            error = {"code": code, "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [
            {"location": list(error.get("loc", ())), "message": error.get("msg", "Invalid value."), "type": error.get("type", "value_error")}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Request validation failed.", "issues": issues}},
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request error for %s",
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An unexpected server error occurred."}},
        )

    return application


app = create_app()

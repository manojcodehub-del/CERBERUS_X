"""Safe local upload staging and deletion; this module never opens files as code."""

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import APIException
from app.models.document import Document
from app.services.ingestion.file_validator import FileValidationError, validate_content, validate_filename
from app.services.ingestion.file_storage import delete_document_file

CHUNK_SIZE = 1024 * 1024
from app.services.ingestion.file_detector import SUPPORTED_MEDIA_TYPES as MEDIA_TYPES


@dataclass(frozen=True)
class StagedUpload:
    temporary_path: Path
    original_filename: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str


def _validated_filename(filename: str | None) -> tuple[str, str, str, set[str]]:
    try:
        return validate_filename(filename)
    except FileValidationError as exc:
        raise APIException(exc.status_code, exc.code, str(exc)) from exc


def _validate_content(path: Path, extension: str, max_uncompressed_bytes: int | None = None) -> None:
    try:
        validate_content(path, extension, max_uncompressed_bytes)
    except FileValidationError as exc:
        raise APIException(exc.status_code, exc.code, str(exc)) from exc


async def _stage_one(upload: UploadFile, staging_dir: Path, max_bytes: int) -> StagedUpload:
    filename, extension, media_type, accepted_types = _validated_filename(upload.filename)
    supplied_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if supplied_type not in accepted_types:
        raise APIException(415, "content_type_mismatch", "The uploaded content type does not match the supported file type.")

    temporary_path = staging_dir / f"{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with temporary_path.open("xb") as target:
            while chunk := await upload.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise APIException(413, "file_too_large", "The uploaded file exceeds the configured size limit.")
                digest.update(chunk)
                target.write(chunk)
        _validate_content(temporary_path, extension, max_bytes)
        return StagedUpload(
            temporary_path=temporary_path,
            original_filename=filename,
            extension=extension,
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


async def store_uploads(
    uploads: list[UploadFile], session: Session, settings: Settings
) -> list[Document]:
    upload_dir = settings.resolved_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = upload_dir / f".staging-{uuid.uuid4().hex}"
    staging_dir.mkdir()
    staged: list[StagedUpload] = []
    stored_paths: list[Path] = []

    try:
        max_bytes = settings.max_upload_mb * 1024 * 1024
        for upload in uploads:
            staged.append(await _stage_one(upload, staging_dir, max_bytes))

        hashes = [item.sha256 for item in staged]
        if len(set(hashes)) != len(hashes):
            raise APIException(409, "duplicate_file", "The upload contains duplicate file content.")
        existing = set(
            session.scalars(select(Document.sha256).where(Document.sha256.in_(hashes))).all()
        )
        if existing:
            raise APIException(409, "duplicate_file", "A document with identical content is already stored.")

        documents: list[Document] = []
        for item in staged:
            stored_filename = f"{uuid.uuid4().hex}{item.extension}"
            destination = upload_dir / stored_filename
            os.replace(item.temporary_path, destination)
            stored_paths.append(destination)
            document = Document(
                original_filename=item.original_filename,
                stored_filename=stored_filename,
                extension=item.extension,
                media_type=item.media_type,
                size_bytes=item.size_bytes,
                sha256=item.sha256,
                processing_status="uploaded",
            )
            session.add(document)
            documents.append(document)

        session.commit()
        return documents
    except IntegrityError as exc:
        session.rollback()
        for stored_path in stored_paths:
            stored_path.unlink(missing_ok=True)
        raise APIException(409, "duplicate_file", "A document with identical content is already stored.") from exc
    except Exception:
        session.rollback()
        for stored_path in stored_paths:
            stored_path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def delete_stored_file(document: Document, settings: Settings) -> None:
    delete_document_file(document, settings)

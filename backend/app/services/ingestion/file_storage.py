"""Constrained local file storage operations."""

from app.core.config import Settings
from app.core.exceptions import APIException
from app.models.document import Document


def delete_document_file(document: Document, settings: Settings) -> None:
    upload_dir = settings.resolved_upload_dir.resolve()
    stored_path = (upload_dir / document.stored_filename).resolve()
    if stored_path.parent != upload_dir:
        raise APIException(500, "invalid_storage_reference", "The stored file reference is invalid.")
    try:
        stored_path.unlink(missing_ok=True)
    except OSError as exc:
        raise APIException(500, "storage_delete_failed", "The stored document could not be removed.") from exc

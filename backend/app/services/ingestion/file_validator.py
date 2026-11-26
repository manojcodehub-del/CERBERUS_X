"""Upload name, media type, signature, and container validation."""

import zipfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.services.ingestion.file_detector import SUPPORTED_MEDIA_TYPES, detect_extension, detect_signature


class FileValidationError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 415) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def validate_filename(filename: str | None) -> tuple[str, str, str, set[str]]:
    if not filename or filename in {".", ".."} or "\x00" in filename:
        raise FileValidationError("invalid_filename", "A valid filename is required.", 400)
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise FileValidationError("invalid_filename", "Folder paths are not allowed in uploaded filenames.", 400)
    if len(filename) > 255:
        raise FileValidationError("invalid_filename", "The filename exceeds 255 characters.", 400)
    try:
        extension = detect_extension(filename)
    except ValueError as exc:
        raise FileValidationError("unsupported_file_type", "This file extension is not supported.") from exc
    canonical_type, accepted_types = SUPPORTED_MEDIA_TYPES[extension]
    return filename, extension, canonical_type, accepted_types


def validate_content(path: Path, extension: str, max_uncompressed_bytes: int | None = None) -> None:
    if path.stat().st_size == 0:
        raise FileValidationError("empty_file", "Empty files cannot be uploaded.", 422)
    if not detect_signature(path, extension):
        raise FileValidationError("content_type_mismatch", "The file content does not match its filename type.")
    if extension in {".docx", ".xlsx"}:
        required = {"[Content_Types].xml", "word/document.xml"} if extension == ".docx" else {"[Content_Types].xml", "xl/workbook.xml"}
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                names = {entry.filename for entry in infos}
                expanded = sum(entry.file_size for entry in infos)
                unsafe = any(Path(entry.filename).is_absolute() or ".." in Path(entry.filename).parts for entry in infos)
                if not required.issubset(names) or unsafe:
                    raise FileValidationError("content_type_mismatch", "The Office document container is malformed.")
                if max_uncompressed_bytes and expanded > max_uncompressed_bytes * 20:
                    raise FileValidationError("file_too_large", "The Office document expands beyond the safety limit.", 413)
                if any(entry.file_size > 0 and entry.compress_size == 0 for entry in infos):
                    raise FileValidationError("content_type_mismatch", "The Office document container is malformed.")
        except (OSError, zipfile.BadZipFile) as exc:
            raise FileValidationError("content_type_mismatch", "The Office document container is malformed.") from exc
    elif extension in {".png", ".jpg", ".jpeg"}:
        try:
            with Image.open(path) as image:
                image.verify()
                width, height = image.size
                if width < 1 or height < 1 or width * height > 100_000_000:
                    raise FileValidationError("invalid_image", "Image dimensions exceed the supported safety limit.", 422)
        except (OSError, UnidentifiedImageError) as exc:
            raise FileValidationError("content_type_mismatch", "The image file is malformed.") from exc

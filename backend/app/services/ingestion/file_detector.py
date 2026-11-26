"""File type recognition from an allowed extension and file signature."""

from pathlib import Path

SUPPORTED_MEDIA_TYPES: dict[str, tuple[str, set[str]]] = {
    ".pdf": ("application/pdf", {"application/pdf"}),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"}),
    ".txt": ("text/plain", {"text/plain"}),
    ".csv": ("text/csv", {"text/csv", "application/csv", "application/vnd.ms-excel"}),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/vnd.ms-excel"}),
    ".png": ("image/png", {"image/png"}),
    ".jpg": ("image/jpeg", {"image/jpeg"}),
    ".jpeg": ("image/jpeg", {"image/jpeg"}),
}


def detect_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_MEDIA_TYPES:
        raise ValueError("unsupported_file_type")
    return extension


def detect_signature(path: Path, extension: str) -> bool:
    with path.open("rb") as source:
        header = source.read(16)
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension in {".docx", ".xlsx"}:
        return header.startswith(b"PK\x03\x04")
    if extension in {".txt", ".csv"}:
        return b"\x00" not in header or header.startswith((b"\xff\xfe", b"\xfe\xff"))
    return False

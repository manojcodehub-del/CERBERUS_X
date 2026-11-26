"""Plain text extraction preserving paragraph order."""

from pathlib import Path

from app.services.extraction.common import ExtractedItem


def extract_text(path: Path) -> list[ExtractedItem]:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        result: list[ExtractedItem] = []
        try:
            with path.open("r", encoding=encoding, newline=None) as source:
                for index, paragraph in enumerate(source):
                    paragraph = paragraph.rstrip("\r\n")
                    if paragraph.strip():
                        result.append(ExtractedItem("paragraph", paragraph, f"text:{encoding}", paragraph_index=index))
            return result
        except UnicodeDecodeError:
            continue
    raise ValueError("The text file encoding is not supported.")

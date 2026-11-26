"""Explicitly ingest files from one user-selected local dataset directory."""

import argparse
import mimetypes
from pathlib import Path

import httpx

SUPPORTED = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".png", ".jpg", ".jpeg"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir", type=Path, help="The specific local dataset directory to ingest.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Local CERBERUS-X API base URL.")
    args = parser.parse_args()
    root = args.dataset_dir.expanduser().resolve()
    if not root.is_dir():
        parser.error("dataset_dir must be an existing directory selected by the user")

    processed = skipped = failed = 0
    with httpx.Client(base_url=args.api_base.rstrip("/"), timeout=300) as client:
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                path.resolve().relative_to(root)
            except ValueError:
                skipped += 1
                print(f"SKIP outside dataset root: {path.name}")
                continue
            if path.suffix.lower() not in SUPPORTED:
                skipped += 1
                print(f"SKIP unsupported type: {path.name}")
                continue
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            try:
                with path.open("rb") as source:
                    uploaded = client.post("/api/documents/upload", files={"files": (path.name, source, content_type)})
                if uploaded.status_code == 409:
                    skipped += 1
                    print(f"SKIP duplicate: {path.name}")
                    continue
                uploaded.raise_for_status()
                document = uploaded.json()["items"][0]
                result = client.post(f"/api/documents/{document['id']}/process")
                result.raise_for_status()
                outcome = result.json()
                print(f"{outcome['status']}: {path.name} ({outcome['evidence_count']} evidence records)")
                processed += 1
            except (OSError, httpx.HTTPError, KeyError, ValueError) as exc:
                failed += 1
                print(f"FAILED: {path.name} ({type(exc).__name__})")
    print(f"Dataset run finished: processed={processed}, skipped={skipped}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

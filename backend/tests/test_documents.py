from sqlalchemy import select

from app.models.document import Document


def test_multiple_upload_list_detail_analytics_and_delete(client, test_app) -> None:
    response = client.post(
        "/api/documents/upload",
        files=[
            ("files", ("meeting-notes.txt", b"Project review notes", "text/plain")),
            ("files", ("budget.pdf", b"%PDF-1.7\nphase two sample", "application/pdf")),
        ],
    )

    assert response.status_code == 201
    uploaded = response.json()["items"]
    assert response.json()["total"] == 2
    assert {item["original_filename"] for item in uploaded} == {"meeting-notes.txt", "budget.pdf"}
    assert all(item["processing_status"] == "uploaded" for item in uploaded)

    with test_app.state.database.session_factory() as session:
        stored_documents = session.scalars(select(Document)).all()
        assert len(stored_documents) == 2
        stored_path = test_app.state.settings.resolved_upload_dir / next(
            row.stored_filename for row in stored_documents if row.id == uploaded[0]["id"]
        )
        assert all((test_app.state.settings.resolved_upload_dir / row.stored_filename).is_file() for row in stored_documents)

    listing = client.get("/api/documents")
    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    assert len(listing.json()["items"]) == 2

    document_id = uploaded[0]["id"]
    detail = client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == document_id
    assert "stored_filename" not in detail.json()

    analytics = client.get("/api/analytics").json()
    assert analytics["total_documents"] == 2
    assert analytics["uploaded_documents"] == 2
    assert analytics["total_evidence"] == 0

    deletion = client.delete(f"/api/documents/{document_id}")
    assert deletion.status_code == 204
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert not stored_path.exists()
    assert client.get("/api/documents").json()["total"] == 1


def test_duplicate_content_is_rejected_by_sha256(client) -> None:
    file_payload = [("files", ("source.txt", b"same source", "text/plain"))]

    first = client.post("/api/documents/upload", files=file_payload)
    second = client.post("/api/documents/upload", files=file_payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "duplicate_file"
    assert client.get("/api/documents").json()["total"] == 1


def test_invalid_extension_and_content_type_are_rejected(client) -> None:
    unsupported = client.post(
        "/api/documents/upload",
        files=[("files", ("script.exe", b"not executable", "application/octet-stream"))],
    )
    mismatched = client.post(
        "/api/documents/upload",
        files=[("files", ("notes.txt", b"text", "application/pdf"))],
    )
    invalid_signature = client.post(
        "/api/documents/upload",
        files=[("files", ("scan.png", b"not a png", "image/png"))],
    )

    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "unsupported_file_type"
    assert mismatched.status_code == 415
    assert invalid_signature.status_code == 415
    assert client.get("/api/documents").json()["total"] == 0


def test_traversal_name_is_rejected_and_upload_is_not_written(client, test_app) -> None:
    response = client.post(
        "/api/documents/upload",
        files=[("files", ("../outside.txt", b"private", "text/plain"))],
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_filename"
    assert client.get("/api/documents").json()["total"] == 0
    assert list(test_app.state.settings.resolved_upload_dir.iterdir()) == []


def test_oversized_upload_is_rejected_and_staging_is_cleaned(client, test_app) -> None:
    response = client.post(
        "/api/documents/upload",
        files=[("files", ("large.txt", b"x" * (1024 * 1024 + 1), "text/plain"))],
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert client.get("/api/documents").json()["total"] == 0
    assert list(test_app.state.settings.resolved_upload_dir.iterdir()) == []


def test_upload_file_count_limit_is_enforced(client, test_app) -> None:
    response = client.post(
        "/api/documents/upload",
        files=[
            ("files", (f"note-{index}.txt", f"text {index}".encode(), "text/plain"))
            for index in range(test_app.state.settings.max_upload_files + 1)
        ],
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_many_files"
    assert client.get("/api/documents").json()["total"] == 0
    assert list(test_app.state.settings.resolved_upload_dir.iterdir()) == []


def test_unknown_document_returns_404(client) -> None:
    response = client.get("/api/documents/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"

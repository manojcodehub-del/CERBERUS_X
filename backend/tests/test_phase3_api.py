import io
import shutil

from sqlalchemy import select

from app.models.claim import Claim
from app.models.document import Document
from app.models.evidence import Evidence


def _upload(client, filename: str, body: bytes, media_type: str) -> dict:
    response = client.post("/api/documents/upload", files=[("files", (filename, body, media_type))])
    assert response.status_code == 201, response.text
    return response.json()["items"][0]


def test_process_api_persists_evidence_claims_and_is_idempotent(client, test_app) -> None:
    text = "Approved project budget is ₹10,00,000. Invoice INV-2026-07 is paid on 2026-11-25; 5 units for Project ID CERB-20."
    document = _upload(client, "project.txt", text.encode("utf-8"), "text/plain")

    processed = client.post(f"/api/documents/{document['id']}/process")
    assert processed.status_code == 200, processed.text
    result = processed.json()
    assert result["status"] == "COMPLETED"
    assert result["evidence_count"] >= 1
    assert result["claim_count"] >= 4

    evidence_response = client.get(f"/api/documents/{document['id']}/evidence")
    assert evidence_response.status_code == 200
    evidence = evidence_response.json()["items"]
    assert evidence[0]["filename"] == "project.txt"
    assert evidence[0]["original_text"] == text
    assert evidence[0]["source_hash"] == document["sha256"]
    claim_types = {claim["claim_type"] for row in evidence for claim in row["claims"]}
    assert {"monetary_amount", "date", "invoice_number", "project_id", "quantity"}.issubset(claim_types)
    assert "approval_reference" not in claim_types

    before = len(evidence)
    again = client.post(f"/api/documents/{document['id']}/process")
    assert again.json()["status"] == "COMPLETED"
    assert again.json()["evidence_count"] == before
    assert client.get(f"/api/documents/{document['id']}/evidence").json()["total"] == before

    status = client.get(f"/api/documents/{document['id']}/status").json()
    assert status["status"] == "COMPLETED"
    assert status["job_status"] == "completed"
    with test_app.state.database.session_factory() as session:
        assert session.scalar(select(Document).where(Document.id == document["id"])).processing_status == "COMPLETED"
        assert session.scalar(select(Evidence.document_id).where(Evidence.document_id == document["id"])) is not None
        assert session.scalar(select(Claim.id).join(Evidence).where(Evidence.document_id == document["id"])) is not None


def test_processing_failure_is_persisted_and_reported(client, test_app) -> None:
    document = _upload(client, "lost.txt", b"A valid source that will be removed before processing.", "text/plain")
    with test_app.state.database.session_factory() as session:
        row = session.get(Document, document["id"])
        (test_app.state.settings.resolved_upload_dir / row.stored_filename).unlink()

    result = client.post(f"/api/documents/{document['id']}/process")
    assert result.status_code == 200
    assert result.json()["status"] == "VALIDATION_FAILED"
    assert "missing" in result.json()["error"]
    assert client.get(f"/api/documents/{document['id']}/status").json()["job_status"] == "failed"


def test_missing_document_process_and_evidence_routes_return_404(client) -> None:
    assert client.post("/api/documents/missing/process").status_code == 404
    assert client.get("/api/documents/missing/evidence").status_code == 404
    assert client.get("/api/documents/missing/status").status_code == 404


def test_empty_upload_is_rejected(client) -> None:
    response = client.post("/api/documents/upload", files=[("files", ("empty.txt", b"", "text/plain"))])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_file"


def test_office_format_processing_stores_table_cell_locations(client) -> None:
    import pandas as pd

    # Exercise upload, Office container validation, processing, and SQLite provenance together.
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([{"Project": "CERBERUS-X", "Budget": "₹10,00,000"}]).to_excel(writer, index=False, sheet_name="Budget")
    document = _upload(client, "budget.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    result = client.post(f"/api/documents/{document['id']}/process").json()
    assert result["status"] == "COMPLETED"
    records = client.get(f"/api/documents/{document['id']}/evidence").json()["items"]
    budget = next(item for item in records if item["original_text"] == "₹10,00,000")
    assert budget["sheet_name"] == "Budget"
    assert budget["cell_coordinate"] == "B2"
    assert budget["row_number"] == 2


def test_docx_upload_and_processing_extracts_paragraph(client) -> None:
    from docx import Document as DocxDocument

    stream = io.BytesIO()
    doc = DocxDocument()
    doc.add_paragraph("Invoice INV-2026-07 is pending approval.")
    doc.save(stream)
    document = _upload(client, "invoice.docx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    result = client.post(f"/api/documents/{document['id']}/process").json()
    assert result["status"] == "COMPLETED"
    evidence = client.get(f"/api/documents/{document['id']}/evidence").json()["items"]
    assert any(item["original_text"] == "Invoice INV-2026-07 is pending approval." for item in evidence)


def test_image_upload_reports_ocr_status_without_fabricating_text(client) -> None:
    from PIL import Image

    image = io.BytesIO()
    Image.new("RGB", (80, 40), "white").save(image, format="PNG")
    document = _upload(client, "scan.png", image.getvalue(), "image/png")
    result = client.post(f"/api/documents/{document['id']}/process").json()
    evidence = client.get(f"/api/documents/{document['id']}/evidence").json()["items"]
    if shutil.which("tesseract") is None:
        assert result["status"] == "OCR_UNAVAILABLE"
        assert any("Tesseract OCR is unavailable" in warning for warning in result["warnings"])
        assert not any(item["content_type"] == "ocr_text" for item in evidence)
    else:
        assert result["status"] in {"COMPLETED", "PARTIALLY_COMPLETED"}


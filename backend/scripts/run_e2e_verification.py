"""Repeatable Phase 7 API workflow using a temporary DB and real local Ollama."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


RESULT_PATH = ROOT / "docs" / "e2e_results.json"
SAMPLE_PATH = ROOT / "data" / "datasets" / "phase4_demo_synthetic_budget.txt"
EXPECTED_CLAIMS = {"INR 1,250,000", "INR 1,850,000"}
EXPECTED_OCR = "CERBERUS_X_TEST_SCAN_123"


def require_status(response, expected: int, step: str) -> dict:
    if response.status_code != expected:
        raise AssertionError(
            f"{step}: expected HTTP {expected}, received {response.status_code}: {response.text}"
        )
    return response.json() if response.content else {}


def build_pdf(source_text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    remaining = page.insert_textbox(
        pymupdf.Rect(48, 48, 548, 744),
        source_text,
        fontname="helv",
        fontsize=11,
        lineheight=1.25,
    )
    if remaining < 0:
        raise AssertionError("The sample dataset did not fit on the generated PDF page.")
    content = document.tobytes()
    document.close()
    return content


def build_scan() -> bytes:
    image = Image.new("RGB", (1400, 240), color="white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    try:
        font = ImageFont.truetype(str(font_path), 52) if font_path.exists() else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()
    draw.text((48, 80), EXPECTED_OCR, fill="black", font=font)
    from io import BytesIO

    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def source_location_present(claim: dict) -> bool:
    location = claim.get("source_location") or {}
    return any(location.get(key) is not None for key in (
        "page_number", "sheet_name", "row_number", "cell_coordinate",
        "paragraph_index", "table_index",
    ))


def run_e2e_workflow() -> dict:
    if not SAMPLE_PATH.is_file():
        raise FileNotFoundError(f"Required sample dataset is missing: {SAMPLE_PATH}")
    source_text = SAMPLE_PATH.read_text(encoding="utf-8").strip()
    if "DEMO-ALPHA" not in source_text or "INR 1,250,000" not in source_text:
        raise AssertionError("The sample dataset does not contain the expected DEMO-ALPHA budget claim.")

    RESULTS: dict[str, object] = {"sample_dataset": str(SAMPLE_PATH.relative_to(ROOT))}
    base_settings = get_settings()

    with tempfile.TemporaryDirectory(prefix="cerberus-phase7-e2e-") as temporary:
        work_dir = Path(temporary)
        database_path = work_dir / "cerberus_phase7_e2e.db"
        settings_values = base_settings.model_dump()
        settings_values.update({
            "database_url": f"sqlite:///{database_path.as_posix()}",
            "upload_dir": work_dir / "uploads",
            "processed_dir": work_dir / "processed",
            "max_upload_mb": 50,
            "max_upload_files": 10,
        })
        settings = Settings(_env_file=None, **settings_values)
        app = create_app(settings)

        with TestClient(app) as client:
            health = require_status(client.get("/api/health"), 200, "Health check")
            system = require_status(client.get("/api/system/status"), 200, "System status")
            if health.get("database") != "connected":
                raise AssertionError(f"Temporary SQLite database is not connected: {health}")
            RESULTS["step0_health"] = {"status": health.get("status"), "database": health.get("database"), "system": system}

            pdf_bytes = build_pdf(source_text)
            uploaded = require_status(
                client.post(
                    "/api/documents/upload",
                    files=[("files", ("phase7_demo_alpha_charter.pdf", pdf_bytes, "application/pdf"))],
                ),
                201,
                "PDF upload",
            )
            pdf_doc = uploaded["items"][0]
            pdf_id = pdf_doc["id"]
            RESULTS["step1_pdf_upload"] = {"document_id": pdf_id, "filename": pdf_doc["original_filename"]}

            extraction = require_status(
                client.post(f"/api/documents/{pdf_id}/process"), 200, "PDF processing"
            )
            if extraction["status"] != "COMPLETED" or extraction["evidence_count"] < 1:
                raise AssertionError(f"PDF extraction did not complete: {extraction}")
            RESULTS["step2_extraction"] = extraction

            evidence_payload = require_status(
                client.get(f"/api/documents/{pdf_id}/evidence"), 200, "PDF evidence"
            )
            evidence_items = evidence_payload["items"]
            sample_evidence = next(
                (item for item in evidence_items if "INR 1,250,000" in (item.get("original_text") or "")),
                None,
            )
            if sample_evidence is None or sample_evidence.get("page_number") != 1:
                raise AssertionError("The sample budget text or PDF page-1 provenance was not preserved.")
            RESULTS["step3_provenance"] = {
                "evidence_count": len(evidence_items),
                "evidence_id": sample_evidence["id"],
                "page_number": sample_evidence["page_number"],
                "source_text_contains_budget": True,
            }

            indexed = require_status(
                client.post("/api/embeddings/index", json={"document_ids": [pdf_id]}),
                200,
                "PDF embedding/index",
            )
            if indexed.get("status") != "completed" or indexed.get("generated_embeddings", 0) < 1:
                raise AssertionError(f"A fresh local embedding was not generated: {indexed}")
            embedding_status = require_status(
                client.get("/api/embeddings/status"), 200, "Embedding status"
            )
            if not embedding_status.get("embedding_model_installed") or embedding_status.get("indexed_chunks", 0) < 1:
                raise AssertionError(f"Local embedding index is not ready: {embedding_status}")
            RESULTS["step4_embedding"] = {
                "status": indexed["status"],
                "model": indexed["model"],
                "chunks": indexed["total_chunks"],
                "generated_embeddings": indexed["generated_embeddings"],
                "embedding_model_installed": embedding_status["embedding_model_installed"],
                "indexed_chunks": embedding_status["indexed_chunks"],
            }

            search = require_status(
                client.post(
                    "/api/search",
                    json={"query": "approved project budget for Project DEMO-ALPHA", "document_id": pdf_id, "top_k": 5},
                ),
                200,
                "Evidence search",
            )
            matching_search = next(
                (item for item in search["items"] if item["evidence_id"] == sample_evidence["id"]),
                None,
            )
            if matching_search is None:
                raise AssertionError("Scoped search did not return the source evidence containing the budget.")
            RESULTS["step5_search"] = {
                "retrieval_method": search["retrieval_method"],
                "result_count": len(search["items"]),
                "top_evidence_id": search["items"][0]["evidence_id"],
                "matched_sample_evidence_id": matching_search["evidence_id"],
            }

            answer = require_status(
                client.post(
                    "/api/ask",
                    json={"question": "What is the approved project budget for Project DEMO-ALPHA?", "document_id": pdf_id},
                ),
                200,
                "Grounded Q&A",
            )
            if answer.get("abstained") or not answer.get("citations"):
                raise AssertionError(f"Q&A did not return a supported answer and citation: {answer}")
            citation = next(
                (
                    item for item in answer["citations"]
                    if item["document_id"] == pdf_id
                    and item["evidence_id"] == sample_evidence["id"]
                    and item["page_number"] == 1
                    and "1,250,000" in (item.get("quoted_text") or "")
                ),
                None,
            )
            if citation is None:
                raise AssertionError("Q&A did not cite the correct sample PDF evidence and page.")
            RESULTS["step6_answer_citation"] = {
                "answer": answer["answer"],
                "model": answer["model_used"],
                "abstained": answer["abstained"],
                "citation": citation,
            }

            conflict_text = (
                "SYNTHETIC DEMONSTRATION CONFLICT â€” invented values for local testing only.\n"
                "Project ID: DEMO-ALPHA\n"
                "A later approved amendment sets the approved project budget for Project DEMO-ALPHA "
                "to INR 1,850,000.\n"
                "Approval date: 2026-11-25.\n"
                "Project status is APPROVED.\n"
            ).encode("utf-8")
            conflict_upload = require_status(
                client.post(
                    "/api/documents/upload",
                    files=[("files", ("phase7_demo_alpha_amendment.txt", conflict_text, "text/plain"))],
                ),
                201,
                "Conflicting TXT upload",
            )
            conflict_doc = conflict_upload["items"][0]
            conflict_id = conflict_doc["id"]
            conflict_processing = require_status(
                client.post(f"/api/documents/{conflict_id}/process"), 200, "Conflicting TXT processing"
            )
            if conflict_processing["status"] != "COMPLETED" or conflict_processing["evidence_count"] < 1:
                raise AssertionError(f"Conflicting TXT extraction did not complete: {conflict_processing}")
            conflict_evidence = require_status(
                client.get(f"/api/documents/{conflict_id}/evidence"), 200, "Conflicting TXT evidence"
            )["items"]
            if not any("INR 1,850,000" in (item.get("original_text") or "") for item in conflict_evidence):
                raise AssertionError("The second document's original conflicting amount was not preserved.")
            RESULTS["step7_conflict_source"] = {
                "document_id": conflict_id,
                "filename": conflict_doc["original_filename"],
                "status": conflict_processing["status"],
                "evidence_count": conflict_processing["evidence_count"],
            }

            conflict_index = require_status(
                client.post("/api/embeddings/index", json={"document_ids": [conflict_id]}),
                200,
                "Conflicting TXT embedding/index",
            )
            if conflict_index.get("status") != "completed":
                raise AssertionError(f"The conflicting document was not indexed: {conflict_index}")

            normalization = require_status(
                client.post("/api/claims/normalize", json={"document_ids": [pdf_id, conflict_id]}),
                200,
                "Claim normalization and conflict analysis",
            )
            normalized_sample_claims = require_status(
                client.get("/api/claims", params={"document_id": pdf_id, "normalized_only": "true"}),
                200,
                "Normalized sample claims",
            )["items"]
            sample_money = {
                item["value"]: item
                for item in normalized_sample_claims
                if item["claim_type"] == "monetary_amount"
            }
            if sample_money.get("INR 1,250,000", {}).get("project_identifier") != "DEMO-ALPHA":
                raise AssertionError("The alphabetic project identifier was not retained on the sample budget claim.")
            if sample_money.get("INR 1,250,000", {}).get("predicate") != "approved_budget":
                raise AssertionError("The sample's approved budget was normalized to the wrong field.")
            if sample_money.get("INR 1,400,000", {}).get("predicate") != "procurement_estimate":
                raise AssertionError("The sample's explicitly unapproved vendor quote was misclassified.")
            conflicts = require_status(
                client.get("/api/contradictions?limit=200"), 200, "Contradiction list"
            )["items"]
            target_pair = None
            for finding in conflicts:
                claim_a, claim_b = finding.get("claim_a"), finding.get("claim_b")
                if not claim_a or not claim_b:
                    continue
                documents = {claim_a.get("document_id"), claim_b.get("document_id")}
                values = {claim_a.get("value"), claim_b.get("value")}
                if documents == {pdf_id, conflict_id} and values == EXPECTED_CLAIMS:
                    target_pair = finding
                    break
            if target_pair is None:
                raise AssertionError(
                    "Contradiction analysis did not compare the sample's INR 1,250,000 claim "
                    "with the amendment's INR 1,850,000 claim."
                )
            claim_a, claim_b = target_pair["claim_a"], target_pair["claim_b"]
            if not source_location_present(claim_a) or not source_location_present(claim_b):
                raise AssertionError("The compared original claims are missing source locations.")
            detailed_conflict = require_status(
                client.get(f"/api/contradictions/{target_pair['id']}"),
                200,
                "Contradiction detail",
            )
            RESULTS["step8_conflict_analysis"] = {
                "normalized_claims": normalization["normalized"],
                "classification": detailed_conflict["classification"],
                "conflict_id": detailed_conflict["id"],
                "claims": [
                    {
                        "document_id": item["document_id"],
                        "filename": item["filename"],
                        "original_value": item["value"],
                        "source_location": item["source_location"],
                        "evidence_id": item["evidence_id"],
                    }
                    for item in (detailed_conflict["claim_a"], detailed_conflict["claim_b"])
                ],
            }

            reliability = require_status(
                client.get("/api/reliability/sources"), 200, "Source reliability"
            )
            reliability_by_id = {item["document_id"]: item for item in reliability["items"]}
            if pdf_id not in reliability_by_id or conflict_id not in reliability_by_id:
                raise AssertionError("Reliability results are missing one or both E2E sources.")
            if not all(reliability_by_id[doc_id]["explanation"] for doc_id in (pdf_id, conflict_id)):
                raise AssertionError("Reliability explanations were not returned for both sources.")
            RESULTS["step9_reliability"] = {
                "sources": [
                    {
                        "document_id": reliability_by_id[doc_id]["document_id"],
                        "filename": reliability_by_id[doc_id]["filename"],
                        "score": reliability_by_id[doc_id]["heuristic_score"],
                        "approval_status": reliability_by_id[doc_id]["approval_status"],
                        "explanation": reliability_by_id[doc_id]["explanation"],
                        "criteria": reliability_by_id[doc_id]["criteria"],
                    }
                    for doc_id in (pdf_id, conflict_id)
                ],
                "score_notice": reliability["score_notice"],
            }

            graph = require_status(
                client.get("/api/knowledge-graph?limit=500"), 200, "Knowledge graph"
            )
            document_nodes = {
                node["document_id"] for node in graph["nodes"]
                if node.get("type") == "document" and node.get("document_id")
            }
            if not {pdf_id, conflict_id}.issubset(document_nodes):
                raise AssertionError("The graph is missing one or both E2E documents.")
            conflict_claim_ids = {claim_a["id"], claim_b["id"]}
            if not any(node.get("claim_id") in conflict_claim_ids for node in graph["nodes"]):
                raise AssertionError("The graph does not contain either original conflicting claim.")
            RESULTS["step10_graph"] = {
                "node_count": graph["node_count"],
                "edge_count": graph["edge_count"],
                "sample_documents_present": True,
                "conflicting_claim_nodes_present": True,
            }

            verification = require_status(
                client.post(
                    "/api/verification/analyze",
                    json={
                        "question": "What approved budget is recorded for Project DEMO-ALPHA?",
                        "document_ids": [pdf_id, conflict_id],
                        "top_k": 8,
                    },
                ),
                200,
                "Evidence verification API",
            )
            if not verification.get("evidence") or not verification.get("comparison_findings"):
                raise AssertionError("Verification did not return the source evidence and comparison findings.")
            RESULTS["step11_verification"] = {
                "abstained": verification["abstained"],
                "conflict_assessment": verification["conflict_assessment"],
                "evidence_count": len(verification["evidence"]),
                "comparison_count": len(verification["comparison_findings"]),
                "retrieval_method": verification["retrieval_method"],
            }

            investigation = require_status(
                client.post(
                    "/api/investigations",
                    json={
                        "title": "DEMO-ALPHA budget investigation",
                        "question": "What approved budget is recorded for Project DEMO-ALPHA?",
                        "document_ids": [pdf_id, conflict_id],
                        "top_k": 12,
                    },
                ),
                201,
                "Investigation creation",
            )
            investigation_id = investigation["id"]
            investigation = require_status(
                client.post(f"/api/investigations/{investigation_id}/generate", json={}),
                200,
                "Investigation report generation",
            )
            report = investigation.get("report") or {}
            if report.get("scope", {}).get("document_count") != 2:
                raise AssertionError("The investigation report did not preserve both selected source documents.")
            if not report.get("relevant_evidence") or not report.get("source_reliability"):
                raise AssertionError("The investigation report omitted retrieved source passages or reliability explanations.")
            if not report.get("supporting_evidence") or not report.get("opposing_evidence"):
                raise AssertionError("The local stance model did not identify both supporting and opposing source passages.")
            report_conflict = next((item for item in report.get("contradictions", [])
                                    if item.get("claim_a") and item.get("claim_b")
                                    and {item["claim_a"].get("document_id"), item["claim_b"].get("document_id")} == {pdf_id, conflict_id}
                                    and {item["claim_a"].get("value"), item["claim_b"].get("value")} == EXPECTED_CLAIMS), None)
            if report_conflict is None:
                raise AssertionError("The investigation report omitted the genuine cross-document budget conflict and its original claims.")
            if not all(source_location_present(report_conflict[side]) for side in ("claim_a", "claim_b")):
                raise AssertionError("The report conflict is missing original source locations.")
            if not report.get("conclusion", {}).get("abstained"):
                raise AssertionError("The investigation did not abstain despite the unresolved conflicting budget claims.")
            report_pdf = client.get(f"/api/investigations/{investigation_id}/report.pdf")
            if report_pdf.status_code != 200 or not report_pdf.content.startswith(b"%PDF"):
                raise AssertionError(f"Investigation PDF export failed: HTTP {report_pdf.status_code}")
            RESULTS["step12_investigation_report"] = {
                "investigation_id": investigation_id,
                "scope_document_count": report["scope"]["document_count"],
                "retrieved_evidence_count": len(report["relevant_evidence"]),
                "supporting_passages": len(report["supporting_evidence"]),
                "opposing_passages": len(report["opposing_evidence"]),
                "conflict_id": report_conflict["id"],
                "conflict_classification": report_conflict["classification"],
                "conclusion_abstained": report["conclusion"]["abstained"],
                "pdf_bytes": len(report_pdf.content),
            }
            image_upload = require_status(
                client.post(
                    "/api/documents/upload",
                    files=[("files", ("phase7_ocr_test.png", build_scan(), "image/png"))],
                ),
                201,
                "OCR image upload",
            )
            image_id = image_upload["items"][0]["id"]
            image_processing = require_status(
                client.post(f"/api/documents/{image_id}/process"), 200, "OCR image processing"
            )
            image_evidence = require_status(
                client.get(f"/api/documents/{image_id}/evidence"), 200, "OCR image evidence"
            )["items"]
            recognized_text = " ".join(item.get("original_text") or "" for item in image_evidence)
            expected_text_found = EXPECTED_OCR.casefold() in recognized_text.casefold()
            ocr_working = image_processing["status"] == "COMPLETED" and expected_text_found
            if image_processing["status"] == "COMPLETED" and not expected_text_found:
                raise AssertionError(
                    "Image processing reported completion but did not recognize the actual test phrase."
                )
            RESULTS["image_ocr_test"] = {
                "status": image_processing["status"],
                "ocr_working": ocr_working,
                "expected_text_found": expected_text_found,
                "warnings": image_processing.get("warnings", []),
                "recognized_text": recognized_text,
            }

        with TestClient(create_app(settings)) as restarted_client:
            restarted_health = require_status(
                restarted_client.get("/api/health"), 200, "Health check after app restart"
            )
            restarted_docs = require_status(
                restarted_client.get("/api/documents?limit=20"), 200, "Documents after app restart"
            )["items"]
            persisted_ids = {item["id"] for item in restarted_docs}
            if not {pdf_id, conflict_id, image_id}.issubset(persisted_ids):
                raise AssertionError("Uploaded documents did not persist after recreating the application.")
            persisted_investigation = require_status(
                restarted_client.get(f"/api/investigations/{investigation_id}"),
                200,
                "Investigation after app restart",
            )
            if persisted_investigation.get("report") != report:
                raise AssertionError("The saved investigation report did not persist after recreating the application.")
            persisted_pdf = restarted_client.get(f"/api/investigations/{investigation_id}/report.pdf")
            if persisted_pdf.status_code != 200 or not persisted_pdf.content.startswith(b"%PDF"):
                raise AssertionError("The saved investigation PDF could not be exported after application restart.")
            persisted_evidence = require_status(
                restarted_client.get(f"/api/documents/{pdf_id}/evidence"),
                200,
                "Evidence after app restart",
            )["items"]
            persisted_embeddings = require_status(
                restarted_client.get("/api/embeddings/status"),
                200,
                "Embedding status after app restart",
            )
            persisted_graph = require_status(
                restarted_client.get("/api/knowledge-graph?limit=500"),
                200,
                "Graph after app restart",
            )
            if not persisted_evidence or not persisted_embeddings.get("indexed_chunks") or not persisted_graph.get("edge_count"):
                raise AssertionError("Evidence, embeddings, or graph edges were not present after restart.")
            RESULTS["step13_restart_persistence"] = {
                "health": restarted_health["status"],
                "documents": len(persisted_ids),
                "sample_evidence_records": len(persisted_evidence),
                "indexed_chunks": persisted_embeddings["indexed_chunks"],
                "graph_nodes": persisted_graph["node_count"],
                "graph_edges": persisted_graph["edge_count"],
            }

        connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
        try:
            counts = {
                "questions": connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
                "answer_citations": connection.execute("SELECT COUNT(*) FROM answer_citations").fetchone()[0],
                "embedding_chunks": connection.execute("SELECT COUNT(*) FROM embedding_chunks").fetchone()[0],
            }
        finally:
            connection.close()
        if counts["questions"] < 1 or counts["answer_citations"] < 1 or counts["embedding_chunks"] < 1:
            raise AssertionError(f"Question, citation, or embedding rows were not persisted: {counts}")
        RESULTS["step14_persisted_rows"] = counts

    RESULT_PATH.write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(RESULTS, indent=2, ensure_ascii=False))
    print(f"\nE2E workflow passed. Results written to {RESULT_PATH}")
    if RESULTS["image_ocr_test"]["ocr_working"]:
        print("Image OCR passed by recognizing the expected text.")
    else:
        print("Image OCR is not reported as working; see the recorded engine status and warning.")


if __name__ == "__main__":
    run_e2e_workflow()




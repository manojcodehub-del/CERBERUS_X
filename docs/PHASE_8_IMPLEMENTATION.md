# CERBERUS-X Phase 8 Implementation

**Status:** Phase 8 implementation is present; automated tests/build pass. Real-model E2E and disconnected/offline verification remain incomplete.
**Audit date:** 2026-11-25

## Pre-change audit

The Phase 7 reports and repository were inspected before source changes. The project is a React/Vite frontend with a FastAPI backend, SQLAlchemy/SQLite persistence, and loopback Ollama models. Phase 7 records 53 backend tests passing, one Tesseract-dependent skip, a passing frontend production build, and a real local PDF-to-citation/conflict E2E run. The host was not physically disconnected, so offline readiness remains unverified. Tesseract and the optional local projector GLB are absent.

### Reusable APIs and pipelines

- Document upload, validation, processing, and page/sheet/paragraph provenance: `/api/documents/*`.
- Local embedding and hybrid retrieval: `/api/embeddings/index`, `/api/embeddings/status`, `/api/search`, and `/api/retrieval/status`. The retrieval service can use semantic-plus-keyword vectors or an explicit keyword fallback.
- Local Qwen answering validates citation IDs and exact source quotes before persisting citations; it abstains if evidence is weak, unavailable, conflicting, or citations fail validation.
- Deterministic claim normalization, contradiction comparison, source reliability evaluation, and verification are implemented in `services/normalization`, `services/contradiction`, `services/reliability`, and `services/verification`.
- Conflict findings preserve both claim/evidence IDs, source locations, original/normalized values, classification, explanation, confidence note, and review status/history. Existing classes include confirmed/potential conflict, temporal difference, category mismatch, unit mismatch, unresolved, and no-conflict outcomes. Currency conversion and common physical-unit normalization are not implemented; possible duplicate text is only handled by reliability fingerprints.
- The SQLite knowledge graph persists document/evidence/claim/conflict/project/person/organization nodes and evidence-backed edges. The React UI has 3D and React Flow 2D views with node inspection; event nodes are not currently created.
- Reliability & settings already serves as the diagnostics screen for database, local model/index, OCR, processing, and offline-not-verified state. It does not show free local storage.

### Missing Phase 8 capabilities

- No investigation model, create/list/detail/generate API, investigation report snapshot, or report PDF export.
- No frontend investigation workspace or saved investigation navigation.
- No explicit support/opposition evidence classification scoped to an investigation question.
- No normalized canonical conversion for common physical units; no possible-duplicate conflict finding.
- No event nodes in the persisted graph.
- No available-storage diagnostic.

### Persistence and testing constraints

The database creates ORM tables and applies additive SQLite column migrations at startup. New functionality must preserve existing rows and use additive tables/columns only. Phase 7's configured DB counts and previous test side effects are documented in `PHASE_7_AUDIT.md`; Phase 8 API tests must use the temporary database fixture. No frontend test runner is configured.

### Phase 8 implementation plan

1. Add an additive persisted investigation record and validated create/list/read/generate/PDF-export endpoints. Compose existing retrieval, verification, normalized claims, conflicts, source evaluations, graph relationships, and citation-validated local Qwen answers. Store an evidence-linked structured report and abstain when evidence cannot support a conclusion.
2. Add a React investigation workspace with document scope selection, saved investigations, evidence/claim/conflict/reliability sections, provenance navigation, loading/error/empty states, and local PDF export.
3. Extend the existing deterministic conflict engine carefully for normalized common physical units and possible textual duplicates without converting currencies using unstated exchange rates or treating category/time differences as direct contradictions.
4. Add evidence-linked event graph nodes and surface them in the existing lightweight graph and inspector.
5. Extend the existing diagnostics page with real local free-storage information while keeping offline readiness explicitly `not verified` unless an actual disconnected run is performed.
6. Add temporary-database backend API tests and an isolated E2E runner covering multiple documents, generated report/PDF, graph, and restart persistence. Re-run backend tests, Python compilation, and frontend production build.


## Phase 8 implementation and final audit (2026-11-26)

### Implemented

- Added an additive SQLite `investigations` table with create/list/detail/generate endpoints. Investigation documents and report snapshots persist across application restarts; existing tables and records were not cleared.
- Reused existing retrieval, verification, deterministic claims, contradiction, reliability, graph, and exact-quote citation services. Retrieval can be scoped to selected document IDs; an explicit whole-collection scope remains available.
- Added local-model support/opposition/context classification for retrieved passages. A stance is retained only when its evidence ID belongs to the retrieved set and its quote is an exact substring of that evidence. Citation validation does not override an opposing stance. When local answer generation is unavailable, the report preserves retrieved records and explicitly abstains.
- Added a saved Investigation Workspace with loading, error, empty, selected-document, report, and PDF-export states. Its report presents question, executive summary, supporting and opposing passages/claims, comparison findings, source-reliability explanations, missing-evidence notes, conclusion, and limitations. Source actions open original documents.
- Added local PyMuPDF PDF export from the saved report. PDF content includes source identifiers and available page/sheet/row/cell/paragraph/table locations, original claim text, normalized values, conflict explanations, reliability notes, abstention state, and limitations.
- Extended deterministic comparisons with canonical common physical units and a `POSSIBLE_DUPLICATE` review result. A duplicate candidate is explicitly not a contradiction and does not block verification. Currency markers and scales normalize to a canonical number/currency; currencies are not converted using exchange rates. Existing date, time-period, category, and unit mismatch outcomes remain reviewable and do not select a winning source.
- Added dated event graph nodes linked to claims and original evidence. Evidence graph nodes now include filename and page/sheet/row/cell/paragraph/table provenance. Conflict and possible-duplicate relationships are distinct.
- Extended system diagnostics with measured free bytes on the upload volume. Offline readiness remains `not_verified`; local model reachability and OCR availability use actual backend status.
- Extended the existing isolated real-model E2E runner with investigation scope, support/opposition, conflict provenance, report PDF, and restart-persistence checks. It continues to use a temporary database and temporary uploads.

### Final verification

- Full backend suite: **61 passed, 2 skipped**. The skips are the opt-in live Ollama test (not enabled) and the Tesseract integration prerequisite (Tesseract was not found on PATH). One Starlette/httpx deprecation warning remains.
- Python `compileall` passed for `backend/app`, `backend/scripts`, and `backend/tests`.
- Frontend `npm run build` passed and produced the investigation page chunk. Vite warns that the existing `constants` chunk is about 919.55 kB minified / 243.20 kB gzip.
- The isolated real-model runner was attempted on 2026-11-26. It successfully uploaded and extracted the generated sample PDF and retained page-level evidence, then embedding/indexing returned HTTP 503 (`ollama_unavailable`) because the loopback Ollama endpoint was not reachable. The Phase 8 report, conflict workflow, PDF export, and live-model stance classification were therefore not exercised in this attempt. The previous Phase 7 E2E success is historical and does not verify Phase 8.
- No physical internet-disconnected run or browser-level UI/WebGL interaction was performed. The UI is production-build verified; live browser behavior remains unverified.
- The Phase 8 tests use temporary SQLite databases. No configured project database or existing user document was cleared or intentionally modified by these tests.

### Remaining readiness boundary

Phase 8 APIs, persistence, local report generation logic, provenance mapping, and PDF generation are covered by automated tests. Full demonstration readiness still depends on a reachable local Ollama service with the configured chat and embedding models installed, followed by a successful run of `backend/scripts/run_e2e_verification.py`. Image OCR requires the separate Tesseract executable. Offline readiness is not claimed until the real workflow is repeated while disconnected.

See [`PHASE_8_TEST_REPORT.md`](PHASE_8_TEST_REPORT.md), [`INVESTIGATION_WORKFLOW.md`](INVESTIGATION_WORKFLOW.md), [`OFFLINE_VERIFICATION.md`](OFFLINE_VERIFICATION.md), and [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

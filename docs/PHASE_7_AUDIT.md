# CERBERUS-X Phase 7 Audit Report

**Audit date:** 2026-11-25  
**Repository:** `C:\Users\manoj\OneDrive\Documents\ChatGPT\CERBERUS_X\CERBERUS-X`  
**Audit stage:** Pre-source-change baseline

## Scope and method

Inspected the repository file inventory, FastAPI route modules, SQLAlchemy models and startup schema migration, frontend routes/pages/API calls, installed local runtimes, current SQLite database metadata, and the existing end-to-end artifact. Ran the backend test suite, Python compilation, and frontend production build. Checked the local API and Ollama service over loopback. No source code had been changed when these findings were recorded.

## Architecture found

- **Backend:** Python 3.11 virtual environment, FastAPI, SQLAlchemy, SQLite. Route modules cover health/system, documents, analytics, embeddings/retrieval/search/answers, claims, contradictions, source reliability, knowledge graph, and verification.
- **Frontend:** React/Vite application with six hash-routed pages: Dashboard, Document explorer, AI intelligence, Contradiction centre, Knowledge graph, and Reliability & settings. Page data and actions use the shared local API client; no fake-data source was found in those page flows. The API base defaults to `http://127.0.0.1:8000` and can be overridden with `VITE_API_BASE_URL`.
- **Persistence:** 15 ORM tables cover documents, evidence, processing jobs, claims, contradictions/resolution history, source evaluations, graph nodes/edges, embedding chunks/cache, questions/citations, entities, and relationships. Schema evolution is implemented as additive SQLite column checks in `backend/app/database/session.py`; there is no versioned migration directory.
- **Ingestion/security:** Validators and storage services handle PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, and JPEG. Existing tests cover invalid formats, size limits, and traversal attempts. SQLite is the configured local store; Ollama client is configured for loopback.

## Current stored data

Read-only inspection of `data/cerberus_x.db` found 15 tables and these rows: 9 documents, 23 evidence records, 18 processing jobs, 52 claims, 3 contradictions, 0 conflict-resolution records, 8 source evaluations, 21 embedding chunks, 14 cached vectors, 6 questions, 6 citations, 90 knowledge-graph nodes, and 163 graph edges. The database includes a processed sample budget text, processed Phase 7 PDF/TXT fixtures, and an image fixture whose processing status is `OCR_UNAVAILABLE`. The user database was not reset.

## Frontend/backend integration inventory

- Dashboard: live analytics, system status, embedding/retrieval status, recent documents.
- Documents: upload, list, delete, process, inspect evidence and provenance.
- Intelligence: local retrieval status and `POST /api/ask` with citations.
- Contradictions: list/filter and human-review status updates.
- Knowledge graph: persisted graph and entity-neighborhood endpoints; 3D view plus React Flow 2D view.
- Reliability & settings: source evaluations and system/embedding/retrieval/analytics status.

## Pre-change verification results

- Backend: **51 passed, 2 skipped** in 30.85 seconds. Skips are the opt-in live Ollama integration and Tesseract-dependent OCR integration; the live Ollama service is available but the opt-in test was not enabled in this baseline run.
- Python compilation: `compileall` completed without reported errors.
- Frontend: `npm run build` completed successfully. Vite reported a minified chunk of about 920 KB (243 KB gzip), which is a bundle-size optimization opportunity. No frontend test script is configured.
- Local API: `GET /api/health` returned `status=ok` and `database=connected`.
- Local Ollama: reachable on loopback; `qwen3.5:4b` and `nomic-embed-text:latest` are installed.
- Tesseract: executable is absent from PATH. The existing image test correctly records `OCR_UNAVAILABLE`; image OCR is **not verified as working**.
- Local hologram GLB: `frontend/public/models/hologram-projector.glb` is absent. The UI source includes a procedural projector and a CSS 2D fallback; browser-level WebGL failure behavior remains to be exercised.
- Offline mode: application configuration and the Ollama client are local/loopback-oriented, but an internet-disconnected runtime test has not yet been performed.

## Gaps to carry into Phase 7

1. Refresh the stale claims in this report's predecessor and produce current E2E/offline/limitations/demo reports.
2. Run the full live-model E2E flow and endpoint smoke checks against the installed local Ollama models, while keeping OCR success unclaimed unless Tesseract actually processes the fixture.
3. Verify the React Three Fiber fallback and reduced-motion behavior in a browser; document the missing optional GLB asset.
4. Review file validation, path handling, API constraints, and persistence/restart behavior against implementation and tests.
5. Reduce or explain the production chunk-size warning if a low-risk split is available.
6. Report the offline test boundary accurately if the host's network cannot be safely disconnected for the session.

## Baseline preservation note

The workspace Git metadata reports no commits yet and the project directory appears untracked. Treat every existing file and the current SQLite database as user-owned; do not use Git reset/clean or destructive database operations.


## Phase 7 completion results

**Review date:** 2026-11-25

### Corrections and integration work

- Added an explicit **Index** action in the document explorer using `POST /api/embeddings/index` and reporting the real local generated/reused vector counts.
- Added hybrid evidence search to Intelligence using `POST /api/search`, showing actual matched evidence, source locations, retrieval method, diagnostics, and a link to the source document.
- Added **Analyze new claims** to the Contradiction centre using `POST /api/claims/normalize`; the UI reports normalization, new findings, and graph counts returned by the backend.
- Corrected deterministic claim normalization so alphanumeric project identifiers such as `DEMO-ALPHA` retain their project context across evidence rows, and a vendor quotation explicitly described as not approved is not classified as the approved budget.
- Replaced the former broad, live-database E2E runner with a repeatable workflow using a temporary SQLite database and temporary upload storage. Full results are in [`END_TO_END_TEST_REPORT.md`](END_TO_END_TEST_REPORT.md) and [`e2e_results.json`](e2e_results.json).

### Final verification

- Backend suite with live local Ollama enabled: **53 passed, 1 skipped**. The skipped case requires the Tesseract executable, which is missing. One third-party Starlette/httpx deprecation warning was emitted.
- Python compilation: passed (`python -m compileall -q app tests`).
- Frontend production build: passed. Vite still warns about the 919.55 kB minified `constants` chunk (243.20 kB gzip). There is no configured frontend test script.
- Isolated real-model end-to-end workflow: passed. PDF extraction and page provenance, local embeddings, hybrid retrieval, local Qwen citation, conflict analysis, source explanations, graph, verification abstention, and persistence after application recreation all passed.
- Read-only smoke check: 16 critical GET routes returned HTTP 200 against the running local API.
- Upload tests cover duplicate hashes, invalid extension/media types and signatures, path-traversal names, file size limits, malformed Office containers, and OCR-unavailable handling. The complete backend suite passed.
- Static hologram review found local optional GLB loading with procedural fallback, WebGL fallback content, reduced-motion handling, bounded DPR/particles, no expensive scene shadows, and a React Flow 2D graph mode. Browser behavior was not exercised because the browser automation runtime was unavailable; the GLB file itself is absent.
- OCR test outcome is explicitly `OCR_UNAVAILABLE`; no OCR success is claimed.
- Offline status remains **not verified** because the host was not disconnected from the internet. Local API/model use and source endpoints are documented in [`OFFLINE_VERIFICATION.md`](OFFLINE_VERIFICATION.md).

### Current configured database state

A read-only count of `data/cerberus_x.db` after the earlier legacy-run side effect found: 10 documents, 24 evidence records, 22 processing jobs, 60 claims, 10 contradictions, 10 source evaluations, 22 embedding chunks, 14 cached vectors, 7 questions, 7 citations, 109 graph nodes, and 213 graph edges. These are user/project data and were preserved. The initial legacy E2E attempt added one generated Phase 7 PDF and related processing, answer, and conflict records to this database before the runner was isolated; the replacement runner uses a separate temporary database.

### Remaining gaps

Physical offline operation, visual browser behavior (including WebGL failure and responsive/reduced-motion rendering), direct loading of the absent optional GLB, and image OCR remain unverified or unavailable. The precise boundaries and current limitations are recorded in [`OFFLINE_VERIFICATION.md`](OFFLINE_VERIFICATION.md) and [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

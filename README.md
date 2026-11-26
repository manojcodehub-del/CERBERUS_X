# CERBERUS-X

CERBERUS-X is an offline-first multimodal evidence intelligence system. The repository is being built in reviewable phases so that document processing, citations, contradiction handling, and local AI are backed by real implementations.

## Current phase

Phase 8 adds a persisted Investigation Workspace to the existing React/Vite, FastAPI, SQLite, and local Ollama architecture. Investigations can scope one or more documents or the full collection, gather evidence and claims, keep supporting and opposing passages separate, show source reliability and contradiction provenance, abstain when evidence conflicts or local answer generation is unavailable, and export the saved report as a local PDF. The graph includes dated event nodes and full evidence locations; diagnostics report free storage and keep offline readiness `not_verified` until a disconnected run is completed.

The backend suite (61 passed, 2 skipped), Python compilation, and frontend production build passed on 2026-11-26. The isolated real-model E2E run processed the sample PDF but stopped at embedding/index because the local Ollama endpoint was unavailable. Thus the Phase 8 real-model investigation workflow and offline behavior are not yet verified. Tesseract is absent from PATH, the optional projector GLB is not included, and browser-level behavior was not visually tested. See the [Phase 8 implementation audit](docs/PHASE_8_IMPLEMENTATION.md), [investigation workflow](docs/INVESTIGATION_WORKFLOW.md), [test report](docs/PHASE_8_TEST_REPORT.md), [offline report](docs/OFFLINE_VERIFICATION.md), [limitations](docs/KNOWN_LIMITATIONS.md), and [five-minute demo guide](docs/HACKATHON_DEMO_GUIDE.md).
## Requirements

- Windows 10/11 with PowerShell
- Python 3.11 (use the same interpreter to create the backend environment)
- Node.js 20.19+ or 22.12+
- Internet access for the initial package installation only

The Tesseract Python wrapper is installed, but the Tesseract OCR executable was not found during workspace inspection. Searchable PDFs and text-based formats work without it. Scanned PDF pages and images report `OCR_UNAVAILABLE` or `PARTIALLY_COMPLETED` until a local OCR executable is installed and configured. Internet disconnection has not yet been tested; do not treat this phase as proof of offline operation.

## First-time setup (PowerShell)

The VS Code workspace root is `CERBERUS_X`; the application project is inside its `CERBERUS-X` subfolder. From the workspace root, enter the project folder first:

```powershell
Set-Location .\CERBERUS-X
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
& "C:\Users\manoj\AppData\Local\Programs\Python\Python311\python.exe" -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location .\frontend
npm install
Set-Location ..
```

If Python 3.11 is installed elsewhere, replace the interpreter path above with its full path:

```powershell
& "C:\Path\To\Python311\python.exe" -m venv backend\.venv
```

## Run locally

Open two PowerShell terminals at the workspace root (`CERBERUS_X`).

Terminal 1, start the API:

```powershell
Set-Location .\CERBERUS-X
& .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\backend --host 127.0.0.1 --port 8000 --reload
```

Terminal 2, start the frontend:

```powershell
Set-Location .\CERBERUS-X\frontend
npm run dev
```

Open <http://127.0.0.1:5173>. Use **Check API** to make a real request to `GET /api/health`. The API also provides interactive endpoint documentation at <http://127.0.0.1:8000/docs>.

## Database

On backend startup, SQLAlchemy creates any missing tables in the configured SQLite database. The default database is `data/cerberus_x.db`; upload and processed files are stored under `data/uploads` and `data/processed`. These local files are excluded from Git. No manual SQL setup is required.

## API endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Checks the API and SQLite connection. |
| GET | `/api/system/status` | Reports database/storage readiness, document processing availability, and local OCR readiness. |
| GET | `/api/documents` | Lists stored document metadata (`limit` and `offset` supported). |
| POST | `/api/documents/upload` | Validates and stores one or more supported files. Multipart field: `files`. |
| GET | `/api/documents/{document_id}` | Returns metadata for one stored document. |
| POST | `/api/documents/{document_id}/process` | Extracts the local document, persists evidence and candidate claims, and returns the real processing status. |
| GET | `/api/documents/{document_id}/evidence` | Returns stored evidence, source locations, and linked candidate claims. |
| GET | `/api/documents/{document_id}/status` | Returns current document and latest processing job state. |
| DELETE | `/api/documents/{document_id}` | Removes its local file and metadata. |
| POST | `/api/embeddings/index` | Chunks processed evidence and creates/reuses local Ollama vectors. |
| GET | `/api/embeddings/status` | Reports Ollama and local embedding-index status. |
| GET | `/api/retrieval/status` | Reports the active retrieval configuration and local counts. |
| POST | `/api/search` | Hybrid semantic/keyword evidence retrieval; keyword fallback is explicit. |
| POST | `/api/ask` | Answers from retrieved evidence through the configured local chat model and verifies citations. |
| POST | `/api/documents/{document_id}/reindex` | Rebuilds that document's chunks using local cached embeddings when possible. |
| GET | `/api/analytics` | Returns live document, evidence, contradiction, and job counts. |
| GET | `/api/claims` | Lists original candidate claims with normalized fields and evidence provenance. |
| POST | `/api/claims/normalize` | Deterministically normalizes unprocessed claims (or requested claim/document IDs), detects comparisons, and updates the graph. |
| GET | `/api/contradictions` | Lists conflict findings; supports classification, status, document, limit, and offset filters. |
| GET | `/api/contradictions/{conflict_id}` | Returns both assertions and their evidence references. |
| POST | `/api/contradictions/{conflict_id}/resolve` | Records an open, under-review, resolved, or dismissed status plus append-only review history. |
| GET | `/api/reliability/sources` | Evaluates sources and explains each heuristic criterion and weight. |
| GET | `/api/reliability/sources/{document_id}` | Returns one source evaluation. |
| POST | `/api/verification/analyze` | Retrieves local evidence, claims, conflicts, source evaluations, and graph relationships; abstains when support is weak or conflicting. |
| GET | `/api/investigations` | Lists saved investigations. |
| POST | `/api/investigations` | Persists a question with a whole-collection or selected-document scope. |
| GET | `/api/investigations/{investigation_id}` | Reads the saved scope and generated report. |
| POST | `/api/investigations/{investigation_id}/generate` | Retrieves local evidence, claims, conflicts, reliability, and citation-checked answer data, then saves a structured report. |
| GET | `/api/investigations/{investigation_id}/report.pdf` | Exports the persisted report as a local PDF. |
| GET | `/api/knowledge-graph` | Returns persisted nodes and evidence-backed edges. |
| GET | `/api/knowledge-graph/entities/{entity_id}` | Returns a graph node and its adjacent nodes and edges. |

Use <http://127.0.0.1:8000/docs> to exercise the endpoints. Upload accepts PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, and JPEG with matching media types. It checks signatures and Office container structure, enforces `MAX_UPLOAD_MB` and `MAX_UPLOAD_FILES`, generates safe local storage names, validates image dimensions, and rejects repeated SHA-256 hashes. Upload and processing are separate actions: uploading never executes the file or starts extraction automatically.

### Process an uploaded document

After uploading, copy its returned `id` and call:

```powershell
$documentId = "PASTE_RETURNED_DOCUMENT_ID"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/documents/$documentId/process"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/documents/$documentId/evidence"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/documents/$documentId/status"
```

The processing lifecycle starts at the Phase 2 upload status `uploaded`, then moves through `VALIDATING` â†’ `QUEUED` â†’ `PROCESSING` â†’ `COMPLETED`; errors are reported as `VALIDATION_FAILED`, `PROCESSING_FAILED`, `OCR_UNAVAILABLE`, or `PARTIALLY_COMPLETED`. Extraction can be requested again safely: stable evidence keys prevent duplicate evidence and claims. Candidate claims are deterministic first-stage values linked to the evidence row; names/status candidates are heuristic and must be reviewed, not treated as verified facts.

CSV evidence retains row, column, and cell coordinates. XLSX records include worksheet names and cell coordinates. PDF text retains page numbers and table cells where PyMuPDF can detect them. DOCX paragraphs/headings and table cells retain paragraph/table indexes. Original extracted text is preserved as stored evidence.


### Phase 8: Investigation Workspace

From the UI, create a saved investigation, enter the question, and select documents or the whole collection. Generated reports display exact-quote-checked evidence passages, linked normalized claims, conflict pairs with source locations, heuristic reliability explanations, missing evidence, limitations, and either a cited local answer or an explicit abstention. Export the saved report from the workspace as a PDF. The database table is additive and existing data is retained.

The repeatable isolated E2E runner is `backend/scripts/run_e2e_verification.py`. It checks the real local Ollama flow only when Ollama and both configured models are available; it uses temporary SQLite/upload paths. Current test status and remaining readiness requirements are in `docs/PHASE_8_TEST_REPORT.md`.
### Phase 4: Local embeddings, retrieval, and Qwen answers

Ollama must be running on loopback (`http://127.0.0.1:11434`). The configured defaults are `qwen3.5:4b` for answers and `nomic-embed-text` for embeddings. The application checks installed model names and does not download or pull models. Inspect the local inventory with `ollama list`; if a required model is missing, install it yourself once with `ollama pull qwen3.5:4b` or `ollama pull nomic-embed-text`. The Ollama client rejects non-loopback URLs.

The local index stores chunk text and provenance links in SQLite. Embedding vectors are also cached in SQLite by model and text hash, so unchanged reindex requests reuse existing vectors. Evidence records remain the citation source of truth. If Ollama is unavailable, search falls back to keyword matching; answer generation abstains when the local chat model is unavailable, evidence is weak, or the model's citations fail source verification. Confidence labels are retrieval heuristics, not calibrated probabilities.

To index processed documents and ask a question from PowerShell:

```powershell
$documentId = "PASTE_RETURNED_DOCUMENT_ID"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/embeddings/index" `
  -ContentType "application/json" `
  -Body (@{ document_ids = @($documentId) } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/ask" `
  -ContentType "application/json" `
  -Body (@{ question = "What is the approved project budget?"; document_id = $documentId } | ConvertTo-Json)
```

The synthetic sample at `data/datasets/phase4_demo_synthetic_budget.txt` is invented test data. Upload it through `POST /api/documents/upload`, process the returned document ID, then index and ask: â€œWhat is the approved project budget for Project DEMO-ALPHA?â€ The API answer returns evidence metadata and a citation tied to a persisted SQLite evidence ID. Sample data is ignored by Git.

`OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`, `EMBEDDING_BATCH_SIZE`, `RETRIEVAL_CHUNK_SIZE`, `RETRIEVAL_CHUNK_OVERLAP`, `RETRIEVAL_TOP_K`, and `RETRIEVAL_MIN_SCORE` can be set in `.env`. The base URL must remain a loopback address. Embedding, indexing, search, and chat are local runtime operations.

### Local OCR on Windows

OCR requires the separate Tesseract executable; installing the Python `pytesseract` package alone is insufficient. Install the current 64-bit Windows build from the [UB Mannheim Tesseract installer page](https://github.com/UB-Mannheim/tesseract/wiki), which is the Windows installer source referenced by the [Tesseract installation guide](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md). Select English language data during installation. Add `C:\Program Files\Tesseract-OCR` to `PATH`, or set `TESSERACT_CMD` in `.env` to the full path to `tesseract.exe`. Then open a new PowerShell terminal and verify:

```powershell
tesseract --version
Get-Command tesseract
```

If configured with `.env`, use `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`, restart the backend, and reprocess the document. The default OCR engine is local Tesseract (`OCR_ENGINE=tesseract`). Selecting an unavailable engine never triggers a model download and returns a diagnostic. OCR-dependent tests skip when the executable is missing; the non-OCR extraction and the unavailable-engine behavior are still tested.

### Explicit sample dataset ingestion

The current sample `data/datasets/phase4_demo_synthetic_budget.txt` is synthetic test data. The script below processes only the directory explicitly passed to it and talks to the loopback API. It does not search other folders on the computer.

```powershell
Set-Location .\CERBERUS-X
& .\backend\.venv\Scripts\python.exe .\backend\scripts\ingest_dataset.py .\data\datasets
```

Place the selected files under `data\datasets` first, or pass another specific folder path. Unsupported files and duplicate uploads are reported and skipped. Start the backend before running this command.

### Troubleshooting

- `OCR_UNAVAILABLE`: install the local Tesseract executable, add it to `PATH` or set `TESSERACT_CMD`, restart the backend, then process the document again.
- `PROCESSING_FAILED`: inspect the file status and backend log; the API deliberately does not log document text. Confirm the upload was not malformed or truncated.
- `409 duplicate_file`: the same bytes already have a document record. Retrieve it through `GET /api/documents` and request processing again if needed.
- `415 content_type_mismatch`: check the filename extension and multipart media type; both must match the actual file format.
- XLSX/DOCX parsing depends on valid Office ZIP containers. Password-protected or malformed documents are not supported.
- Reprocessing stores no duplicate evidence. Existing database tables are upgraded with additive columns at backend startup; the database file is never reset.

### Backend tests

From the outer workspace root (`CERBERUS_X`):

```powershell
Set-Location .\CERBERUS-X
Set-Location .\backend
& .\.venv\Scripts\python.exe -m pytest tests
& .\.venv\Scripts\python.exe -m pip check
Set-Location ..\frontend
npm run build
```

The real Ollama test is opt-in and checks installed models, an embedding request, and a local chat response. Run it from `CERBERUS-X\backend` with:

```powershell
$env:CERBERUS_RUN_REAL_OLLAMA = "1"
& .\.venv\Scripts\python.exe -m pytest tests\test_phase4_real_ollama.py -v
Remove-Item Env:CERBERUS_RUN_REAL_OLLAMA
```

Mocked service tests check deterministic failure paths; they do not prove real model operation. A separate local sample workflow was run through document upload, extraction, indexing, `/api/ask`, and an SQLite citation lookup. No test has yet disconnected the network, so the project must not be described as verified offline.

The current workspace has no actual supplied CERBERUS-X dataset to ingest. Phase 3 tests generate clearly synthetic temporary fixtures for each extractable format.

### Phase 5: claim comparison and evidence verification

After document extraction, normalize Phase 3 candidate claims with the local API. This does not change `Claim.value`, `Claim.context`, or the original evidence text; it fills separate structured fields and retains the evidence/source-location foreign keys.

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/claims/normalize" `
  -ContentType "application/json" -Body "{}"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/claims?normalized_only=true"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/contradictions"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/reliability/sources"
```

Ask the verification endpoint for a source-linked report:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/verification/analyze" `
  -ContentType "application/json" `
  -Body (@{ question = "What approved budget values are recorded for Project ORION-204?"; top_k = 8 } | ConvertTo-Json)
```

The Phase 5 report uses the existing Phase 4 local retrieval service. If local embeddings are unavailable, it reports keyword-only retrieval diagnostics. The answer text is assembled from retrieved normalized claims; it does not call Qwen, choose a winning claim, or invent citations. Use `POST /api/ask` for Phase 4's local Qwen answer, which validates citation IDs and quoted text against stored evidence. A Phase 5 verification abstains when it has no matching evidence, no linked claim, weak retrieval, or a same-field, temporal, unit, or unresolved disagreement. A category mismatch is reported as a non-conflict comparison finding and does not by itself force abstention.

Conflict classifications describe the relationship between assertions: `CONFIRMED_CONFLICT`, `POTENTIAL_CONFLICT`, `TEMPORAL_DIFFERENCE`, `CATEGORY_MISMATCH`, `UNIT_MISMATCH`, `UNRESOLVED`, and `NO_CONFLICT`. A confirmed conflict means the records disagree about a comparable field; it does not establish which record is correct. Financial category differences such as an approved budget versus a procurement estimate are retained as `CATEGORY_MISMATCH`, not automatically treated as contradictory. Draft/approved state differences remain potential conflicts. Human status changes are stored separately in `conflict_resolutions`; the claim and evidence rows are preserved.

Source evaluations expose authority, approval status, recency, directness, completeness, extraction quality, and independent corroboration. Default weights are in `backend/app/services/reliability/source_reliability.py`. To override them for a backend process, set `CERBERUS_RELIABILITY_WEIGHTS` to a JSON object with all seven criteria and nonnegative values summing to 1. For example:

```powershell
$env:CERBERUS_RELIABILITY_WEIGHTS = '{"authority":0.2,"approval_status":0.2,"recency":0.1,"directness":0.2,"completeness":0.1,"extraction_quality":0.15,"independent_corroboration":0.05}'
```

These weights produce a configurable review heuristic, not a scientifically validated probability. Publication recency remains neutral because the current document model stores upload time, not a trusted source-publication date. Exact extracted-text copies are detected and excluded from corroboration. Distinct text fingerprints are only a proxy and do not prove that two sources are independent. Conflict confidence fields are also rule-based heuristics, not calibrated probabilities.

The graph is built with NetworkX and persisted in SQLite. Nodes cover documents, evidence, claims, projects/named entities, and conflict findings. Edges include the evidence ID that supports each relationship. Rebuilding the graph is idempotent. The React frontend exposes the live knowledge graph and conflict review views alongside verification counts.

The Phase 5 synthetic test uses two separate text records:

```text
Project ORION-204 approved budget is â‚¹10,00,000.
Project ORION-204 approved budget is â‚¹12,00,000.
```

The deterministic comparison classifies these as a disagreement about the same normalized approved-budget field, preserves both values and source locations, and does not select a winner. Separate tests confirm that an approved budget and procurement estimate are treated as different categories, and that January/March project statuses can be a temporal change. These values are synthetic test data, not claims about a real project.

## Data and privacy

Uploaded documents, processed files, datasets, local model files, environment secrets, and SQLite databases are excluded from Git. The API binds to loopback by default, and CORS is limited to the local Vite development origins. Do not put private documents or secrets in tracked files.

## Planned implementation phases

1. Workspace and runnable foundation.
2. FastAPI modules, SQLite schema, and database operations.
3. Validated local uploads, extraction, OCR, and provenance.
4. Local Ollama embeddings, hybrid retrieval, and grounded answers (implemented; live sample verified).
5. Claims, contradiction review, source reliability, abstention, and knowledge graph.
6. Dashboard and evidence workflows connected to real APIs.
7. Integration, document/API coverage, and offline verification.
8. Demonstration dataset workflow and final setup guide.


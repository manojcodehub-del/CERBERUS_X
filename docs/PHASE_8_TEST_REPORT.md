# CERBERUS-X Phase 8 Test Report

**Verification date:** 2026-11-26
**Overall result:** Automated checks passed. The real-model Phase 8 E2E workflow stopped at the unavailable local Ollama dependency. Offline and browser-level visual tests were not performed.

## Automated checks

| Check | Result | Notes |
| --- | --- | --- |
| Backend suite: `backend\.venv\Scripts\python.exe -m pytest -q` | **61 passed, 2 skipped** | Temporary DB/API tests. One skip requires Tesseract; the other requires `CERBERUS_RUN_REAL_OLLAMA=1`. One Starlette/httpx deprecation warning. |
| Python compile: `backend\.venv\Scripts\python.exe -m compileall -q backend\app backend\scripts backend\tests` | **Passed** | Includes the extended E2E runner. |
| Frontend production build: `npm run build` from `frontend` | **Passed** | Vite transformed 2,580 modules. `constants` chunk warning: 919.55 kB minified / 243.20 kB gzip. |
| Frontend unit tests | **Not configured** | `frontend/package.json` has no test script. |
| API integration and critical route tests | **Covered by backend suite** | Health/status, documents, indexing/retrieval/verification, conflicts/reliability/graph, investigations and PDF, validation and persistence. |

## Phase 8 coverage in automated tests

- Investigation create/list/read/generate, validation, scope filtering, saved report reads, and PDF export.
- Report evidence and claims are tied to stored evidence/document IDs; source stance is not inferred from a citation label.
- Missing local answer model keeps the retrieved evidence/claims and produces an explicit abstention.
- Common physical-unit normalization, possible duplicate classification, event-node evidence provenance, and live storage/not-verified diagnostics.
- Investigation and PDF can be fetched after a second app instance opens the same temporary SQLite DB.

These tests validate API/service behavior. Local model output is stubbed in those cases; they are not a real-model E2E result.

## Real-model E2E attempt

`backend/scripts/run_e2e_verification.py` was run on 2026-11-26 with its isolated temporary database. The runner:

1. Received HTTP 200 from health and system status.
2. Uploaded the generated sample PDF (HTTP 201).
3. Processed the PDF (HTTP 200) and read page-level evidence (HTTP 200).
4. Stopped at local embedding/index with HTTP 503: `ollama_unavailable`; `127.0.0.1:11434` was not reachable. `ollama list` also failed to start its service because it could not open the user Ollama log (`Access is denied`).

Therefore the following Phase 8 real-model steps were **not reached** in this run: embeddings/search, live stance classification, investigation conflict report, local answer generation, PDF export from live report, and restart persistence of that report. The prior Phase 7 run documented in `END_TO_END_TEST_REPORT.md` is historical evidence for the Phase 7 workflow only.

The isolated runner has been extended to assert those Phase 8 steps when Ollama is available. Because it stopped before those steps, it did not write a new `docs/e2e_results.json`.

## OCR, offline, and UI checks

- **Image OCR:** Tesseract was not found on PATH. The Tesseract integration test was skipped. A prior Phase 7 image run returned `OCR_UNAVAILABLE`; image OCR is not claimed as working.
- **Offline:** no internet-disconnected run was performed. The model inventory/weights could not be confirmed in the current session, and the Ollama loopback API was unavailable. `/api/system/status` intentionally returns `offline_readiness: not_verified`.
- **Unexpected network requests:** static inspection of application sources found the configured local endpoints only (`127.0.0.1:8000` frontend API and `127.0.0.1:11434` Ollama). No OS-level outbound capture or browser network inspection was performed.
- **Browser/WebGL:** production build passed, but the workspace, 3D loading/failure path, 2D fallback, reduced motion, and mobile layout were not clicked/visually tested in a browser during Phase 8.

## Limitations and reproduction

Local Qwen/embedding model availability, Tesseract, the optional GLB, the large Vite chunk, and live browser behavior remain the main readiness limits. The exact start and repeatable test commands are in [`HACKATHON_DEMO_GUIDE.md`](HACKATHON_DEMO_GUIDE.md). The application can continue to use local keyword search when Ollama is missing; local generated answers and embeddings require the local models.

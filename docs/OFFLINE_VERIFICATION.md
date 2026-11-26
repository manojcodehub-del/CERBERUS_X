# CERBERUS-X Offline Verification

**Verification date:** 2026-11-26
**Status:** **Not verified offline.** No physically disconnected run was performed. The current local Ollama endpoint was unavailable, so the model weights and live local AI path could not be confirmed before an offline run.

## Current checks

- The existing Python 3.11 virtual environment and frontend npm dependencies were usable for the backend suite and production build; those commands did not need dependency downloads.
- `http://127.0.0.1:11434/api/tags` was not reachable in this session. `ollama list` failed to start the server because access to the Ollama application log was denied. This does not establish whether either configured model is installed.
- The isolated real-model E2E runner successfully uploaded and extracted its generated PDF, preserving page-level evidence, then received HTTP 503 `ollama_unavailable` at embedding/index. It stopped before the Phase 8 report path.
- Tesseract was not found on PATH. Image OCR requires the separate local executable and is not reported as working.
- The diagnostics API returns `offline_readiness: not_verified`, which the frontend displays directly.

The Phase 7 report recorded an earlier successful local-Ollama run on 2026-11-25. That historical result does not establish the current service state and does not exercise the Phase 8 investigation workflow.

## Network scope

Static inspection found these configured application URLs:

- Frontend API: `http://127.0.0.1:8000`.
- Ollama model service: `http://127.0.0.1:11434`.

No cloud AI endpoint or external runtime asset URL was found in the inspected application code. This is a static code observation only. No packet capture, browser network trace, or whole-host egress audit was performed; Windows/OneDrive and other processes were not measured.

## Dependencies and features that need internet at setup time

- Python and npm package installation need package access unless their dependencies are already cached/installed.
- Ollama model weights need to be installed locally before disconnection (`qwen3.5:4b` and `nomic-embed-text`). The current inventory was not verified.
- The optional Tesseract executable/language data and optional local projector GLB must be acquired separately if those features are wanted. The app does not fetch OCR/cloud AI or GLB assets at runtime in the inspected sources.

With Ollama unavailable, local SQLite/document extraction and keyword fallback can work; semantic embeddings and generated local answers cannot be verified. No cloud AI service is configured or required by the app architecture.

## Repeatable offline verification procedure

After Ollama starts successfully and `ollama list` confirms both models, install all required packages and model weights first. Then use Windows network controls to disconnect the machine and run these checks:

1. Start Ollama locally and confirm it remains available on loopback while disconnected.
2. Start the backend and frontend using the commands in [`HACKATHON_DEMO_GUIDE.md`](HACKATHON_DEMO_GUIDE.md).
3. Run `backend/scripts/run_e2e_verification.py`. The isolated workflow now includes investigation report, opposing/supporting passages, conflict provenance, local PDF export, and saved report after app recreation.
4. Run `backend/.venv/Scripts/python.exe -m pytest -q` and exercise the document, search, question, contradiction, graph, diagnostics, and investigation UI paths.
5. Capture outbound connections at the OS level if making a no-egress claim. Keep OCR unavailable unless a generated image is actually recognized by the installed OCR engine.
6. Restore network connectivity and record the command outputs/date. Until this is done, offline readiness must remain `not_verified`.

## Local-only behavior in the code

- SQLite and document files use local storage paths.
- Ollama requests are restricted to loopback.
- Missing Ollama models produce diagnostics/keyword fallback or an abstention; the app does not pull models or fall back to a cloud AI API.
- Missing Tesseract is reported as unavailable rather than silently claiming OCR.

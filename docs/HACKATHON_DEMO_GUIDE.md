# CERBERUS-X Five-Minute Hackathon Demo

## Before the demo

Start Ollama and verify `ollama list` includes the configured local models:

- `qwen3.5:4b`
- `nomic-embed-text:latest` (often shown as `nomic-embed-text`)

Complete model/package downloads before disconnecting the internet. The current Phase 8 verification session could not reach Ollama, so run the E2E command below successfully on the demo laptop before telling judges the AI path was verified. Tesseract is optional for the core text/PDF demo; do not claim image OCR unless it actually recognizes the test image.

Open two PowerShell terminals from `C:\Users\manoj\OneDrive\Documents\ChatGPT\CERBERUS_X` (or the outer workspace root containing `CERBERUS-X`).

**Terminal 1 — backend:**

```powershell
Set-Location .\CERBERUS-X
& .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\backend --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend:**

```powershell
Set-Location .\CERBERUS-X\frontend
npm run dev
```

Open <http://127.0.0.1:5173>. Check the Dashboard and Diagnostics before starting. The default database is persistent; do not clear it during the demo.

To create the second synthetic source before the demo:

```powershell
$demoConflictPath = Join-Path $env:TEMP 'cerberus_demo_alpha_amendment.txt'
$demoConflictText = @('SYNTHETIC DEMONSTRATION DATA — invented values for local testing only.', 'Project ID: DEMO-ALPHA', 'The revised approved project budget for Project DEMO-ALPHA is INR 1,850,000.', 'Approval date: 2026-11-25.')
Set-Content -LiteralPath $demoConflictPath -Value $demoConflictText -Encoding utf8
```

## Five-minute run of show

| Time | Action | What to show |
| --- | --- | --- |
| 0:00–0:25 | Dashboard, then Diagnostics. | Live database/storage and model/OCR statuses. State offline readiness accurately; current status is not verified until the disconnected test passes. |
| 0:25–1:05 | Documents: upload `data\datasets\phase4_demo_synthetic_budget.txt`, process it, then index it. | Actual extracted source text, provenance, and local embedding/index status. The sample is synthetic. |
| 1:05–1:45 | Intelligence: search `approved project budget DEMO-ALPHA`; ask `What is the approved project budget for Project DEMO-ALPHA?`. | Local answer and clickable citation. Open the citation to show the source record. |
| 1:45–2:20 | Upload the amendment at `$demoConflictPath`, process and index it. | The second source's original INR 1,850,000 claim and paragraph location. |
| 2:20–3:05 | Contradictions: analyze new claims. | The INR 1,250,000 vs INR 1,850,000 disagreement, both original claims/locations, and a human-review explanation. The system does not choose a winning source. |
| 3:05–4:15 | Investigation workspace: create `DEMO-ALPHA budget review` with question `What approved budget is recorded for Project DEMO-ALPHA?`; select both documents and generate. | Supporting/opposing passages and claims, conflict pair, reliability explanation, missing-evidence/limitations notes, and abstention because the budget assertions conflict. |
| 4:15–4:40 | Export PDF, then open Knowledge Graph. | Locally generated saved report; actual source provenance and conflict relationships. Select evidence/claim/event nodes and use the 2D fallback if WebGL is unavailable. |
| 4:40–5:00 | Reliability/Diagnostics. | Heuristic reliability explanation, local dependencies, free storage, and OCR/offline readiness limitations. |

## Repeatable API workflow

From the `CERBERUS-X` project directory:

```powershell
& .\backend\.venv\Scripts\python.exe .\backend\scripts\run_e2e_verification.py
```

The runner uses a temporary SQLite database and upload directory, makes a PDF from the included synthetic dataset, exercises local indexing/search/Q&A and the conflicting TXT source, then checks investigation report, support/opposition, conflict provenance, PDF export, and report persistence after app recreation. It also tests image OCR separately when the workflow reaches that step. It does not modify the configured project database. The Phase 8 extension was not reached during the 2026-11-26 attempt because Ollama returned unavailable at embedding/index.

## Accurate claims to make

- Demo values are synthetic, not real project records.
- AI, embeddings, report stance, and answers use local Ollama only when its models are installed and reachable.
- Citations point to stored evidence; the report checks IDs/quotes. Conflicts preserve both sources and require human judgment.
- Reliability and stance labels are heuristic/model interpretations, not truth scores.
- Image OCR is not working on this machine until local Tesseract successfully processes a test image.
- Full offline and browser-level behavior have not been verified. See [`PHASE_8_TEST_REPORT.md`](PHASE_8_TEST_REPORT.md) and [`OFFLINE_VERIFICATION.md`](OFFLINE_VERIFICATION.md).

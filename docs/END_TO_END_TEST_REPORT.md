# CERBERUS-X End-to-End Test Report

**Run date:** 2026-11-25  
**Result:** Passed for the text/PDF evidence workflow using local Ollama. Image OCR is unavailable and is reported separately.  
**Runner:** `backend/scripts/run_e2e_verification.py`  
**Machine-readable result:** [`e2e_results.json`](e2e_results.json)

## Scope and isolation

The runner builds a temporary SQLite database and upload directory, starts the FastAPI application in-process, uses the actual synthetic dataset `data/datasets/phase4_demo_synthetic_budget.txt`, creates a one-page PDF from that dataset, and calls the installed loopback Ollama models. It does not add rows to the configured project database. It recreates the application against the same temporary database to check persistence.

## Workflow results

1. **PDF upload and extraction:** upload returned HTTP 201; processing completed with 1 page-level evidence record and 5 candidate claims.
2. **Provenance:** the extracted record retained PDF page 1 and its original budget text.
3. **Embedding and indexing:** `nomic-embed-text:latest` generated 1 vector for the first PDF chunk; indexing status was `completed`.
4. **Search:** hybrid retrieval returned the sample evidence record for the approved-budget query.
5. **Question answering:** `qwen3.5:4b` returned `INR 1,250,000`, did not abstain, and cited the exact source sentence from the PDF on page 1.
6. **Conflicting source:** a second processed TXT amendment asserted an approved budget of `INR 1,850,000`; its extracted paragraph provenance was retained.
7. **Contradiction analysis:** deterministic normalization created a `CONFIRMED_CONFLICT` between the original `INR 1,250,000` claim and the amendment's `INR 1,850,000` claim. The result exposed both filenames, evidence IDs, and locations (PDF page 1; TXT paragraph 2). The original INR 1,400,000 vendor quotation remained marked as not the approved budget/procurement estimate.
8. **Reliability:** both sources returned heuristic scores and criterion explanations, including the neutral authority and publication-recency limits.
9. **Knowledge graph:** graph API returned nodes for both documents and their conflicting claims; the result included 22 nodes and 50 edges before the image fixture was processed.
10. **Verification:** the answer verification endpoint abstained because the retrieved assertions conflicted and reported `CONFIRMED_CONFLICT`.
11. **Restart persistence:** after recreating the application on the same temporary database, health remained `ok`; the sample evidence, indexed chunks, graph, question, and citation remained stored. The final temporary database had 3 documents (PDF, amendment TXT, and OCR test image), 6 indexed chunks, and 24 graph nodes / 51 edges.

## Image OCR (separate test)

The test image was accepted and processed, but OCR status was `OCR_UNAVAILABLE`; recognized content contained image metadata only, no expected image text. The warning identifies the missing local Tesseract executable. **Image OCR is not working on this machine and is not claimed as verified.**

## Additional checks

- A read-only smoke pass against the running local API returned HTTP 200 for 16 health, status, analytics, document/evidence, embedding, retrieval, claim, contradiction, reliability, graph, and entity-neighborhood GET routes.
- The full backend suite with the real local Ollama integration enabled passed: **53 passed, 1 skipped**. The skipped test requires Tesseract.
- Python `compileall` passed. Frontend `npm run build` passed; Vite emitted the documented large-chunk warning.
- The E2E workflow exercises the backend APIs, not a browser. A visual browser run was unavailable in this environment, so the new React controls are build-verified and their API operations are covered at the backend level, not clicked through in a browser.

## Existing project database note

An earlier pre-isolation legacy E2E run wrote one generated Phase 7 PDF and associated processing, Q&A, and conflict rows into the configured project database. Those user data rows were intentionally preserved. The final runner is isolated and does not repeat that side effect. Current project database counts are recorded in [`PHASE_7_AUDIT.md`](PHASE_7_AUDIT.md).

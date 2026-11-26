# CERBERUS-X Investigation Workflow

## Purpose and boundaries

An investigation is a saved question and source scope. CERBERUS-X gathers local retrieved evidence, normalized claims, comparison findings, source evaluations, and evidence-backed graph relationships. The generated report is a snapshot stored in SQLite and can be regenerated as local documents or indexes change.

The application does not decide which conflicting source is true. Source reliability scores and model stance labels are review aids, not calibrated probabilities or verified truth. A local answer is accepted only through the existing citation validation path. If verification is weak/conflicting, a local model is unavailable, or no exact citations pass validation, the conclusion explicitly abstains.

## UI workflow

1. Start the local backend, frontend, and (for AI features) Ollama. Open **Investigation workspace** from the navigation.
2. Enter a title and investigation question.
3. Choose the whole collection or select documents. Selected scopes are limited to 50 document IDs and constrain evidence retrieval, claims, and conflict pairs.
4. Create the investigation. The backend saves it first, then retrieves evidence and generates a report. Saved investigations can be reopened and regenerated.
5. Inspect source passages, linked claims, original values, normalized values, conflict classifications, both source locations, reliability explanations, missing evidence, and limitations. Source buttons open the stored document in the document explorer.
6. Export the persisted report as a local PDF. A saved report can be read and exported after application restart.

## Report sections

1. **Investigation question and scope:** question, collection or selected-document mode, document count, indexed count, and the IDs actually returned by retrieval.
2. **Executive summary:** citation-validated local answer, or an explicit abstention.
3. **Supporting evidence:** source passages and claims classified as supporting. Each passage carries a real evidence/document ID, source filename, location when available, and quote validated against stored text.
4. **Opposing evidence:** same provenance checks, with opposing labels kept separate from citations and supporting claims.
5. **Contradictions and unresolved issues:** conflict ID, classification/status, explanation and confidence note, both original claims, normalized values, document/claim/evidence IDs, and original locations.
6. **Source reliability:** actual stored source evaluation and criterion explanation. Scores are heuristic.
7. **Missing evidence:** weak retrieval, unavailable models, unindexed documents, documents without extracted evidence, absent support/opposition, or empty scope, as applicable.
8. **Conclusion and limitations:** validated answer citations when accepted, otherwise abstention and the reasons/limitations returned by the existing verification pipeline.

The local stance model is asked for structured JSON. Entries are omitted unless the evidence ID came from the current retrieval and the returned quote is an exact source substring. A valid citation alone does not turn an opposing passage into supporting evidence.

## API contract

All paths below are under `/api`:

- `GET /investigations?limit=50&offset=0` — list saved investigations.
- `POST /investigations` — create a draft. JSON fields: `title`, `question`, optional `document_ids` (null means whole collection), and `top_k` (1–20).
- `GET /investigations/{id}` — read the saved scope and report snapshot.
- `POST /investigations/{id}/generate` — generate and persist the report; optional JSON `top_k`.
- `GET /investigations/{id}/report.pdf` — export the saved report using local PyMuPDF.

Example create request:

```json
{
  "title": "DEMO-ALPHA budget review",
  "question": "What approved budget is recorded, and what evidence disagrees?",
  "document_ids": ["<stored-document-id-1>", "<stored-document-id-2>"],
  "top_k": 12
}
```

The create endpoint returns an investigation ID. Call the generate endpoint with that ID, then read the `report` in its response or fetch the saved investigation later. The API validates title/question bounds, top-k, duplicate/empty IDs, maximum scope size, and that every selected document exists.

## Conflict interpretation

Conflict classes retain the existing deterministic engine outcomes: confirmed/potential disagreement, temporal difference, category mismatch, unit mismatch, unresolved comparison, and no conflict. Common measurement units normalize to canonical values. Currency symbols/codes and magnitude scales normalize, but different currencies are never exchange-converted. `POSSIBLE_DUPLICATE` means highly similar passages with the same normalized value; it is a review hint, not a contradiction or independent corroboration finding. Human review is required to determine source truth and whether differences refer to the same event/time/category.

## Local persistence and verification

Investigation rows and report JSON are additive SQLite data. The local PDF is generated from that report on demand and is not sent to a cloud service. Automated tests cover report scoping, quote validation behavior, missing-model abstention, conflict normalization, graph provenance, PDF signature/content type, and persistence after app recreation.

The live-model investigation path is part of `backend/scripts/run_e2e_verification.py`. The Phase 8 extension was not completed in the current run because Ollama was unavailable during the embedding step. Do not treat the tests with local-model fakes as proof of live Qwen/embedding output. Offline operation also remains unverified.

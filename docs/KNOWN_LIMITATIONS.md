# CERBERUS-X Known Limitations

**Reviewed:** 2026-11-26

## Runtime and feature limits

- **Live local AI:** Ollama's loopback endpoint was unreachable in the Phase 8 verification session. The isolated E2E runner extracted the generated PDF but stopped with HTTP 503 at embedding/index. Local model inventory and weights are unverified in the current session; live embeddings, stance classification, and generated answers have not been confirmed for Phase 8.
- **Offline verification:** no physically disconnected run or OS-level network capture was performed. The API and diagnostics screen correctly show `not_verified`. See [`OFFLINE_VERIFICATION.md`](OFFLINE_VERIFICATION.md).
- **OCR:** Tesseract is not available on PATH in this session. The integration test was skipped and a prior Phase 7 image test returned `OCR_UNAVAILABLE`. Image/scanned-document OCR is not claimed as working.
- **Local projector model:** `frontend/public/models/hologram-projector.glb` is absent. A procedural projector fallback exists, but loading the optional GLB itself was not tested.
- **Browser/WebGL:** source includes loading/error fallbacks, a React Flow 2D graph, and reduced-motion handling. Browser interactions, WebGL failure, responsive layout, and reduced-motion behavior were not visually exercised in Phase 8.
- **Reliability scores:** these are deterministic heuristic review aids, not calibrated probabilities. Recency/independence limitations remain; human review is required.
- **Claim and stance analysis:** extracted claims are deterministic/heuristic. Investigation stance labels are local-model interpretations with evidence-ID and exact-quote checks; they still require human review. Conflict detection identifies disagreement, not which source is true.
- **Currency:** symbols/codes and magnitude scales normalize, but currencies are not converted using exchange rates. Common physical units normalize; uncommon or ambiguous units need review.
- **Frontend automated tests:** `frontend/package.json` has no test script. The production build passes; browser-level behavior is not covered.
- **Bundle size:** Vite warns that the `constants` chunk is approximately 919.55 kB minified / 243.20 kB gzip.
- **SQLite migrations:** startup creates additive tables/columns; there is no versioned migration directory.

## Data and demo caveats

The included `phase4_demo_synthetic_budget.txt` and the conflicting amendment contain invented values for local testing only. Do not present them as real project records. The configured local database contains records preserved from earlier testing; the Phase 8 automated and E2E runners use isolated temporary storage. See [`PHASE_7_AUDIT.md`](PHASE_7_AUDIT.md) for the earlier database history and [`PHASE_8_TEST_REPORT.md`](PHASE_8_TEST_REPORT.md) for current verification boundaries.

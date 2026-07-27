# API Contracts

Doctrine rule 6: every frontend call maps to a backend endpoint, and this file is checked in CI
against the live OpenAPI spec at `/openapi.json`. The frontend is a Phase 2 deliverable (Next.js), so
the "Frontend call" column names the planned caller; the endpoints marked implemented are live today
and callable without the UI. FastAPI serves interactive docs at `/docs` and the machine-readable spec
at `/openapi.json`.

| Frontend call (Phase 2) | Method | Path | Status | Notes |
|---|---|---|---|---|
| Liveness/readiness poll | GET | `/health` | implemented | Returns `{status, env}`. No auth required. |
| Demo data load | GET | `/api/v1/demo` | implemented | Returns `{items: [...]}` from `data/synthetic/`. Development-only; responds 503 outside `development`. |
| — | GET | `/openapi.json` | implemented | OpenAPI schema, served by FastAPI. CI diffs this file against it. |
| — | GET | `/docs` | implemented | Swagger UI, served by FastAPI. |
| Upload sales history CSV | POST | `/api/v1/ingest` | implemented | Keyless. All-or-nothing CSV validation (row-numbered errors), idempotent by (sku, date); runs the documented demand-repair rule inline and reports repaired-day counts. |
| Compute a forecast for a SKU | POST | `/api/v1/forecasts` | implemented | Deterministic seasonal weekday core over the repaired history; persists version + P10/P50/P90 points. 422 without ingested history. |
| View quantile forecast for a SKU | GET | `/api/v1/forecasts/{sku_id}` | implemented | Latest stored forecast with its points. |
| Compute an action envelope for a SKU | POST | `/api/v1/envelopes` | implemented | Newsvendor-style lower/point/upper at a service level with a regret note per bound; requires unit economics (request or CSV), no invented defaults. |
| Open the action envelope for a SKU | GET | `/api/v1/envelopes/{sku_id}` | implemented | Latest stored envelope; stored signals surfaced beside it with an explicit "signals never change quantities in Phase 1" note. |
| Score a closed period | POST | `/api/v1/autopsy` | implemented | Deterministic forecast-vs-actual miss report (error, APE, band coverage). Stub honestly labeled: decomposition lands with the Phase 2 arena. |
| Sense a context note into typed signals | POST | `/api/v1/signals` | implemented | Key-gated (typed 503 without OPENROUTER_API_KEY). Gateway + strict JSON schema; span and date gates; rejected signals kept, never dropped. |
| List stored signals | GET | `/api/v1/signals` | implemented | Keyless read of stored demand signals. |
| Approve an order draft | POST | `/api/v1/orders/{order_id}/approve` | planned — Phase 2 | Human approval turns a draft into an order record. Never auto-submitted. Deferred with the owner-confirmation surfaces. |
| Confirm or edit a Scout signal | POST | `/api/v1/signals/{signal_id}/confirm` | planned — Phase 2 | Owner confirmation gate before a validated signal can influence a recommendation. |
| Compile a natural-language scenario | POST | `/api/v1/scenarios` | planned — Phase 3 | Parses a scenario sentence to typed, feasibility-validated parameters; recomputed deterministically. |

CI fails if a frontend call has no backend endpoint here, or if a path/method in this table is absent
from `/openapi.json` once its status is `implemented`.

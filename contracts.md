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
| Upload sales/inventory CSV or sync POS | POST | `/api/v1/ingest` | planned — Phase 1 | Ingest sales history + inventory; runs deterministic demand repair; returns per-SKU data-quality confidence. |
| View quantile forecast for a SKU | GET | `/api/v1/forecasts/{sku_id}` | planned — Phase 1 | Versioned P10/P50/P90 output from the deterministic statistical core. |
| Open the action envelope for a SKU | GET | `/api/v1/envelopes/{sku_id}` | planned — Phase 1 | Recommended order, safe range, latest order date, cash required, expected service level, downside exposure. |
| Approve an order draft | POST | `/api/v1/orders/{order_id}/approve` | planned — Phase 1 | Human approval turns a draft into an order record. Never auto-submitted. |
| Confirm or edit a Scout signal | POST | `/api/v1/signals/{signal_id}/confirm` | planned — Phase 2 | Owner confirmation gate before a validated signal can influence a recommendation. |
| Compile a natural-language scenario | POST | `/api/v1/scenarios` | planned — Phase 3 | Parses a scenario sentence to typed, feasibility-validated parameters; recomputed deterministically. |

CI fails if a frontend call has no backend endpoint here, or if a path/method in this table is absent
from `/openapi.json` once its status is `implemented`.

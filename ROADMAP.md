# Almanac — Roadmap

Three phases, drawn from the chapter's MVP build path. Each phase maps to a GitHub milestone; issues
carry the phase label and the milestone tracks its close.

## Phase 1 — Trustworthy classical core

*Mirrors GitHub milestone `phase-1-core`.*

A rigorous deterministic forecaster with no LLM in the loop. A classical forecaster alone already
beats what most small retailers use, so it ships first and stands on its own.

Deliverables:

- CSV / POS ingest for sales history and inventory.
- Deterministic demand repair: stockout censoring detection, lost-sales estimation with explicit
  assumptions, returns and bulk-order cleanup, per-SKU data-quality confidence.
- Statistical core: seasonal decomposition, ETS, Croston-class intermittent methods, LightGBM with
  engineered covariates, hierarchical reconciliation, quantile output (P10/P50/P90), versioned.
- Inventory optimizer: newsvendor quantities, safety stock, reorder points against lead-time
  distributions.
- Action envelopes with intervals: recommended order, safe range, latest order date, cash required,
  expected service level, downside exposure.
- `make eval` harness wired to the acceptance thresholds in EVAL.md (currently raising
  `NotImplementedError` until this phase lands).

## Phase 2 — Signal Scout, backtest arena, and the frontend

*Mirrors GitHub milestone `phase-2-signals`.*

The LLM enters as a context sensor — permanently walled off from the arithmetic — and the product
gets its first UI.

Deliverables:

- Signal Scout for weather feeds and public event / school calendars, emitting typed event signals
  with checkable provenance.
- Deterministic calendar and geo validation of every signal; owner confirmation before any signal can
  influence a recommendation.
- Quarantine and backtest arena: new signal classes earn live weight only after sustained lift across
  rolling windows, demoted automatically on decay; a public earned-influence scoreboard.
- Audit-trailed adjustments tying every envelope shift back to a confirmed, backtested signal.
- **Next.js frontend** on the shared portfolio design system: envelope view, signal confirmation, and
  scoreboard. This is where the demo GIF referenced in the README is produced.

## Phase 3 — Full context, scenarios, and self-grading

*Mirrors GitHub milestone `phase-3-context`.*

Deliverables:

- Supplier inbox ingestion (with explicit permission, multilingual, stored locally) as claim-typed
  signals.
- Regional social-trend sensing.
- Scenario console: natural-language scenarios parsed to typed, feasibility-validated parameters and
  recomputed deterministically.
- Regret maps across candidate decisions and per-period forecast autopsies (miss decomposition:
  model vs data quality vs signal vs override), feeding the signal scoreboard and calibration ledger.
- Multi-store hierarchy: transfers and reconciliation across SKU, category, and location.

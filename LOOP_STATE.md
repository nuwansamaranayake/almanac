# LOOP_STATE — Almanac Phase 1

Branch: `phase-1`. BLUEPRINT L681-683 (MVP path, Phase 1): **CSV/POS ingest, demand repair,
statistical core, optimizer, action envelopes with intervals.** A trustworthy classical
forecaster alone already beats what most small retailers use. The Phase 1 cut adds the LLM
context sensor as a key-gated store-and-surface stage (signals never change numbers; the
earn-influence backtest arena is Phase 2, stated honestly). Exit requires: real eval meeting
EVAL.md bounds, keyless smoke through the real processing loop, alembic migration with the
table count asserted, CI eval flipped to required, and the flywheel duty (a Seismograph
contract ships with the LLM stage).

## Milestones (commit each; gate.py after each)

- [x] M1  EVAL.md numeric thresholds first; LOOP_STATE; branch phase-1
- [x] M2  engine/repair: censored-demand repair (stockout-flagged days imputed from
         same-weekday medians of non-stockout days; repaired = max(observed, imputed));
         engine/forecast: seasonal moving average with weekday seasonality + empirical
         prediction intervals (P10/P50/P90); engine/synth: seeded synthetic generator
         with known seasonality + planted stockouts (+tests)
- [x] M3  engine/optimizer: newsvendor-style action envelope (order-quantity range per
         SKU at a service level, monotone in service level, one-line regret note per
         bound, deterministic arithmetic); engine/autopsy: per-period miss stubs
         (forecast vs actual: error, APE, band coverage) (+tests)
- [x] M4  scripts/eval.py: deterministic keyless harness against the pre-written EVAL.md
         bounds; byte-reproducible report; loud key-gated note
- [x] M5  schema + alembic 0002 (skus, sales_records, stockout_flags, repaired_demand,
         forecasts, forecast_points, action_envelopes, demand_signals)
         EXPECTED_TABLE_COUNT=9; API: ingest (keyless CSV), forecasts (POST compute /
         GET read), envelopes (POST compute / GET read, signals surfaced beside),
         autopsy, signals (key-gated POST / keyless GET); CLI `python -m app.cli plan`;
         smoke = real deterministic loop keyless; Dockerfile migrate-on-start
- [x] M6  flywheel: engine/signals (LLM context sensor via gateway, strict JSON schema,
         enum'd signal types = canonical anchors, span + date gates);
         contracts/context-sensor-stability.yaml validated against Seismograph's DSL;
         key-gated eval_llm observed with a real key
- [x] M7  CI eval -> "eval (required)"; README/contracts.md/CHANGELOG/EVAL.md truth pass
- [x] FINAL gate.py GATE OK; check_migrations MIGRATION OK: 9; prod-guard (demo 503 +
         real GET 200 under APP_ENV=production); byte-reproducibility (two eval runs, cmp)

## DECISION log

- Phase 1 statistical core is the blueprint's MVP cut, not the full core: seasonal moving
  average with weekday seasonality and empirical residual quantiles, pure stdlib, fully
  deterministic. ETS/Croston/LightGBM/hierarchy arrive in later phases; the wall (LLM never
  emits a number that enters the forecast) is load-bearing from day one.
- Censored-demand repair rule (documented, deterministic): a stockout-flagged day's demand
  is imputed as the median of same-weekday sales over non-stockout days; fallback to the
  all-days non-stockout median when the weekday has no clean history; repaired units =
  max(observed, imputed) because observed sales during a stockout are a floor on demand,
  never the demand.
- Signals in Phase 1 are stored and surfaced beside the envelope, never applied to numbers.
  The blueprint's earn-influence rule requires the backtest arena, which is Phase 2; saying
  otherwise would be an unearned claim. The envelope response says this explicitly.
- Canonical signal identity is the schema-enforced enum pair `signal_type:direction`, not
  any model-invented label (CareerCompiler FAIL-0003 lesson: model naming is not stable
  identity). The Seismograph contract compares Jaccard over these anchors.
- Zero-key smoke path: CSV ingest -> repair -> forecast -> envelope -> autopsy is the real
  product loop and needs no LLM. The signals endpoint refuses loudly (typed 503) without
  OPENROUTER_API_KEY (Standard 3: no silent fallback between paths).
- Newsvendor envelope quantile curve: piecewise-linear interpolation through the horizon
  sums of (P10, P50, P90), clamped flat outside [0.1, 0.9]. Lower/point/upper evaluate the
  curve at (sl-0.15, sl, sl+0.15) clamped to [0.05, 0.95]; monotone in service level by
  construction, and lower <= point <= upper always.

## BLOCKED

(none)

## Next

GATES_PASSED — all Phase 1 gates observed green on 2026-07-27:
- `python scripts/gate.py` -> GATE ruff/pytest/smoke/eval PASS, GATE OK, twice in a row
  (the first re-run caught a smoke idempotency bug, FAILURES.md FAIL-0005, fixed at root).
- `alembic upgrade head` + `scripts/check_migrations.py` -> MIGRATION OK: 9 tables against
  the throwaway verification Postgres (port 55435).
- Prod-guard under APP_ENV=production -> `/api/v1/demo` 503 (typed detail) AND
  `GET /api/v1/forecasts/{sku_id}` 200 with 7 real points.
- Byte-reproducibility -> two consecutive `scripts/eval.py` runs, `cmp` identical.
- Key-gated `scripts/eval_llm.py` observed live (google/gemini-2.5-flash): recall 1.00,
  paraphrase jaccard [1.0, 1.0] (first run failed honestly: FAIL-0004).

Phase 2 picks up from ROADMAP.md: Signal Scout sources (weather/events), owner
confirmation surfaces, quarantine + backtest arena (signals start earning influence),
order drafts with human approval.

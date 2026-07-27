# Changelog

All notable changes to Almanac are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-27

> **BREAKING.** Business read endpoints now require the same bearer token as writes.
> **Migration:** send `Authorization: Bearer $SMOKE_TEST_TOKEN` on GET requests too.
> Unauthenticated reads previously returned data and now return 401. Development is
> unaffected while the token is empty.

### Eval
- repair MAPE 0.0687 (<= 0.20), forecast MAPE 0.0862 (<= 0.25), envelope monotonicity 1.0,
  envelope sanity 1.0. Byte-reproducible.

### Changed
- `scripts/gate.py` enumerates routes and fails on any unguarded non-public route.

### Security
- Business read endpoints (GET /api/v1/forecasts/{sku}, /envelopes/{sku}, /signals) now require the same bearer token as writes. They
  previously served real production data to unauthenticated callers (FAILURES FAIL-0008).

## [0.2.0] - 2026-07-23

### Fixed
- Adversarial review wave (7 confirmed findings, see FAILURES.md FAIL-0006):
  - `POST /api/v1/autopsy` now verifies an explicit `forecast_id` belongs to the requested
    `sku_id` (typed 422) instead of silently scoring a cross-SKU forecast against the wrong
    SKU's actuals, and returns a typed 404 (not a TypeError 500) for a nonexistent
    `forecast_id`.
  - `POST /api/v1/signals` no longer runs the network LLM call inside an open DB
    session/transaction: the SKU check runs in a short first session, the gateway call runs
    with no session open, and results are inserted in a separate write transaction — a slow
    provider response can no longer pin a pooled Postgres connection.
  - CSV ingest rejects a blank or missing `stockout` cell with the row-numbered
    `IngestError` instead of silently importing it as `False` (which skewed the
    censored-demand repair).
  - Packaging: setuptools now auto-discovers `app*`, so wheels / non-editable installs ship
    `app.engine` (the explicit `packages = ["app"]` list silently dropped it).
  - CI test job installs the same pinned groundwork ref as pyproject/eval
    (`nuwansamaranayake/groundwork@v0.1.0`); the `|| echo` failure-swallow and the dead
    minimal-deps fallback are gone — an install failure fails the job loudly.
  - `scripts/check_migrations.py` hard-fails when `EXPECTED_TABLE_COUNT` is unset or not a
    positive integer instead of printing `MIGRATION OK` as a vacuous check (Standard 4).
  - Added `.dockerignore` so `.git`, `.env`, caches, and loop state never enter the image
    build context.

### Added
- Phase 1 core loop (branch `phase-1`): CSV sales ingest with all-or-nothing validation,
  censored-demand repair (same-weekday median rule, `repaired = max(observed, imputed)`,
  documented in `app/engine/repair.py`), seasonal weekday forecast core with empirical
  P10/P50/P90 intervals, newsvendor-style action envelopes with a regret note per bound,
  and per-period miss-autopsy stubs. Pure stdlib arithmetic; the LLM has no path into it.
- Persisted API loop: `POST /api/v1/ingest`, `POST+GET /api/v1/forecasts`,
  `POST+GET /api/v1/envelopes` (stored signals surfaced beside the envelope, never applied
  to quantities in Phase 1), `POST /api/v1/autopsy`, `POST /api/v1/signals` (key-gated,
  typed 503 without a key) and `GET /api/v1/signals`. Bearer auth on mutations when
  `SMOKE_TEST_TOKEN` is set. CLI: `python -m app.cli plan` (keyless, serverless).
- Schema + alembic `0002_real_schema`: skus, sales_records, stockout_flags,
  repaired_demand, forecasts, forecast_points, action_envelopes, demand_signals —
  8 app tables + alembic_version, `EXPECTED_TABLE_COUNT=9` asserted after migration
  (observed `MIGRATION OK: 9 tables`). Dockerfile migrates and asserts before serving.
- Deterministic eval harness meeting the pre-written EVAL.md bounds. Observed: repair MAPE
  0.0687 (bound 0.20), forecast MAPE 0.0862 (bound 0.25), envelope monotonicity 1.0,
  envelope sanity 1.0; report byte-reproducible (two runs, `cmp` identical).
- LLM context sensor (`app/engine/signals.py`) through the groundwork gateway with a strict
  JSON schema; canonical anchors are the closed enums `signal_type:direction`. Seismograph
  contract `contracts/context-sensor-stability.yaml` (validated against the Seismograph DSL
  loader, plan_id `88188a950fbce240`). Key-gated `scripts/eval_llm.py` observed live with
  google/gemini-2.5-flash: planted-anchor recall 1.00, paraphrase jaccard min 1.0. Its
  first run failed at jaccard 0.00 — root-caused and documented as FAILURES.md FAIL-0004
  (store context injected into the sensing prompt; bounds unmoved).
- Smoke test now drives the real keyless loop end to end: ingest with a planted stockout ->
  repair -> forecast -> envelope -> actuals -> autopsy.

### Changed
- CI eval job flipped to `eval (required)` (`continue-on-error` removed): a missed bound
  fails the build. Lean keyless deps (`pydantic`, `httpx`, `pyyaml`, pinned groundwork).
- README/EVAL.md/contracts.md truth pass: status reflects the built Phase 1 loop with the
  observed numbers; endpoint rows flipped to implemented; order-draft approval moved
  honestly to Phase 2 (no owner-confirmation surfaces exist yet).
- Dependency on `aignite-groundwork` switched from an editable path source to a pinned git
  dependency (`git+https://github.com/nuwansamaranayake/groundwork@v0.1.0`) so standalone clones and CI resolve
  it without a sibling checkout. PyPI publication planned at first release.
- `scripts/check_migrations.py` now uses `DATABASE_URL` with the declared psycopg v3 driver
  unmodified, fixing a clean-machine `make migrate` failure (see FAILURES.md FAIL-0002).
- README truth pass: scaffold status block, `(the design)` heading, "What exists today (verified)"
  section, scoped/dated novelty, dual-path Quickstart, em-dash sweep.
- CI: Python matrix (3.12, 3.13); eval job labeled "eval (Phase 1 pending)".

### Added
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) and a SECURITY.md vulnerability-reporting policy.

## [0.1.0] - 2026-07-21
### Added
- Engineering harness scaffold: governed doc set, config guard, verification gates,
  smoke test against a real business endpoint, migration-count check, CI pipeline,
  and a synthetic dataset so the demo runs with zero external keys.

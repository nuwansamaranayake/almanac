# Failure Gallery — Almanac

An honest record of things that broke, why, and what changed. A curated gallery beats a buried
changelog: it is where the doctrine earns its keep. Every entry names the *reported* symptom and
the *diagnosed* root cause separately (Standard 5).

> The entry below is a seeded template. Replace it with the first real failure you diagnose.

## FAIL-0001 (template) — Demo showed no data

- **Date**: 2026-07-21
- **Surface**: `GET /api/v1/demo`
- **Reported symptom**: The demo view rendered "no data".
- **Diagnosed cause**: `data/synthetic/demo.json` existed but was an empty array. The endpoint
  correctly raised HTTP 500 (`"synthetic fixture is empty"`) instead of silently returning `[]`.
- **Root cause**: Fixture authored empty during scaffold.
- **Fix**: Populated the fixture with a non-empty synthetic dataset. The smoke test asserts
  `items` is non-empty, so this cannot regress silently.
- **Doctrine link**: Standard 3 (no silent mock/fallback) and Standard 2 (smoke asserts non-empty).

## FAIL-0002 — `make migrate` failed on a clean machine (check_migrations driver)

- **Date**: 2026-07-21
- **Surface**: `scripts/check_migrations.py` (`make migrate`)
- **Reported symptom**: The migration-count check errored immediately after a successful
  `alembic upgrade`.
- **Diagnosed cause**: The script did `DATABASE_URL.replace("+psycopg", "")`, turning
  `postgresql+psycopg://...` into a bare `postgresql://...`. SQLAlchemy routes the bare URL to the
  **psycopg2** driver, which is not a declared dependency (the apps pin `psycopg` v3). `alembic`
  itself succeeded because it kept the `+psycopg` URL, so the failure surfaced only at the check step.
- **Root cause**: Driver mismatch between the migration step (psycopg v3) and the check step (psycopg2).
- **Fix**: Use `DATABASE_URL` unmodified so the check reuses the declared psycopg v3 driver. Proven
  against a real Postgres: `MIGRATION OK: 1 tables` at `EXPECTED_TABLE_COUNT=1`, and
  `MIGRATION CHECK FAILED: expected 2 tables, found 1` (rc=1) at `EXPECTED_TABLE_COUNT=2`.
- **Doctrine link**: Standard 4 (assert the table count) and Standard 1 (fix the root cause — the
  driver — not the symptom).

## FAIL-0003 — First public CI run: smoke job died before the stack started

- **Date**: 2026-07-23
- **Surface**: GitHub Actions `smoke` job (`docker compose up -d --build`)
- **Reported symptom**: CI run red on the first push; compose exited immediately.
- **Diagnosed cause (from the run log)**: `env file ... .env not found`. `docker-compose.yml`
  declares `env_file: .env`, and `.env` is gitignored by design, so it does not exist in a CI
  checkout. A second, deterministic failure sat behind it: the Dockerfile's `pip install .` now
  resolves `aignite-groundwork` from a `git+https` URL, and `python:3.12-slim` ships no git.
- **Root cause**: The CI environment was never given the dev-shaped inputs the compose file
  assumes (env file present, git available in the build image).
- **Fix**: CI smoke job copies the committed `.env.example` to `.env` before compose (the same
  step the README gives a stranger); Dockerfile installs git before `pip install`.
- **Doctrine link**: Standard 1 (root cause from the real log, not a retry) and Standard 2 (the
  smoke gate exists to catch exactly this before anyone calls the estate "green").

## FAIL-0004 — First real eval_llm run: paraphrase jaccard 0.00 against a 0.6 bound

- **Date**: 2026-07-27
- **Surface**: `scripts/eval_llm.py` (key-gated context-sensor eval, model
  `google/gemini-2.5-flash` via the gateway), first live run.
- **Reported symptom**: `EVAL_LLM FAILED` — planted-anchor recall 0.50 (bound 0.5, barely
  passing) and paraphrase jaccard (min) 0.00 against the contract's 0.6 bound. The base
  note extracted `weather:decrease` for a heat wave; one paraphrase produced an anchor set
  with no overlap at all.
- **Diagnosed cause**: A probe rerun on the failing paraphrase returned `weather:increase`
  — the heat-wave DIRECTION flip-flopped between runs. The sensing task was ill-posed: the
  prompt asked for "expected effect on demand" without saying demand for *what*. Whether a
  heat wave raises or lowers demand genuinely depends on what the store sells; the model
  was being asked to guess missing context, and the guess was unstable. A second hazard sat
  beside it: the pre-authored paraphrase contained a Unicode em dash, an avoidable
  round-trip risk for the verbatim `span_anchor` quote gate.
- **Root cause**: Under-specified sensing task (no store context in the prompt), not model
  flakiness. Canonical anchors (`signal_type:direction`) did their job: they made the
  instability measurable instead of hiding it behind label naming.
- **Fix**: `extract_signals` now injects a store profile into the system prompt
  (`DEFAULT_STORE_CONTEXT`, single-store in Phase 1, per-store in Phase 2), making
  direction well-posed; the paraphrase set is ASCII-only. Observed after the fix:
  recall 1.00, per-paraphrase jaccard [1.0, 1.0], `EVAL_LLM OK`. The bounds were not
  moved.
- **Doctrine link**: the eval bound caught it before any release claim (EVAL.md is the
  gate); Standard 1 (root cause: the task definition, not a retry loop); the
  canonicalize-then-compare rule (model-invented labels are not stable identity) is what
  made the failure visible and diagnosable.

## FAIL-0005 — Gate re-run: smoke failed with repaired_days=35 where 28 was asserted

- **Date**: 2026-07-27
- **Surface**: `scripts/smoke_test.py` via `scripts/gate.py` (second full gate run of the
  session, against the same persistent Postgres).
- **Reported symptom**: `GATE FAIL: smoke ... 'repaired_days': 35` — the first gate run had
  passed with identical code.
- **Diagnosed cause**: The smoke test reused the fixed SKU key `SMOKE-SKU` and asserted
  `repaired_days == 28` after ingesting 28 days. But the previous smoke run had already
  stored 28 history days plus 7 actuals for that SKU, and `POST /api/v1/ingest`
  deliberately recomputes the repaired series over the SKU's FULL stored history
  (idempotent by (sku, date), cumulative by design). 28 + 7 = 35. The product behaved
  correctly; the smoke assertion assumed a clean database it has no right to assume.
- **Root cause**: A test-side hidden-state assumption (fresh DB per run), not an
  application defect.
- **Fix**: The smoke test now mints a run-unique SKU key per invocation, keeping every
  assertion exact against a persistent database. Gate re-run observed green twice in a row.
- **Doctrine link**: Standard 2 (smoke against a real instance is exactly where
  clean-room assumptions die) and Standard 5 (documented what was actually broken — the
  test — versus what was reported — the loop).

## FAIL-0006 — Adversarial review wave: 7 confirmed findings before release

- **Date**: 2026-07-27
- **Surface**: `app/routes.py`, `app/engine/ingest.py`, `pyproject.toml`,
  `.github/workflows/ci.yml`, `scripts/check_migrations.py`.
- **Reported symptom**: None — every finding was latent. An adversarial code review of the
  Phase 1 loop confirmed 7 defects (3 major, 4 minor) that all gates had passed over.
- **Worst findings**:
  - `POST /api/v1/autopsy` never verified that an explicit `forecast_id` belonged to the
    requested `sku_id`, so a cross-SKU forecast was silently scored against the wrong
    SKU's actuals with a 200 response — a wrong-number, not an error (major).
  - `_load_forecast` subscripted the `None` from `.mappings().first()` for a nonexistent
    user-supplied `forecast_id`: an unhandled TypeError 500 instead of a typed 404,
    violating Standard 3 (major).
  - `[tool.setuptools] packages = ["app"]` omitted `app.engine`, so any wheel or
    non-editable install shipped without the deterministic engine; the Docker image only
    worked because `COPY . .` shadowed the broken site-packages install (major).
  - Plus: blank/missing `stockout` silently imported as `False`; the LLM call ran inside
    an open DB transaction; the CI test job swallowed install failures with `|| echo`;
    `check_migrations.py` degraded to a vacuous check when `EXPECTED_TABLE_COUNT` was
    unset.
- **Root cause**: Happy-path blindness — every endpoint was exercised through the loop's
  own derivation (`_latest_forecast_id`), never with adversarial user-supplied ids or
  truncated input; and infrastructure checks trusted their configuration to exist.
- **Fix**: All 7 findings fixed at the root with regression tests (cross-SKU 422,
  missing-forecast 404, blank/truncated stockout rejection, LLM-call-outside-session
  assertion). One refuted claim (keyless GET signals) was confirmed as documented design,
  not a defect.
- **Doctrine link**: Standard 3 (fail loud with a typed error), Standard 4 (assert the
  table count — a gate that can silently skip itself is not a gate), and the review-before-
  release rule: the adversarial pass caught all of this before any release claim.

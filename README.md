# Almanac

> **Status: scaffold (v0.1).** The engineering harness is built and verified: live smoke test,
> fail-loud guards, migration checks, CI. The architecture described below is the design being
> built; Phase 1 is in progress. [ROADMAP.md](ROADMAP.md) shows what exists today versus what
> is next.

**Smart inventory forecasting for retail: the LLM as a context sensor over a deterministic core.**

The forecast that reads the news, while the math stays math. A deterministic statistical engine
owns every number. The LLM does what a 30-year veteran store manager does: it reads the world
(weather, local events, school calendars, supplier messages, social trends) and turns it into
structured signals that must earn their influence in backtests before they touch a live order.

## What it is

Almanac gives small and mid-size retailers demand forecasts and inventory decisions (reorders,
transfers, markdowns) that combine rigorous time-series math with the contextual judgment big chains
staff whole planning departments to provide, as free, self-hostable software a single-store owner
can run. It is built for the shops no enterprise vendor will ever serve, including emerging-market
retailers with sparse data and messy multilingual signals.

The governing rule is a hard wall: **the language model never emits a number that enters the
forecast.** Enterprise demand platforms are statistically serious but priced and staffed for chains.
LLM-era tools bolt a chatbot onto a spreadsheet and, at worst, let a model emit demand numbers
directly: malpractice, because LLMs are unreliable arithmetic engines (the tools we reviewed as of
July 2026). The real determinant of small-retail forecast error is rarely the algorithm; it is
context the algorithm never saw. Almanac productizes that judgmental forecasting while keeping the
model permanently away from the arithmetic.

## How it works (the design)

1. **Repair the history before forecasting it.** A deterministic data-quality layer flags stockout
   intervals, estimates lost sales with explicit assumptions, separates returns and one-off bulk
   orders, and assigns a data-quality confidence per SKU. Observed sales are not demand.
2. **The statistical core does the math.** Seasonal decomposition, ETS and Croston-class intermittent
   models, LightGBM with engineered covariates, hierarchical reconciliation, and quantile output
   (P10/P50/P90). Deterministic and versioned.
3. **The Signal Scout senses context.** Scheduled agents read weather, event calendars, school
   schedules, social trends, and (with permission) the supplier inbox in any language. Output is
   never prose, it is a typed event signal with checkable provenance. The owner confirms or edits
   any signal before it can influence a recommendation.
4. **Influence is earned in the backtest arena.** A new signal class enters quarantine and earns
   live weight only after backtests show it improves error on held-out history, demoted
   automatically on decay. A public scoreboard tracks which sources have earned trust.
5. **Decisions, not integers.** The optimizer (newsvendor quantities, safety stock, reorder points)
   emits an action envelope with a regret map, and after each period a forecast autopsy decomposes
   the miss across model, data quality, signal, and owner override.

## What exists today (verified)

This scaffold's doctrine is already enforced, not promised. Three checks you can run in five minutes:

1. `python scripts/smoke_test.py` against a running instance: hits real endpoints and asserts
   non-empty, schema-valid data. Passes.
2. Set `APP_ENV=production` and call `/api/v1/demo`: returns 503, because fixture data outside
   development is forbidden by code, not by convention.
3. `python scripts/eval.py`: raises loudly instead of passing vacuously. An eval that cannot
   fail is theater; the real harness lands in Phase 1.

## The unique bet

No open forecasting tool we reviewed (July 2026) combines censored-demand repair, context signals that must earn influence in public backtests, regret-mapped decision envelopes, and per-period miss autopsies. That combination is the bet.

The full scoped novelty statement, with the field surveyed, is in [PRD.md](PRD.md).

Earned influence is terrible marketing, a quarantine period where the AI layer visibly
does nothing until it proves lift contradicts every vendor's "AI impact from day one" pitch. Open
source has no pitch to protect, so the public scoreboard becomes the feature.

## Quickstart (local, zero external keys)

### Standalone clone

```bash
python -m venv .venv
source .venv/bin/activate         # POSIX     (.venv\Scripts\activate on Windows)
pip install -e .[dev]             # groundwork resolves from GitHub automatically
cp .env.example .env              # POSIX     (copy .env.example .env on Windows)
uvicorn app.main:app --reload
```

### Developing the whole portfolio (sibling checkout, editable)

```bash
git clone https://github.com/nuwansamaranayake/groundwork ../groundwork
pip install -e ../groundwork
pip install -e .[dev]
```

Then, in another shell:

```bash
export API_PORT=8000 SMOKE_TEST_TOKEN=dev && python scripts/smoke_test.py   # POSIX -> SMOKE OK
set API_PORT=8000 && set SMOKE_TEST_TOKEN=dev && python scripts/smoke_test.py  # Windows
```

The `/api/v1/demo` endpoint serves the synthetic dataset in `data/synthetic/`: no OpenRouter key, Postgres, or Redis is needed to see the app respond. Those are required only for Phase 1 features (real extraction, persistence, migrations).

## Demo

A recorded walkthrough (screenshot / GIF of the action envelope shifting as a confirmed festival
signal earns its weight) lands with the Next.js frontend in Phase 2. Until then, the demo surface is
the JSON API above and the synthetic dataset.

## Doctrine

The operating rules that keep the model out of the arithmetic, and every other non-negotiable this
repo was built under, live in [DOCTRINE.md](DOCTRINE.md).

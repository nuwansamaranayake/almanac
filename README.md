# Almanac

**Smart inventory forecasting for retail: the LLM as a context sensor over a deterministic core.**

The forecast that reads the news, while the math stays math. A deterministic statistical engine
owns every number. The LLM does what a 30-year veteran store manager does: it reads the world
(weather, local events, school calendars, supplier messages, social trends) and turns it into
structured signals that must earn their influence in backtests before they touch a live order.

## What it is

Almanac gives small and mid-size retailers demand forecasts and inventory decisions (reorders,
transfers, markdowns) that combine rigorous time-series math with the contextual judgment big chains
staff whole planning departments to provide — as free, self-hostable software a single-store owner
can run. It is built for the shops no enterprise vendor will ever serve, including emerging-market
retailers with sparse data and messy multilingual signals.

The governing rule is a hard wall: **the language model never emits a number that enters the
forecast.** Enterprise demand platforms are statistically serious but priced and staffed for chains.
LLM-era tools bolt a chatbot onto a spreadsheet and, at worst, let a model emit demand numbers
directly — malpractice, because LLMs are unreliable arithmetic engines. The real determinant of
small-retail forecast error is rarely the algorithm; it is context the algorithm never saw. Almanac
productizes that judgmental forecasting while keeping the model permanently away from the arithmetic.

## How it works

1. **Repair the history before forecasting it.** A deterministic data-quality layer flags stockout
   intervals, estimates lost sales with explicit assumptions, separates returns and one-off bulk
   orders, and assigns a data-quality confidence per SKU. Observed sales are not demand.
2. **The statistical core does the math.** Seasonal decomposition, ETS and Croston-class intermittent
   models, LightGBM with engineered covariates, hierarchical reconciliation, and quantile output
   (P10/P50/P90). Deterministic and versioned.
3. **The Signal Scout senses context.** Scheduled agents read weather, event calendars, school
   schedules, social trends, and (with permission) the supplier inbox in any language. Output is
   never prose — it is a typed event signal with checkable provenance. The owner confirms or edits
   any signal before it can influence a recommendation.
4. **Influence is earned in the backtest arena.** A new signal class enters quarantine and earns
   live weight only after backtests show it improves error on held-out history — demoted
   automatically on decay. A public scoreboard tracks which sources have earned trust.
5. **Decisions, not integers.** The optimizer (newsvendor quantities, safety stock, reorder points)
   emits an action envelope with a regret map, and after each period a forecast autopsy decomposes
   the miss across model, data quality, signal, and owner override.

## The unique bet

The only open forecasting system where an LLM turns real-world context into typed signals that must
earn statistical influence through public backtests, feeding a deterministic engine that repairs
censored demand, outputs decision envelopes with regret analysis, and grades itself in public
autopsies. Earned influence is terrible marketing — a quarantine period where the AI layer visibly
does nothing until it proves lift contradicts every vendor's "AI impact from day one" pitch. Open
source has no pitch to protect, so the public scoreboard becomes the feature.

## Quickstart (local, zero external keys)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on POSIX)
pip install -e ../groundwork      # sibling shared library (uv users: uv sync)
pip install -e .[dev]
copy .env.example .env            # leave keys blank; the demo runs on synthetic data
uvicorn app.main:app --reload
```

In another shell:

```bash
set API_PORT=8000 && set SMOKE_TEST_TOKEN=dev && python scripts/smoke_test.py   # -> SMOKE OK
```

The `/api/v1/demo` endpoint serves the synthetic dataset in `data/synthetic/` — no OpenRouter
key, Postgres, or Redis needed to see the app respond. Those are required only for Phase 1
features (real extraction, persistence, migrations).

## Demo

A recorded walkthrough (screenshot / GIF of the action envelope shifting as a confirmed festival
signal earns its weight) lands with the Next.js frontend in Phase 2. Until then, the demo surface is
the JSON API above and the synthetic dataset.

## Doctrine

The operating rules that keep the model out of the arithmetic — and every other non-negotiable this
repo was built under — live in [DOCTRINE.md](DOCTRINE.md).

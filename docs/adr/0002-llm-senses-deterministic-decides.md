# 2. The LLM senses, deterministic code decides

Date: 2026-07-21

## Status

Accepted

## Context

Almanac forecasts demand and recommends inventory decisions for retailers who cannot afford to be
wrong about cash. Two design cultures both fail this user. Enterprise demand platforms have serious
operations-research math but enterprise pricing and staffing. LLM-era tools bolt a chatbot onto a
spreadsheet and, at worst, let a language model emit demand numbers directly. That last move is
malpractice: LLMs are unreliable arithmetic engines, and an inventory decision is arithmetic under
uncertainty.

Yet the dominant driver of small-retail forecast error is not the algorithm. It is context the
algorithm never saw — the festival two blocks away, the heat wave, a supplier's WhatsApp message about
a two-week delay, a product going viral regionally. That context is real, and until LLMs it was
economically unmappable into a covariate schema. So we need the LLM's perception without ever letting
it touch a number.

## Decision

We draw the boundary exactly where the portfolio thesis draws it: **the LLM is a sensor, not a judge.**

**What the LLM senses (non-deterministic):** it reads unstructured external sources — weather feeds,
event and school calendars, regional social trends, and (with permission) multilingual supplier
messages — and emits *typed event signals only*, never prose and never numbers that enter the model.
Each signal is a schema-forced object: event type, affected window, affected categories, direction, a
prior-elasticity distribution, checkable provenance, and a verification status. Supplier-message
interpretation is claim-typed the same way. Natural-language scenarios are parsed to typed,
feasibility-validated parameters. Plan narration is grounded in the audit record.

**What deterministic code decides and computes:** demand repair and censoring adjustment on the raw
history; all forecasting math (seasonal decomposition, ETS, Croston-class, LightGBM, hierarchical
reconciliation, P10/P50/P90 quantiles); the backtest arena and signal scoreboard; the optimizer
(newsvendor, safety stock, reorder points), action envelopes, and regret maps; the autopsy that
decomposes each period's miss; and the calendar/geo validation of every signal.

Two deterministic gates stand between a sensed signal and any effect on an order: the **owner
confirms** the signal, and the signal's class must have **earned influence in backtests** (quarantine
until proven, weighted by demonstrated lift, demoted on decay). No LLM output is ever a demand value,
a quantity, a price, or a submitted order.

## Consequences

- The load-bearing wall is explicit and testable: any code path where a model output becomes a
  forecast or order number is a defect, and the eval suite isolates and reports the LLM layer's
  marginal lift separately so its influence is always auditable.
- Reviewers can see, from the data model alone, which fields a model may write (signals, claims,
  parsed scenario parameters) and which it may never touch (forecasts, envelopes, orders).
- We accept a "boring" cost: a quarantine period where the AI layer visibly does nothing until it
  proves lift. That is honest engineering and poor marketing — acceptable because open source has no
  pitch to protect and the public scoreboard becomes the feature.
- Prompt injection is contained by construction: an instruction hidden in a supplier message can, at
  most, produce a signal that still needs human confirmation and a backtest before it means anything.
- If a future stage needs a model to produce a number, it does not get an exception — it gets a
  superseding ADR that argues the case in public.

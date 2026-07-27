# Almanac — Evaluation

Releases are gated on measured behavior, not vibes. `make eval` runs the suite below and must pass
its thresholds before a release is cut.

**Status: Phase 1 harness implemented and passing.** `scripts/eval.py` runs the deterministic
suite below against the pre-written thresholds and exits nonzero on any miss. Observed on
2026-07-27 (fixed seeds, two consecutive runs byte-identical): repair MAPE 0.0687, forecast
MAPE 0.0862, envelope monotonicity 1.0, envelope sanity 1.0 — report committed as
`eval_report.md`. The key-gated `scripts/eval_llm.py` was run for real through the gateway
(google/gemini-2.5-flash): planted-anchor recall 1.00, paraphrase anchor jaccard 1.0
(`eval_report_llm.md`); its first run failed and the diagnosis is FAILURES.md FAIL-0004.
The sections following the thresholds describe the full evaluation program this repo grows
into (M5-class backtests, planted-signal recovery, decision simulation); those are Phase 2+
targets, not current measurements.

## Phase 1 acceptance thresholds (written before the harness, 2026-07-27)

Phase 1 ships the deterministic core loop (CSV ingest, censored-demand repair, seasonal
weekday forecast with empirical intervals, newsvendor-style action envelopes, miss-autopsy
stubs), so its bounds measure that loop. The suite is deterministic and keyless: a seeded
synthetic sales generator with known weekday seasonality and planted stockouts (the truth is
known because we planted it), run end to end through the real engine modules.
`scripts/eval.py` exits nonzero on any miss and writes a byte-reproducible `eval_report.md`.

| Metric | Definition | Bound |
|---|---|---|
| Repair error | MAPE of imputed demand vs the true planted demand on stockout-flagged days | <= 20% |
| Forecast MAPE | MAPE of P50 vs true demand on held-out synthetic weeks (never seen in training) | <= 25% |
| Envelope monotonicity | share of service-level steps where a higher service level shrinks the order-quantity upper bound | = 0 violations (score 1.0) |
| Envelope sanity | share of envelopes with lower <= point <= upper | = 1.0 |
| Reproducibility | two consecutive `python scripts/eval.py` runs | byte-identical reports |

The LLM context-sensor stage is measured separately and key-gated: `scripts/eval_llm.py`
extracts demand signals from a planted event note and pre-authored paraphrases through the
real gateway and compares canonicalized anchors (`signal_type:direction`, schema-enforced
enums, never model-invented labels). Its bounds, stated before its first run: planted-anchor
recall >= 0.5 and paraphrase anchor Jaccard (min) >= 0.6 — the same invariant declared in
`contracts/context-sensor-stability.yaml` (Seismograph DSL). Never a required keyless check,
never a silent skip: the deterministic report states loudly whether the key-gated section ran.

## Published limits

This sentence is what the root page publishes, verbatim. The gate fails if the page and this block drift apart.

<!-- LIMITS -->
On a seeded synthetic store with planted stockouts, censored-demand repair lands within 6.9% of the planted true demand (MAPE 0.0687 against a 0.20 bound) and the forecast within 8.6% on held-out days (MAPE 0.0862 against a 0.25 bound), with order envelopes always correctly ordered and monotone in service level (1.0); the generator is synthetic and stationary, so it does not measure accuracy against real retail demand, promotions or supply shocks.
<!-- /LIMITS -->


## What good means

Almanac is good when its numbers beat the naive baseline, when the LLM signal layer's contribution is
isolated and reported honestly (including when it is zero or negative), and when the whole
Scout-to-signal-to-decision pipeline recovers effects we plant into synthetic data.

## How `make eval` will measure it

1. **Forecast accuracy vs baselines.** Backtests on public retail datasets (M5 and similar) plus
   synthetic stores. Report WAPE and bias against two references: seasonal-naive, and the statistical
   core alone. Target: beat seasonal-naive on WAPE and bias across the held-out windows.

2. **Isolated LLM marginal lift.** Run the pipeline with and without the confirmed signal layer and
   report the difference. The layer's contribution is stated on its own — if it does not help, the
   report says so. Target: no release claims lift the isolation test does not show.

3. **Planted-signal recovery.** Inject synthetic events with known effects (a festival with a known
   elasticity, a heat wave with a known lift) and measure whether the Scout-to-signal pipeline
   recovers the injected effect end to end. Target: recovered direction and magnitude within a stated
   tolerance of the planted effect.

4. **Decision quality under simulation.** Run simulated inventory episodes against the action
   envelopes and score service level, stockouts, waste, and realized regret. Target: dominate the
   seasonal-naive reorder policy on the service-level / waste frontier.

5. **Calibration honesty.** Compare stated quantile intervals (P10/P50/P90) to realized outcomes;
   publish realized error per release. Target: quantile coverage close to nominal, and every release
   ships its own calibration numbers even when they are unflattering.

6. **Extraction consistency.** Seismograph (App 1) monitors the Scout's extraction consistency and
   schema stability across model versions, so a signal schema drift is caught as a regression rather
   than discovered in production.

Red-team prompt-injection cases (a supplier message that tries to issue instructions rather than
report a fact) ship in the eval suite per the shared security baseline. Every eval report is published
with the release it gates.

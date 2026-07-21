# Almanac — Evaluation

Releases are gated on measured behavior, not vibes. `make eval` runs the suite below and must pass
its thresholds before a release is cut.

**Status: not yet implemented.** The harness intentionally raises `NotImplementedError` until the
Phase 1 statistical core exists (see ROADMAP.md). The numbers below are the targets that harness will
enforce once wired — they are goals, not achieved measurements. No eval report has been published yet.

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

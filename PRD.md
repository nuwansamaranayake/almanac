# Almanac — Product Requirements

## Users

- **Single-store owner-operator.** Runs a shop with no planning staff, orders on gut and a
  spreadsheet, and eats every stockout and every pile of dead stock personally. The primary user.
- **Small-chain inventory manager.** Two to a dozen locations, some transfers between them, still no
  budget for an enterprise demand-planning seat.
- **Emerging-market retailer.** Sparse SKU history, messy and multilingual supplier communication,
  and context (festivals, weather, local closures) that no off-the-shelf vendor models.
- **Self-hosting technical operator.** The person who stands the tool up for the above — often a
  contractor or a family member — and needs a five-minute demo and honest error states.

## Jobs to be done

- "Tell me how many units to reorder, and how sure you are." Quantile forecasts (P10/P50/P90) and an
  action envelope with a safe range, latest order date, cash required, and downside exposure.
- "Don't let a past stockout teach you to under-order forever." Deterministic demand repair on
  censored history before any model sees it.
- "Account for the festival, the heat wave, the supplier's delay message" — without letting a chatbot
  invent a number. Typed, provenance-carrying signals the owner confirms, that earn influence only in
  backtests.
- "Let me pick a risk posture." A regret map across candidate decisions (best on average, smallest
  worst case, most cash-protective) instead of one opaque integer.
- "Tell me honestly when you were wrong." A per-period forecast autopsy that attributes the miss to
  model, data quality, signal, or the owner's override.

## Non-goals

- **The LLM never emits a number that enters the forecast or the order.** No model-generated demand
  values, quantities, or prices. This is the load-bearing exclusion, not a limitation.
- **No auto-submitted purchase orders.** Every order is a human-approved draft; the tool informs a
  decision, it does not make one.
- **No signal acts on day one.** New signal classes sit in quarantine until they prove lift. Visible
  inaction is intended behavior.
- **No certainty theater.** Probabilistic outputs are always rendered as ranges, never as a single
  confident number.
- **No supplier-inbox ingestion without explicit permission**, and no phase-jumping: the Next.js UI,
  scenario console, and multi-store hierarchy are later phases, not Phase 1.

## Success metrics (targets, not yet measured)

Derived from the evaluation plan; the Phase 1 harness will enforce these as gates (see EVAL.md):

- **Forecast accuracy:** WAPE and bias beat seasonal-naive on public retail datasets (M5 and similar)
  plus synthetic stores.
- **Honest marginal lift:** the LLM signal layer's contribution is isolated and reported against the
  statistical core alone — including when it is zero or negative.
- **Signal pipeline integrity:** planted-signal tests (synthetic events with known effects) recover
  the injected effect end to end through the Scout-to-signal pipeline.
- **Decision quality:** simulated inventory runs score service level, stockouts, waste, and realized
  regret against the action envelopes.
- **Calibration honesty:** realized error is published per release, so failure becomes visible
  calibration rather than silent erosion of trust.

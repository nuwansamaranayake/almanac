"""Censored-demand repair: observed sales are not demand (BLUEPRINT core idea 2).

When a SKU was out of stock, low sales reflect missing supply, not missing desire. A model
trained on censored history learns to under-order forever. This module repairs the history
deterministically before any forecasting touches it.

The rule, stated in full (and asserted by tests and the eval suite):

  For every stockout-flagged day, the imputed demand is the MEDIAN of units sold on the
  SAME WEEKDAY across all non-stockout days in the series. If that weekday has no clean
  (non-stockout) history, fall back to the median over all non-stockout days. If the
  series has no clean days at all, the observed value is kept unchanged (nothing to learn
  from). The repaired value is max(observed, imputed): sales recorded during a stockout
  are a floor on demand, never the demand.

No LLM anywhere near this path. Pure arithmetic, same input -> same output, always.
"""
from __future__ import annotations

from datetime import date
from statistics import median

from pydantic import BaseModel

RULE_WEEKDAY_MEDIAN = "same_weekday_median"
RULE_OVERALL_MEDIAN = "overall_median_fallback"
RULE_OBSERVED_KEPT = "observed_kept_no_clean_history"
RULE_NOT_STOCKOUT = "not_stockout"


class DailySale(BaseModel):
    """One observed day for one SKU."""
    day: date
    units: float
    stockout: bool = False


class RepairedDay(BaseModel):
    """The repaired view of one day: observed kept, repaired stated, rule named."""
    day: date
    observed: float
    repaired: float
    was_stockout: bool
    rule: str


def repair_series(series: list[DailySale]) -> list[RepairedDay]:
    """Repair one SKU's daily series per the documented rule. Deterministic; order-stable."""
    ordered = sorted(series, key=lambda s: s.day)
    clean = [s for s in ordered if not s.stockout]
    clean_by_weekday: dict[int, list[float]] = {}
    for s in clean:
        clean_by_weekday.setdefault(s.day.weekday(), []).append(s.units)
    overall = [s.units for s in clean]

    out: list[RepairedDay] = []
    for s in ordered:
        if not s.stockout:
            out.append(RepairedDay(day=s.day, observed=s.units, repaired=s.units,
                                   was_stockout=False, rule=RULE_NOT_STOCKOUT))
            continue
        weekday_units = clean_by_weekday.get(s.day.weekday(), [])
        if weekday_units:
            imputed, rule = median(weekday_units), RULE_WEEKDAY_MEDIAN
        elif overall:
            imputed, rule = median(overall), RULE_OVERALL_MEDIAN
        else:
            imputed, rule = s.units, RULE_OBSERVED_KEPT
        out.append(RepairedDay(day=s.day, observed=s.units,
                               repaired=max(s.units, imputed),
                               was_stockout=True, rule=rule))
    return out

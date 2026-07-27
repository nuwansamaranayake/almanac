"""Per-period miss autopsy, Phase 1 stub: forecast vs actual, deterministically compared.

When actuals arrive for dates a forecast covered, this module scores the miss per day
(error, absolute percentage error, band coverage) and in aggregate (MAPE, bias, coverage).
It is called a stub honestly: the blueprint's full autopsy decomposes a miss into model
error vs data-quality error vs signal error vs owner override, which requires the signal
quarantine and backtest arena — Phase 2 machinery. What ships now is the deterministic
comparison those decompositions will build on.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .forecast import Forecast


class DayMiss(BaseModel):
    day: date
    actual: float
    p10: float
    p50: float
    p90: float
    error: float                 # actual - p50; positive = under-forecast
    ape: float | None            # |error| / actual; None when actual == 0
    within_band: bool            # p10 <= actual <= p90


class AutopsyReport(BaseModel):
    days_scored: int
    mape: float | None           # mean APE over days where actual > 0
    bias: float                  # mean(actual - p50); positive = systematic under-forecast
    band_coverage: float         # share of scored days inside [p10, p90]
    days: list[DayMiss]
    note: str


NOTE = ("Phase 1 stub: deterministic forecast-vs-actual comparison. Decomposition into "
        "model / data-quality / signal / override error lands with the backtest arena "
        "in Phase 2.")


def run_autopsy(forecast: Forecast, actuals: dict[date, float]) -> AutopsyReport:
    """Score every forecast day that has an actual. Raises when there is no overlap."""
    days: list[DayMiss] = []
    for p in forecast.points:
        if p.day not in actuals:
            continue
        actual = actuals[p.day]
        error = actual - p.p50
        days.append(DayMiss(
            day=p.day, actual=actual, p10=p.p10, p50=p.p50, p90=p.p90, error=error,
            ape=abs(error) / actual if actual > 0 else None,
            within_band=p.p10 <= actual <= p.p90))
    if not days:
        raise ValueError("no overlap between forecast days and provided actuals")
    apes = [d.ape for d in days if d.ape is not None]
    return AutopsyReport(
        days_scored=len(days),
        mape=sum(apes) / len(apes) if apes else None,
        bias=sum(d.error for d in days) / len(days),
        band_coverage=sum(1 for d in days if d.within_band) / len(days),
        days=days,
        note=NOTE)

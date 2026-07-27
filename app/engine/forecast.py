"""The Phase 1 statistical core: seasonal moving average with weekday seasonality and
empirical prediction intervals. Deterministic, versioned by name, pure stdlib.

Method (`seasonal_weekday_ma`):
  * Fit: the per-weekday mean of the (repaired) training series is the seasonal profile.
  * Point: the forecast for a future date is the mean for that date's weekday.
  * Intervals: residuals (actual - fitted) over the training days are collected once;
    P10/P50/P90 are the point plus the empirical 0.10/0.50/0.90 residual quantiles
    (linear interpolation between order statistics), clamped at zero. Quantile
    monotonicity guarantees p10 <= p50 <= p90 on every point.

A point forecast hides exactly the uncertainty an ordering decision needs, so quantiles
are the primary output, not an afterthought. The LLM never touches this module: no model
emits a number that enters the forecast (the load-bearing wall).
"""
from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

from .repair import RepairedDay

METHOD = "seasonal_weekday_ma"


class ForecastPoint(BaseModel):
    day: date
    p10: float
    p50: float
    p90: float


class Forecast(BaseModel):
    method: str
    train_start: date
    train_end: date
    horizon_days: int
    points: list[ForecastPoint]


def empirical_quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation quantile over pre-sorted values. Deterministic, stdlib-only."""
    if not sorted_values:
        raise ValueError("cannot take a quantile of an empty list")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def forecast_series(history: list[RepairedDay], horizon_days: int) -> Forecast:
    """Forecast `horizon_days` daily quantiles from a repaired history.

    Raises on empty history or a weekday in the horizon that has no training history —
    refusing loudly beats inventing a number (Standard 3).
    """
    if not history:
        raise ValueError("cannot forecast from an empty history")
    if horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")
    ordered = sorted(history, key=lambda r: r.day)
    by_weekday: dict[int, list[float]] = {}
    for r in ordered:
        by_weekday.setdefault(r.day.weekday(), []).append(r.repaired)
    weekday_mean = {wd: sum(v) / len(v) for wd, v in by_weekday.items()}

    residuals = sorted(r.repaired - weekday_mean[r.day.weekday()] for r in ordered)
    q10 = empirical_quantile(residuals, 0.10)
    q50 = empirical_quantile(residuals, 0.50)
    q90 = empirical_quantile(residuals, 0.90)

    train_end = ordered[-1].day
    points: list[ForecastPoint] = []
    for i in range(1, horizon_days + 1):
        target = train_end + timedelta(days=i)
        if target.weekday() not in weekday_mean:
            raise ValueError(
                f"no training history for weekday {target.weekday()} ({target.isoformat()}); "
                "refusing to invent a seasonal level")
        point = weekday_mean[target.weekday()]
        points.append(ForecastPoint(
            day=target,
            p10=max(0.0, point + q10),
            p50=max(0.0, point + q50),
            p90=max(0.0, point + q90),
        ))
    return Forecast(method=METHOD, train_start=ordered[0].day, train_end=train_end,
                    horizon_days=horizon_days, points=points)

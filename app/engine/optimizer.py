"""The order optimizer: newsvendor-style ACTION ENVELOPES, not naked integers.

The output of a forecast is a decision aid, so the deliverable is a range with named
risk at both ends. All arithmetic here is deterministic; the LLM has no path into this
module (the load-bearing wall).

Construction, stated in full:
  * Horizon demand quantiles D10/D50/D90 are the sums of the daily P10/P50/P90 over the
    envelope horizon (a documented approximation: summing daily quantiles ignores
    day-to-day error correlation; honest and simple beats falsely precise).
  * The demand-quantile curve Dq(s) is piecewise-linear through (0.1, D10), (0.5, D50),
    (0.9, D90) and clamped flat outside [0.1, 0.9]. It is nondecreasing because
    D10 <= D50 <= D90 by quantile ordering.
  * At service level sl with on-hand stock h:
        lower = max(0, Dq(sl - 0.15) - h)     (cash-protective posture)
        point = max(0, Dq(sl) - h)            (the newsvendor quantity at sl)
        upper = max(0, Dq(sl + 0.15) - h)     (stockout-averse posture)
    with the evaluation points clamped to [0.05, 0.95]. Monotone in sl by construction,
    and lower <= point <= upper always.
  * Each bound carries a one-line regret note with the arithmetic shown: ordering the
    lower bound risks lost margin if demand lands high; ordering the upper bound risks
    cash tied in leftover stock if demand lands low.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .forecast import Forecast

POSTURE_SPREAD = 0.15
SL_FLOOR, SL_CEIL = 0.05, 0.95


class ActionEnvelope(BaseModel):
    service_level: float
    horizon_days: int
    on_hand: float
    demand_p10: float
    demand_p50: float
    demand_p90: float
    lower_qty: float
    point_qty: float
    upper_qty: float
    regret_lower: str
    regret_upper: str


class CostInputs(BaseModel):
    unit_cost: float = Field(gt=0)
    unit_price: float = Field(gt=0)


def demand_quantile(d10: float, d50: float, d90: float, s: float) -> float:
    """Piecewise-linear horizon-demand quantile, clamped flat outside [0.1, 0.9]."""
    if not d10 <= d50 <= d90:
        raise ValueError("quantiles out of order: require d10 <= d50 <= d90")
    if s <= 0.1:
        return d10
    if s >= 0.9:
        return d90
    if s <= 0.5:
        return d10 + (d50 - d10) * (s - 0.1) / 0.4
    return d50 + (d90 - d50) * (s - 0.5) / 0.4


def build_envelope(forecast: Forecast, service_level: float, on_hand: float,
                   costs: CostInputs) -> ActionEnvelope:
    """Deterministic envelope from a quantile forecast. Raises on unusable inputs."""
    if not 0.0 < service_level < 1.0:
        raise ValueError("service_level must be in (0, 1)")
    if on_hand < 0:
        raise ValueError("on_hand must be >= 0")
    if not forecast.points:
        raise ValueError("forecast has no points")

    d10 = sum(p.p10 for p in forecast.points)
    d50 = sum(p.p50 for p in forecast.points)
    d90 = sum(p.p90 for p in forecast.points)

    s_low = max(SL_FLOOR, min(SL_CEIL, service_level - POSTURE_SPREAD))
    s_mid = max(SL_FLOOR, min(SL_CEIL, service_level))
    s_high = max(SL_FLOOR, min(SL_CEIL, service_level + POSTURE_SPREAD))

    lower = max(0.0, demand_quantile(d10, d50, d90, s_low) - on_hand)
    point = max(0.0, demand_quantile(d10, d50, d90, s_mid) - on_hand)
    upper = max(0.0, demand_quantile(d10, d50, d90, s_high) - on_hand)

    margin = costs.unit_price - costs.unit_cost
    short_units = max(0.0, max(0.0, d90 - on_hand) - lower)
    leftover_units = max(0.0, upper - max(0.0, d10 - on_hand))
    regret_lower = (
        f"ordering {lower:.1f} risks up to {short_units:.1f} units short if demand hits "
        f"P90 ({d90:.1f}): lost margin up to {short_units * margin:.2f}")
    regret_upper = (
        f"ordering {upper:.1f} risks up to {leftover_units:.1f} units left over if demand "
        f"hits P10 ({d10:.1f}): cash at risk up to {leftover_units * costs.unit_cost:.2f}")

    return ActionEnvelope(
        service_level=service_level, horizon_days=forecast.horizon_days, on_hand=on_hand,
        demand_p10=round(d10, 3), demand_p50=round(d50, 3), demand_p90=round(d90, 3),
        lower_qty=round(lower, 3), point_qty=round(point, 3), upper_qty=round(upper, 3),
        regret_lower=regret_lower, regret_upper=regret_upper)

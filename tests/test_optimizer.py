from datetime import date, timedelta

import pytest

from app.engine.forecast import Forecast, ForecastPoint
from app.engine.optimizer import ActionEnvelope, CostInputs, build_envelope, demand_quantile

COSTS = CostInputs(unit_cost=1.0, unit_price=2.5)


def _forecast(days: int = 7, p10: float = 8.0, p50: float = 10.0, p90: float = 14.0):
    start = date(2026, 7, 1)
    return Forecast(
        method="seasonal_weekday_ma", train_start=start - timedelta(days=28),
        train_end=start - timedelta(days=1), horizon_days=days,
        points=[ForecastPoint(day=start + timedelta(days=i), p10=p10, p50=p50, p90=p90)
                for i in range(days)])


def test_envelope_sanity_lower_point_upper():
    for sl in [0.1, 0.3, 0.5, 0.7, 0.9, 0.95]:
        env = build_envelope(_forecast(), sl, on_hand=0.0, costs=COSTS)
        assert env.lower_qty <= env.point_qty <= env.upper_qty, sl


def test_envelope_monotone_in_service_level():
    levels = [i / 100 for i in range(5, 100, 5)]
    envs = [build_envelope(_forecast(), sl, on_hand=0.0, costs=COSTS) for sl in levels]
    for a, b in zip(envs, envs[1:]):
        assert b.upper_qty >= a.upper_qty
        assert b.point_qty >= a.point_qty
        assert b.lower_qty >= a.lower_qty


def test_point_matches_quantile_curve_and_on_hand_subtracts():
    env = build_envelope(_forecast(), 0.5, on_hand=0.0, costs=COSTS)
    assert env.point_qty == pytest.approx(70.0)          # 7 days * p50=10
    env_h = build_envelope(_forecast(), 0.5, on_hand=30.0, costs=COSTS)
    assert env_h.point_qty == pytest.approx(40.0)
    env_full = build_envelope(_forecast(), 0.5, on_hand=1000.0, costs=COSTS)
    assert env_full.point_qty == 0.0                     # never a negative order


def test_regret_notes_carry_the_arithmetic():
    env = build_envelope(_forecast(), 0.5, on_hand=0.0, costs=COSTS)
    assert "lost margin" in env.regret_lower and "98.0" in env.regret_lower  # D90 = 98
    assert "cash at risk" in env.regret_upper and "56.0" in env.regret_upper  # D10 = 56


def test_demand_quantile_curve_shape():
    assert demand_quantile(56, 70, 98, 0.05) == 56       # clamped low
    assert demand_quantile(56, 70, 98, 0.5) == 70
    assert demand_quantile(56, 70, 98, 0.98) == 98       # clamped high
    assert demand_quantile(56, 70, 98, 0.7) == pytest.approx(84.0)
    with pytest.raises(ValueError):
        demand_quantile(70, 56, 98, 0.5)


def test_rejects_bad_inputs():
    with pytest.raises(ValueError):
        build_envelope(_forecast(), 0.0, on_hand=0.0, costs=COSTS)
    with pytest.raises(ValueError):
        build_envelope(_forecast(), 0.5, on_hand=-1.0, costs=COSTS)
    empty = _forecast()
    empty = empty.model_copy(update={"points": []})
    with pytest.raises(ValueError):
        build_envelope(empty, 0.5, on_hand=0.0, costs=COSTS)


def test_envelope_is_a_model_with_stated_uncertainty():
    env = build_envelope(_forecast(), 0.9, on_hand=0.0, costs=COSTS)
    assert isinstance(env, ActionEnvelope)
    assert env.demand_p10 < env.demand_p50 < env.demand_p90

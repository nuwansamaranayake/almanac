from datetime import date, timedelta

import pytest

from app.engine.forecast import METHOD, empirical_quantile, forecast_series
from app.engine.repair import DailySale, repair_series
from app.engine.synth import WEEKDAY_PROFILE, generate_sku


def _clean_history(weeks: int = 4, level: float = 10.0):
    """Noise-free weekday-shaped history starting on a Monday."""
    start = date(2026, 6, 1)
    series = [
        DailySale(day=start + timedelta(days=i),
                  units=level * WEEKDAY_PROFILE[(start + timedelta(days=i)).weekday()])
        for i in range(weeks * 7)
    ]
    return repair_series(series)


def test_recovers_weekday_seasonality_exactly_on_clean_data():
    fc = forecast_series(_clean_history(), horizon_days=7)
    assert fc.method == METHOD
    for p in fc.points:
        expected = 10.0 * WEEKDAY_PROFILE[p.day.weekday()]
        assert p.p50 == pytest.approx(expected)
        assert p.p10 == pytest.approx(expected)   # zero residuals -> collapsed band


def test_quantiles_are_ordered_and_nonnegative_on_noisy_data():
    sku = generate_sku("S", 8.0, date(2026, 3, 2), weeks=8, stockout_rate=0.1, seed=7)
    fc = forecast_series(repair_series(sku.observed_series()), horizon_days=14)
    assert len(fc.points) == 14
    for p in fc.points:
        assert 0.0 <= p.p10 <= p.p50 <= p.p90


def test_horizon_dates_follow_train_end():
    fc = forecast_series(_clean_history(), horizon_days=3)
    assert fc.points[0].day == fc.train_end + timedelta(days=1)
    assert fc.points[-1].day == fc.train_end + timedelta(days=3)


def test_deterministic_same_input_same_output():
    h = _clean_history()
    assert forecast_series(h, 7) == forecast_series(h, 7)


def test_refuses_empty_history_and_bad_horizon():
    with pytest.raises(ValueError):
        forecast_series([], 7)
    with pytest.raises(ValueError):
        forecast_series(_clean_history(), 0)


def test_refuses_weekday_with_no_training_history():
    start = date(2026, 6, 1)  # Mondays only
    hist = repair_series([DailySale(day=start + timedelta(days=7 * i), units=5.0)
                          for i in range(4)])
    with pytest.raises(ValueError, match="weekday"):
        forecast_series(hist, horizon_days=1)     # next day is a Tuesday, never seen


def test_empirical_quantile_interpolates():
    vals = [0.0, 10.0]
    assert empirical_quantile(vals, 0.5) == 5.0
    assert empirical_quantile(vals, 0.0) == 0.0
    assert empirical_quantile(vals, 1.0) == 10.0
    with pytest.raises(ValueError):
        empirical_quantile([], 0.5)

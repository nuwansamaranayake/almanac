from datetime import date, timedelta

import pytest

from app.engine.autopsy import run_autopsy
from app.engine.forecast import Forecast, ForecastPoint


def _forecast():
    start = date(2026, 7, 1)
    return Forecast(
        method="seasonal_weekday_ma", train_start=start - timedelta(days=28),
        train_end=start - timedelta(days=1), horizon_days=3,
        points=[ForecastPoint(day=start + timedelta(days=i), p10=8.0, p50=10.0, p90=14.0)
                for i in range(3)])


def test_autopsy_scores_known_misses():
    start = date(2026, 7, 1)
    actuals = {start: 10.0, start + timedelta(days=1): 15.0, start + timedelta(days=2): 5.0}
    rep = run_autopsy(_forecast(), actuals)
    assert rep.days_scored == 3
    by_day = {d.day: d for d in rep.days}
    assert by_day[start].error == 0.0 and by_day[start].within_band
    assert by_day[start + timedelta(days=1)].error == 5.0            # under-forecast
    assert not by_day[start + timedelta(days=1)].within_band         # 15 > p90
    assert by_day[start + timedelta(days=2)].ape == pytest.approx(1.0)
    assert rep.bias == pytest.approx((0.0 + 5.0 - 5.0) / 3)
    assert rep.band_coverage == pytest.approx(1 / 3)
    assert "Phase 1 stub" in rep.note


def test_autopsy_partial_overlap_scores_only_overlap():
    start = date(2026, 7, 1)
    rep = run_autopsy(_forecast(), {start: 9.0, date(2030, 1, 1): 4.0})
    assert rep.days_scored == 1


def test_autopsy_zero_actual_has_no_ape_but_counts():
    start = date(2026, 7, 1)
    rep = run_autopsy(_forecast(), {start: 0.0})
    assert rep.days[0].ape is None
    assert rep.mape is None
    assert rep.bias == -10.0


def test_autopsy_refuses_no_overlap():
    with pytest.raises(ValueError, match="no overlap"):
        run_autopsy(_forecast(), {date(2030, 1, 1): 4.0})

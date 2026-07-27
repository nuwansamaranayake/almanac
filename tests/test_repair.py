from datetime import date

from app.engine.repair import (
    RULE_NOT_STOCKOUT,
    RULE_OBSERVED_KEPT,
    RULE_OVERALL_MEDIAN,
    RULE_WEEKDAY_MEDIAN,
    DailySale,
    repair_series,
)

MON1, MON2, MON3 = date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15)
TUE1 = date(2026, 6, 2)


def test_stockout_day_imputed_from_same_weekday_median():
    series = [
        DailySale(day=MON1, units=10.0),
        DailySale(day=MON2, units=14.0),
        DailySale(day=MON3, units=2.0, stockout=True),
    ]
    repaired = {r.day: r for r in repair_series(series)}
    assert repaired[MON3].repaired == 12.0          # median(10, 14)
    assert repaired[MON3].rule == RULE_WEEKDAY_MEDIAN
    assert repaired[MON3].observed == 2.0           # observed kept beside the repair
    assert repaired[MON1].rule == RULE_NOT_STOCKOUT
    assert repaired[MON1].repaired == 10.0


def test_observed_is_a_floor_on_demand():
    # Observed above the weekday median (partial-day stockout): keep the observed.
    series = [
        DailySale(day=MON1, units=10.0),
        DailySale(day=MON2, units=12.0),
        DailySale(day=MON3, units=20.0, stockout=True),
    ]
    repaired = {r.day: r for r in repair_series(series)}
    assert repaired[MON3].repaired == 20.0          # max(observed, imputed)


def test_weekday_without_clean_history_falls_back_to_overall_median():
    series = [
        DailySale(day=MON1, units=10.0),
        DailySale(day=MON2, units=30.0),
        DailySale(day=TUE1, units=1.0, stockout=True),   # no clean Tuesday exists
    ]
    repaired = {r.day: r for r in repair_series(series)}
    assert repaired[TUE1].repaired == 20.0          # median(10, 30) over all clean days
    assert repaired[TUE1].rule == RULE_OVERALL_MEDIAN


def test_no_clean_history_keeps_observed():
    series = [DailySale(day=MON1, units=3.0, stockout=True)]
    [r] = repair_series(series)
    assert r.repaired == 3.0
    assert r.rule == RULE_OBSERVED_KEPT


def test_repair_is_deterministic_and_order_stable():
    series = [
        DailySale(day=MON2, units=14.0),
        DailySale(day=MON3, units=2.0, stockout=True),
        DailySale(day=MON1, units=10.0),
    ]
    a = repair_series(series)
    b = repair_series(list(reversed(series)))
    assert a == b
    assert [r.day for r in a] == sorted(r.day for r in a)

"""Seeded synthetic store: known weekday seasonality, planted stockouts, known truth.

The eval suite needs ground truth that real sales data never provides: the demand a
stockout censored. So we plant it. True demand is generated from a base level times a
fixed weekday profile times bounded seeded noise; on planted stockout days the OBSERVED
sales are a censored fraction of the truth. The generator hands back both views, so
repair and forecast quality are measured against the truth we buried, not against vibes.

`random.Random(seed)` (Mersenne Twister) is deterministic across platforms and Python
versions, which keeps the eval report byte-reproducible.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from pydantic import BaseModel

from .repair import DailySale

# Mon..Sun multiplicative profile: quiet early week, weekend peak. Fixed by design.
WEEKDAY_PROFILE = [0.8, 0.9, 1.0, 1.0, 1.1, 1.6, 1.4]
NOISE_SPAN = 0.15          # true demand = base * profile * (1 + U(-0.15, +0.15))
CENSOR_CAP = 0.4           # observed on a stockout day = true * U(0.0, 0.4)


class SyntheticDay(BaseModel):
    day: date
    true_demand: float
    observed_units: float
    stockout: bool


class SyntheticSku(BaseModel):
    sku_key: str
    base_level: float
    days: list[SyntheticDay]

    def observed_series(self) -> list[DailySale]:
        return [DailySale(day=d.day, units=d.observed_units, stockout=d.stockout)
                for d in self.days]


def generate_sku(sku_key: str, base_level: float, start: date, weeks: int,
                 stockout_rate: float, seed: int) -> SyntheticSku:
    """One SKU's history. Same arguments -> byte-identical output, always."""
    rng = random.Random(seed)
    days: list[SyntheticDay] = []
    for i in range(weeks * 7):
        d = start + timedelta(days=i)
        true = base_level * WEEKDAY_PROFILE[d.weekday()] * (1.0 + rng.uniform(-NOISE_SPAN, NOISE_SPAN))
        true = round(true, 3)
        is_stockout = rng.random() < stockout_rate
        observed = round(true * rng.uniform(0.0, CENSOR_CAP), 3) if is_stockout else true
        days.append(SyntheticDay(day=d, true_demand=true, observed_units=observed,
                                 stockout=is_stockout))
    return SyntheticSku(sku_key=sku_key, base_level=base_level, days=days)


def generate_store(start: date = date(2026, 3, 2), weeks: int = 12,
                   stockout_rate: float = 0.1, seed: int = 20260727) -> list[SyntheticSku]:
    """Three SKUs at different volumes. start is a Monday so weeks align with the profile."""
    specs = [("SKU-COLA-330", 50.0), ("SKU-BREAD-800", 20.0), ("SKU-ICE-500", 8.0)]
    return [generate_sku(key, base, start, weeks, stockout_rate, seed + i)
            for i, (key, base) in enumerate(specs)]

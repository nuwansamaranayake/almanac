"""CSV sales-history parsing: the keyless entry path into the loop (a real product
feature, not a fallback — most small retailers have a spreadsheet, not an API).

Format (header required):
    sku,date,units_sold,stockout[,name,unit_cost,unit_price]

* `date` is ISO (YYYY-MM-DD); `stockout` accepts 0/1/true/false/yes/no.
* `name`, `unit_cost`, `unit_price` are optional SKU attributes; the last non-empty
  value in the file wins for its SKU.
* Validation is all-or-nothing with row numbers in the error: no partial silent imports.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from pydantic import BaseModel

from .repair import DailySale

REQUIRED_COLUMNS = ["sku", "date", "units_sold", "stockout"]
_TRUE = {"1", "true", "yes", "y"}
# The empty string is deliberately NOT in _FALSE: a blank or missing stockout cell must
# raise the row-numbered IngestError, never silently import as False (it would skew the
# censored-demand repair).
_FALSE = {"0", "false", "no", "n"}


class SkuBatch(BaseModel):
    sku_key: str
    name: str | None = None
    unit_cost: float | None = None
    unit_price: float | None = None
    sales: list[DailySale]


class IngestError(ValueError):
    """Raised with a row-numbered, human-readable reason. Never partially applied."""


def parse_sales_csv(text: str) -> list[SkuBatch]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise IngestError("empty CSV: a header row is required")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise IngestError(f"missing required columns: {missing}; "
                          f"header must contain {REQUIRED_COLUMNS}")

    batches: dict[str, SkuBatch] = {}
    seen: set[tuple[str, date]] = set()
    for i, row in enumerate(reader, start=2):          # row 1 is the header
        sku_key = (row.get("sku") or "").strip()
        if not sku_key:
            raise IngestError(f"row {i}: empty sku")
        try:
            day = date.fromisoformat((row.get("date") or "").strip())
        except ValueError:
            raise IngestError(f"row {i}: bad date {row.get('date')!r}; expected YYYY-MM-DD")
        try:
            units = float((row.get("units_sold") or "").strip())
        except ValueError:
            raise IngestError(f"row {i}: bad units_sold {row.get('units_sold')!r}")
        if units < 0:
            raise IngestError(f"row {i}: negative units_sold")
        flag_raw = (row.get("stockout") or "").strip().lower()
        if flag_raw in _TRUE:
            stockout = True
        elif flag_raw in _FALSE:
            stockout = False
        else:
            raise IngestError(f"row {i}: bad stockout {row.get('stockout')!r}; use 0/1/true/false")
        if (sku_key, day) in seen:
            raise IngestError(f"row {i}: duplicate (sku, date) pair ({sku_key}, {day})")
        seen.add((sku_key, day))

        batch = batches.setdefault(sku_key, SkuBatch(sku_key=sku_key, sales=[]))
        batch.sales.append(DailySale(day=day, units=units, stockout=stockout))
        for attr, cast in (("name", str), ("unit_cost", float), ("unit_price", float)):
            raw = (row.get(attr) or "").strip()
            if raw:
                try:
                    setattr(batch, attr, cast(raw))
                except ValueError:
                    raise IngestError(f"row {i}: bad {attr} {raw!r}")
    if not batches:
        raise IngestError("CSV contains a header but no data rows")
    return list(batches.values())

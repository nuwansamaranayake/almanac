"""Smoke: the REAL keyless processing loop against a running instance (Standard 2).

health -> demo fixture -> CSV ingest (repair) -> forecast -> envelope -> second ingest
(actuals arrive) -> autopsy. Every step asserts non-empty, schema-valid data. No LLM key
is needed: the deterministic loop is the product's keyless path, not a mock.
"""
import os
import sys
import time
from datetime import date, timedelta

import httpx

BASE = f"http://{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', '8000')}"
TOKEN = os.getenv("SMOKE_TEST_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

START = date(2026, 6, 1)                       # a Monday
LEVELS = [12, 14, 16, 16, 18, 30, 24]          # weekday-shaped demand
# Run-unique SKU: the smoke runs against a persistent database, and ingest recomputes
# repair over the FULL stored history for a SKU — reusing one key across runs made the
# repaired-day count grow (FAILURES.md FAIL-0005). A fresh key keeps assertions exact.
SKU = f"SMOKE-{int(time.time())}"


def _csv(days: int, first_day: date, stockout_day: int | None) -> str:
    rows = ["sku,date,units_sold,stockout,unit_cost,unit_price"]
    for i in range(days):
        d = first_day + timedelta(days=i)
        units = LEVELS[d.weekday()]
        if i == stockout_day:
            rows.append(f"{SKU},{d.isoformat()},2,1,,")
        else:
            cost = "1.0,2.5" if i == 0 else ","
            rows.append(f"{SKU},{d.isoformat()},{units},0,{cost}")
    return "\n".join(rows) + "\n"


def get(path: str):
    r = httpx.get(BASE + path, headers=HEADERS, timeout=10)
    r.raise_for_status()
    body = r.json()
    assert body, f"{path} returned an empty body"
    return body


def post(path: str, payload: dict):
    r = httpx.post(BASE + path, json=payload, headers=HEADERS, timeout=30)
    assert r.status_code in (200, 201), f"{path} -> {r.status_code}: {r.text[:200]}"
    return r.json()


def main():
    get("/health")
    data = get("/api/v1/demo")                 # the scaffold fixture endpoint still works
    assert data.get("items"), "demo endpoint returned no items"

    # 1. Ingest 4 weeks of history with one planted stockout day; repair runs inline.
    ing = post("/api/v1/ingest", {"csv_text": _csv(28, START, stockout_day=7)})
    sku_id = ing["skus"][SKU]
    assert ing["records"] == 28 and ing["stockout_days"] == 1
    assert ing["repaired_days"] == 28, ing

    # 2. Forecast the next week from the repaired history.
    fc = post("/api/v1/forecasts", {"sku_id": sku_id, "horizon_days": 7})
    assert len(fc["points"]) == 7
    for p in fc["points"]:
        assert p["p10"] <= p["p50"] <= p["p90"], p

    # 3. Action envelope at 0.9 service level, signals surfaced beside it.
    env = post("/api/v1/envelopes", {"sku_id": sku_id, "service_level": 0.9})
    assert env["lower_qty"] <= env["point_qty"] <= env["upper_qty"], env
    assert "lost margin" in env["regret_lower"] and "cash at risk" in env["regret_upper"]
    assert "signals_note" in env
    stored = get(f"/api/v1/envelopes/{sku_id}")
    assert stored["envelope"]["point_qty"] == env["point_qty"]

    # 4. Actuals arrive for the forecast week; the autopsy scores the miss.
    post("/api/v1/ingest", {"csv_text": _csv(7, START + timedelta(days=28), None)})
    aut = post("/api/v1/autopsy", {"sku_id": sku_id})
    assert aut["days_scored"] == 7, aut
    assert "band_coverage" in aut and "Phase 1 stub" in aut["note"]

    print("SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"SMOKE FAILED: {e}", file=sys.stderr)
        sys.exit(1)

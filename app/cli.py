"""CLI planning loop: keyless, serverless, honest.

Usage:
    python -m app.cli plan --csv data/synthetic/sales_demo.csv --sku SKU-COLA-330
                           [--service-level 0.9] [--horizon 14] [--on-hand 0]
                           [--unit-cost 1.0] [--unit-price 2.5] [--report out.md]

Reads a sales-history CSV, repairs the censored demand, forecasts the horizon, and prints
the action envelope with both regret notes. No server, no database, no API key: the same
deterministic engine the API persists.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine.forecast import forecast_series
from .engine.ingest import IngestError, parse_sales_csv
from .engine.optimizer import CostInputs, build_envelope
from .engine.repair import repair_series


def plan(csv_path: str, sku_key: str, service_level: float, horizon: int, on_hand: float,
         unit_cost: float | None, unit_price: float | None, report_path: str | None) -> int:
    try:
        batches = parse_sales_csv(Path(csv_path).read_text(encoding="utf-8"))
    except (IngestError, OSError) as e:
        print(f"ingest error: {e}", file=sys.stderr)
        return 2
    batch = next((b for b in batches if b.sku_key == sku_key), None)
    if batch is None:
        print(f"unknown sku '{sku_key}'; available: {[b.sku_key for b in batches]}",
              file=sys.stderr)
        return 2
    cost = unit_cost if unit_cost is not None else batch.unit_cost
    price = unit_price if unit_price is not None else batch.unit_price
    if cost is None or price is None:
        print("unit_cost and unit_price are required (flags or CSV columns); "
              "refusing to invent economics", file=sys.stderr)
        return 2

    repaired = repair_series(batch.sales)
    stockout_days = sum(1 for r in repaired if r.was_stockout)
    fc = forecast_series(repaired, horizon)
    env = build_envelope(fc, service_level, on_hand,
                         CostInputs(unit_cost=cost, unit_price=price))

    lines = [
        f"# Action envelope — {sku_key}",
        "",
        f"history: {fc.train_start} .. {fc.train_end} "
        f"({len(repaired)} days, {stockout_days} stockout-flagged and repaired)",
        f"forecast: {fc.method}, {horizon} days "
        f"(P10 {env.demand_p10}, P50 {env.demand_p50}, P90 {env.demand_p90})",
        f"service level: {service_level}   on hand: {on_hand}",
        "",
        "| bound | order qty |",
        "|---|---|",
        f"| lower (cash-protective) | {env.lower_qty} |",
        f"| point (newsvendor @ {service_level}) | {env.point_qty} |",
        f"| upper (stockout-averse) | {env.upper_qty} |",
        "",
        f"- {env.regret_lower}",
        f"- {env.regret_upper}",
        "",
        "The range is the product: pick the risk posture, the arithmetic is shown.",
    ]
    text = "\n".join(lines) + "\n"
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(prog="almanac")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="repair -> forecast -> action envelope from a CSV")
    p.add_argument("--csv", required=True)
    p.add_argument("--sku", required=True)
    p.add_argument("--service-level", type=float, default=0.9)
    p.add_argument("--horizon", type=int, default=14)
    p.add_argument("--on-hand", type=float, default=0.0)
    p.add_argument("--unit-cost", type=float, default=None)
    p.add_argument("--unit-price", type=float, default=None)
    p.add_argument("--report", default=None)
    args = ap.parse_args()
    sys.exit(plan(args.csv, args.sku, args.service_level, args.horizon, args.on_hand,
                  args.unit_cost, args.unit_price, args.report))


if __name__ == "__main__":
    main()

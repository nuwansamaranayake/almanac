"""Eval harness: the Phase 1 core loop against the EVAL.md acceptance thresholds.

Deterministic and keyless: a seeded synthetic store with known weekday seasonality and
planted, censored stockouts runs end to end through the real engine modules (repair ->
forecast -> envelopes). The truth is known because we planted it. Writes eval_report.md so
consecutive runs can be compared byte-for-byte. The key-gated LLM context-sensor section is
reported separately by scripts/eval_llm.py and is never a required check — and never a
silent skip: this harness says loudly whether it ran.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.forecast import forecast_series  # noqa: E402
from app.engine.optimizer import CostInputs, build_envelope  # noqa: E402
from app.engine.repair import repair_series  # noqa: E402
from app.engine.synth import generate_store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "eval_report.md"

TRAIN_WEEKS = 10
HOLDOUT_DAYS = 14
SERVICE_LEVELS = [i / 100 for i in range(50, 100, 5)]
COSTS = CostInputs(unit_cost=1.0, unit_price=2.5)

BOUNDS = {
    "repair_mape": 0.20,
    "forecast_mape": 0.25,
    "envelope_monotonicity": 1.0,
    "envelope_sanity": 1.0,
}


def main() -> None:
    store = generate_store()          # fixed seeds inside; same store every run
    repair_apes: list[float] = []
    forecast_apes: list[float] = []
    mono_checks = mono_ok = 0
    sane_checks = sane_ok = 0
    rows_out: list[str] = []

    for sku in store:
        train = sku.days[: TRAIN_WEEKS * 7]
        holdout = sku.days[TRAIN_WEEKS * 7: TRAIN_WEEKS * 7 + HOLDOUT_DAYS]

        observed = sku.observed_series()[: TRAIN_WEEKS * 7]
        repaired = repair_series(observed)

        truth = {d.day: d.true_demand for d in train}
        sku_repair_apes = [
            abs(r.repaired - truth[r.day]) / truth[r.day]
            for r in repaired if r.was_stockout
        ]
        repair_apes += sku_repair_apes

        fc = forecast_series(repaired, HOLDOUT_DAYS)
        holdout_truth = {d.day: d.true_demand for d in holdout}
        sku_fc_apes = [
            abs(p.p50 - holdout_truth[p.day]) / holdout_truth[p.day]
            for p in fc.points
        ]
        forecast_apes += sku_fc_apes

        envelopes = [build_envelope(fc, sl, on_hand=0.0, costs=COSTS)
                     for sl in SERVICE_LEVELS]
        for env in envelopes:
            sane_checks += 1
            sane_ok += int(env.lower_qty <= env.point_qty <= env.upper_qty)
        for a, b in zip(envelopes, envelopes[1:]):
            mono_checks += 1
            mono_ok += int(b.upper_qty >= a.upper_qty)

        rows_out.append(
            f"{sku.sku_key}: planted stockout days={len(sku_repair_apes)}, "
            f"repair MAPE={sum(sku_repair_apes) / len(sku_repair_apes):.4f}, "
            f"forecast MAPE={sum(sku_fc_apes) / len(sku_fc_apes):.4f}, "
            f"envelope point@0.90={next(e.point_qty for e in envelopes if e.service_level == 0.9):.1f}")

    metrics = {
        "repair_mape": sum(repair_apes) / len(repair_apes),
        "forecast_mape": sum(forecast_apes) / len(forecast_apes),
        "envelope_monotonicity": mono_ok / mono_checks,
        "envelope_sanity": sane_ok / sane_checks,
    }
    passes = {
        "repair_mape": metrics["repair_mape"] <= BOUNDS["repair_mape"],
        "forecast_mape": metrics["forecast_mape"] <= BOUNDS["forecast_mape"],
        "envelope_monotonicity":
            metrics["envelope_monotonicity"] >= BOUNDS["envelope_monotonicity"],
        "envelope_sanity": metrics["envelope_sanity"] >= BOUNDS["envelope_sanity"],
    }

    lines = ["# Almanac Phase 1 eval report", "",
             f"synthetic store: 3 SKUs, {TRAIN_WEEKS} train weeks, "
             f"{HOLDOUT_DAYS} held-out days, planted stockout rate 0.1, fixed seeds", ""]
    lines += rows_out + ["", "| metric | value | bound | pass |", "|---|---|---|---|"]
    for k, v in metrics.items():
        op = "<=" if k.endswith("_mape") else ">="
        lines.append(f"| {k} | {v:.4f} | {op} {BOUNDS[k]} | {'PASS' if passes[k] else 'FAIL'} |")
    if os.environ.get("OPENROUTER_API_KEY"):
        note_lines = ["", "key-gated context-sensor section: run scripts/eval_llm.py "
                      "(not part of this deterministic report)"]
    else:
        note_lines = ["", "key-gated context-sensor section: NOT RUN (no OPENROUTER_API_KEY); "
                      "deterministic bounds above are the required gate"]
    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    # Environment-dependent key-status note goes to stdout only: the report file
    # must stay byte-identical regardless of ambient keys.
    print(text + "\n".join(note_lines))
    if not all(passes.values()):
        print("EVAL FAILED: at least one threshold missed (see rows above)", file=sys.stderr)
        sys.exit(1)
    print("EVAL OK")


if __name__ == "__main__":
    main()

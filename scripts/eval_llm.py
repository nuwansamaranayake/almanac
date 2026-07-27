"""Key-gated LLM eval: the real context-sensor stage, measured — never a required CI
check, never a silent skip.

Two measures, bounds stated here before the first run (mirrored in EVAL.md):
  planted-anchor recall    >= 0.5    planted event classes recovered from the base note as
                                     canonical anchors (signal_type:direction)
  paraphrase jaccard (min) >= 0.6    anchor-set stability across pre-authored note
                                     paraphrases (the contracts/context-sensor-stability.yaml
                                     invariant)

Anchors are schema-enforced enum pairs, never model-invented labels: the model cannot name
its way out of the comparison. Writes eval_report_llm.md. Exits nonzero on a miss (when it
runs at all).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from groundwork import BaseConfig, LLMGateway  # noqa: E402

from app.engine.signals import anchors, extract_signals  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "eval_report_llm.md"

# The probe note from contracts/context-sensor-stability.yaml, with two planted events.
NOTE = ("The city street festival runs Friday 2026-08-14 through Sunday 2026-08-16 two "
        "blocks from the store; expect big crowds all three days. Also the heat wave is "
        "forecast to hold through the whole week.")
PARAPHRASES = [
    ("Big crowds expected Friday 2026-08-14 to Sunday 2026-08-16: the city street "
     "festival is two blocks away. The forecast says the heat wave continues all week."),
    ("Heads up: heat wave sticking around through the week, and from 2026-08-14 through "
     "2026-08-16 the street festival takes over the block two streets over, expect it "
     "to be packed."),
]
# Planted event classes as canonical anchors. Both events raise demand for a corner store.
PLANTED = {"festival:increase", "weather:increase"}

RECALL_BOUND = 0.5
JACCARD_BOUND = 0.6


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return (len(a & b) / len(union)) if union else 1.0


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL_EXTRACTION", "")
    if not key or not model:
        print("eval_llm: NOT RUN — OPENROUTER_API_KEY / LLM_MODEL_EXTRACTION missing. "
              "This section is key-gated by design; the deterministic suite in "
              "scripts/eval.py is the required gate.", file=sys.stderr)
        sys.exit(2)

    gw = LLMGateway(BaseConfig(openrouter_api_key=key))
    base = extract_signals(gw, model, NOTE, "eval-note")
    base_anchors = anchors(base)
    recall = len(PLANTED & base_anchors) / len(PLANTED)

    jaccards = []
    for i, txt in enumerate(PARAPHRASES):
        v_anchors = anchors(extract_signals(gw, model, txt, f"eval-paraphrase-{i}"))
        jaccards.append(_jaccard(base_anchors, v_anchors))
    j_min = min(jaccards)

    rows = [
        "# Almanac key-gated context-sensor eval",
        "",
        f"model: {model}",
        f"base anchors ({len(base_anchors)}): {sorted(base_anchors)}",
        f"planted: {sorted(PLANTED)}",
        f"per-paraphrase jaccard: {[round(j, 2) for j in jaccards]}",
        "",
        "| metric | value | bound | pass |",
        "|---|---|---|---|",
        f"| planted-anchor recall | {recall:.2f} | >= {RECALL_BOUND} | "
        f"{'PASS' if recall >= RECALL_BOUND else 'FAIL'} |",
        f"| paraphrase jaccard (min) | {j_min:.2f} | >= {JACCARD_BOUND} | "
        f"{'PASS' if j_min >= JACCARD_BOUND else 'FAIL'} |",
        "",
        f"contract: contracts/context-sensor-stability.yaml (threshold {JACCARD_BOUND})",
    ]
    text = "\n".join(rows) + "\n"
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    if recall < RECALL_BOUND or j_min < JACCARD_BOUND:
        print("EVAL_LLM FAILED", file=sys.stderr)
        sys.exit(1)
    print("EVAL_LLM OK")


if __name__ == "__main__":
    main()

"""The Signal Scout, Phase 1 cut: LLM as a context sensor, never an arithmetic engine.

A free-text event note ("street festival next weekend, expect crowds") becomes typed
demand-signal claims on the groundwork spine. Three hard rules:

* The gateway call is schema-forced: `signal_type`, `direction`, and `magnitude` are
  closed enums. The enum pair `signal_type:direction` IS the canonical anchor used for
  stability comparison — model-invented labels are not stable identity (the
  CareerCompiler FAIL-0003 lesson, and the invariant in
  contracts/context-sensor-stability.yaml).
* Every signal carries deterministic gates: `span_anchor` (the quote must appear
  verbatim in the note) and `date_window` (ISO dates, start <= end). A failed gate marks
  the claim rejected — kept and visible, never silently dropped.
* Signals NEVER change forecast or envelope numbers in Phase 1. They are stored and
  surfaced beside the envelope; influence is earned in the Phase 2 backtest arena.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from enum import Enum
from typing import Protocol

from groundwork import Claim, ClaimType, EvidenceRef, Extractor, Verification
from pydantic import BaseModel


class SignalType(str, Enum):
    festival = "festival"
    weather = "weather"
    school_calendar = "school_calendar"
    supplier = "supplier"
    promotion = "promotion"
    closure = "closure"
    viral_trend = "viral_trend"
    other = "other"


class Direction(str, Enum):
    increase = "increase"
    decrease = "decrease"


class Magnitude(str, Enum):
    small = "small"
    moderate = "moderate"
    large = "large"


class DemandSignal(BaseModel):
    """One typed context signal. `core` is the portfolio-wide claim atom; the app adds
    the closed-enum typing that makes the signal comparable and storable."""
    core: Claim
    signal_type: SignalType
    direction: Direction
    magnitude: Magnitude
    window_start: date | None = None
    window_end: date | None = None

    @property
    def anchor(self) -> str:
        """Canonical identity: schema-enforced enums, never a model-invented label."""
        return f"{self.signal_type.value}:{self.direction.value}"


SIGNAL_SCHEMA = {
    "name": "demand_signals",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal_type": {"type": "string",
                                        "enum": [t.value for t in SignalType]},
                        "direction": {"type": "string",
                                      "enum": [d.value for d in Direction]},
                        "magnitude": {"type": "string",
                                      "enum": [m.value for m in Magnitude]},
                        "window_start": {"type": "string",
                                         "description": "YYYY-MM-DD or empty when unknown"},
                        "window_end": {"type": "string",
                                       "description": "YYYY-MM-DD or empty when unknown"},
                        "statement": {"type": "string"},
                        "quote": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["signal_type", "direction", "magnitude", "window_start",
                                 "window_end", "statement", "quote", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["signals"],
        "additionalProperties": False,
    },
}


class CompletesJson(Protocol):
    def complete(self, *, model: str, messages: list[dict],
                 json_schema: dict | None = None, temperature: float = 0.0): ...


# Phase 1 runs single-store: the sensor must know what the store sells or demand
# DIRECTION is ill-posed (observed live: "heat wave" flip-flopped increase/decrease with
# no store context — see FAILURES.md FAIL-0001). Configurable per store in Phase 2.
DEFAULT_STORE_CONTEXT = ("a neighborhood convenience store selling beverages, snacks, "
                         "bread, dairy, and ice cream")


def _claim_id(source: str, anchor: str, statement: str) -> str:
    return hashlib.sha256(f"{source}|{anchor}|{statement}".encode()).hexdigest()[:16]


def _parse_window(raw_start: str, raw_end: str) -> tuple[date | None, date | None, bool]:
    """Deterministic date gate. Returns (start, end, ok). Empty strings claim no dates."""
    start = end = None
    try:
        if raw_start.strip():
            start = date.fromisoformat(raw_start.strip())
        if raw_end.strip():
            end = date.fromisoformat(raw_end.strip())
    except ValueError:
        return None, None, False
    if start is not None and end is not None and start > end:
        return None, None, False
    return start, end, True


def extract_signals(
    gateway: CompletesJson,
    model: str,
    note_text: str,
    source_name: str,
    store_context: str = DEFAULT_STORE_CONTEXT,
) -> list[DemandSignal]:
    """LLM senses the note; deterministic gates dispose.

    Every returned signal carries verification: "pending" when its quote anchors verbatim
    in the note AND its window passes the date gate; "rejected" otherwise. Nothing is
    silently dropped, and nothing here touches a forecast number.
    """
    if not model:
        raise RuntimeError("LLM_MODEL_EXTRACTION is not set. Refusing to guess a model.")
    result = gateway.complete(
        model=model,
        messages=[
            {"role": "system",
             "content": (f"The store is {store_context}. Extract demand-relevant context "
                         "signals from the store owner's note. One signal per distinct "
                         "real-world event. Use ONLY the closed vocabularies for "
                         "signal_type, direction (the expected effect on THIS store's "
                         "demand), and magnitude. window_start/window_end are "
                         "YYYY-MM-DD dates when the note states or clearly implies them, "
                         "else empty strings. quote is a VERBATIM substring of the note "
                         "that evidences the signal. statement is one factual sentence. "
                         "Never infer events the note does not mention. Return JSON.")},
            {"role": "user", "content": note_text},
        ],
        json_schema=SIGNAL_SCHEMA,
    )
    # Provider quirk seen on other apps: the array sometimes arrives at the top level
    # despite the strict object schema. Normalize the envelope only.
    if isinstance(result, list):
        result = {"signals": result}
    now = datetime.now(timezone.utc)
    out: list[DemandSignal] = []
    for item in result.get("signals", []):
        quote = item["quote"]
        idx = note_text.find(quote)
        anchored = idx >= 0 and bool(quote.strip())
        start, end, window_ok = _parse_window(item["window_start"], item["window_end"])
        passed = anchored and window_ok
        anchor = f"{item['signal_type']}:{item['direction']}"
        core = Claim(
            claim_id=_claim_id(source_name, anchor, item["statement"]),
            type=ClaimType.event_signal,
            statement=item["statement"],
            evidence_ref=EvidenceRef(
                source=source_name,
                span=(idx, idx + len(quote)) if anchored else None,
            ),
            observed_at=start,
            recorded_at=now,
            extracted_by=Extractor(model=model, version="phase-1", temp=0.0),
            confidence=max(0.0, min(1.0, float(item["confidence"]))),
            verification=Verification(
                status="pending" if passed else "rejected",
                gates=["span_anchor", "date_window"],
                score=1.0 if passed else 0.0,
            ),
        )
        out.append(DemandSignal(
            core=core,
            signal_type=SignalType(item["signal_type"]),
            direction=Direction(item["direction"]),
            magnitude=Magnitude(item["magnitude"]),
            window_start=start,
            window_end=end,
        ))
    return out


def anchors(signals: list[DemandSignal]) -> set[str]:
    """Canonical anchor set of the non-rejected signals (the contract's invariant field)."""
    return {s.anchor for s in signals if s.core.verification.status != "rejected"}

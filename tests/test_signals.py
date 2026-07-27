"""Signal Scout unit tests: injected typed stub gateway, no network anywhere."""
import pytest

from app.engine.signals import Direction, SignalType, anchors, extract_signals

NOTE = ("The city street festival runs Friday 2026-08-14 through Sunday 2026-08-16 two "
        "blocks away; expect big crowds. The heat wave is forecast to hold all week.")


class StubGateway:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete(self, *, model, messages, json_schema=None, temperature=0.0):
        self.calls.append({"model": model, "schema": json_schema})
        return self.payload


def _item(**over):
    base = {"signal_type": "festival", "direction": "increase", "magnitude": "large",
            "window_start": "2026-08-14", "window_end": "2026-08-16",
            "statement": "A street festival runs nearby that weekend.",
            "quote": "street festival", "confidence": 0.9}
    base.update(over)
    return base


def test_extracts_typed_signals_with_span_and_window():
    gw = StubGateway({"signals": [_item()]})
    [sig] = extract_signals(gw, "test-model", NOTE, "owner-note")
    assert sig.signal_type is SignalType.festival
    assert sig.direction is Direction.increase
    assert sig.anchor == "festival:increase"
    assert sig.core.verification.status == "pending"
    assert sig.core.evidence_ref.span == (NOTE.find("street festival"),
                                          NOTE.find("street festival") + len("street festival"))
    assert sig.window_start.isoformat() == "2026-08-14"
    assert gw.calls[0]["schema"]["name"] == "demand_signals"


def test_unanchored_quote_is_rejected_not_dropped():
    gw = StubGateway({"signals": [_item(quote="INVENTED TEXT")]})
    [sig] = extract_signals(gw, "m", NOTE, "owner-note")
    assert sig.core.verification.status == "rejected"
    assert sig.core.evidence_ref.span is None
    assert anchors([sig]) == set()                    # rejected signals earn no anchor


def test_bad_date_window_is_rejected():
    gw = StubGateway({"signals": [_item(window_start="not-a-date")]})
    [sig] = extract_signals(gw, "m", NOTE, "owner-note")
    assert sig.core.verification.status == "rejected"
    gw = StubGateway({"signals": [_item(window_start="2026-08-16", window_end="2026-08-14")]})
    [sig] = extract_signals(gw, "m", NOTE, "owner-note")
    assert sig.core.verification.status == "rejected"


def test_empty_window_claims_no_dates_and_passes():
    gw = StubGateway({"signals": [_item(window_start="", window_end="")]})
    [sig] = extract_signals(gw, "m", NOTE, "owner-note")
    assert sig.core.verification.status == "pending"
    assert sig.window_start is None and sig.window_end is None


def test_top_level_array_envelope_normalized():
    gw = StubGateway([_item()])
    assert len(extract_signals(gw, "m", NOTE, "owner-note")) == 1


def test_anchor_set_is_canonical_not_model_named():
    gw = StubGateway({"signals": [
        _item(),
        _item(signal_type="weather", quote="heat wave",
              statement="A heat wave holds all week."),
    ]})
    sigs = extract_signals(gw, "m", NOTE, "owner-note")
    assert anchors(sigs) == {"festival:increase", "weather:increase"}


def test_refuses_blank_model():
    with pytest.raises(RuntimeError, match="LLM_MODEL_EXTRACTION"):
        extract_signals(StubGateway({"signals": []}), "", NOTE, "owner-note")

from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import db
from app.main import app

START = date(2026, 6, 1)                       # a Monday
LEVELS = [12, 14, 16, 16, 18, 30, 24]


def _csv(days: int, first_day: date = START, stockout_day: int | None = 7) -> str:
    rows = ["sku,date,units_sold,stockout,unit_cost,unit_price"]
    for i in range(days):
        d = first_day + timedelta(days=i)
        if i == stockout_day:
            rows.append(f"T-SKU,{d.isoformat()},2,1,,")
        else:
            cost = "1.0,2.5" if i == 0 else ","
            rows.append(f"T-SKU,{d.isoformat()},{LEVELS[d.weekday()]},0,{cost}")
    return "\n".join(rows) + "\n"


@pytest.fixture()
def client():
    engine = sa.create_engine(
        "sqlite://",
        poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False},   # TestClient serves on another thread
    )
    db.metadata.create_all(engine)
    db.set_engine_for_tests(engine)
    return TestClient(app)


def _seed(client) -> int:
    body = client.post("/api/v1/ingest", json={"csv_text": _csv(28)}).json()
    return body["skus"]["T-SKU"]


def test_full_loop_ingest_forecast_envelope_autopsy(client):
    r = client.post("/api/v1/ingest", json={"csv_text": _csv(28)})
    assert r.status_code == 201, r.text
    body = r.json()
    sku_id = body["skus"]["T-SKU"]
    assert body["records"] == 28
    assert body["stockout_days"] == 1
    assert body["repaired_days"] == 28

    r = client.post("/api/v1/forecasts", json={"sku_id": sku_id, "horizon_days": 7})
    assert r.status_code == 201, r.text
    fc = r.json()
    assert len(fc["points"]) == 7
    assert all(p["p10"] <= p["p50"] <= p["p90"] for p in fc["points"])
    got = client.get(f"/api/v1/forecasts/{sku_id}").json()
    assert got["forecast_id"] == fc["forecast_id"]

    r = client.post("/api/v1/envelopes", json={"sku_id": sku_id, "service_level": 0.9})
    assert r.status_code == 201, r.text
    env = r.json()
    assert env["lower_qty"] <= env["point_qty"] <= env["upper_qty"]
    assert "never change quantities in Phase 1" in env["signals_note"]
    stored = client.get(f"/api/v1/envelopes/{sku_id}").json()
    assert stored["envelope"]["point_qty"] == env["point_qty"]

    # actuals arrive for the forecast week -> autopsy scores it
    client.post("/api/v1/ingest",
                json={"csv_text": _csv(7, START + timedelta(days=28), None)})
    r = client.post("/api/v1/autopsy", json={"sku_id": sku_id})
    assert r.status_code == 200, r.text
    assert r.json()["days_scored"] == 7


def test_autopsy_rejects_foreign_or_missing_forecast_id(client):
    sku_id = _seed(client)
    client.post("/api/v1/forecasts", json={"sku_id": sku_id, "horizon_days": 7})
    other_csv = _csv(28).replace("T-SKU", "OTHER-SKU")
    other_id = client.post("/api/v1/ingest",
                           json={"csv_text": other_csv}).json()["skus"]["OTHER-SKU"]
    other_fid = client.post("/api/v1/forecasts",
                            json={"sku_id": other_id,
                                  "horizon_days": 7}).json()["forecast_id"]
    # another SKU's forecast must never be scored against this SKU's actuals
    r = client.post("/api/v1/autopsy", json={"sku_id": sku_id, "forecast_id": other_fid})
    assert r.status_code == 422
    assert "different sku_id" in r.json()["detail"]
    # a nonexistent forecast_id is a typed 404, not a TypeError 500
    r = client.post("/api/v1/autopsy", json={"sku_id": sku_id, "forecast_id": 999999})
    assert r.status_code == 404
    assert r.json()["detail"] == "forecast not found"


def test_signals_llm_call_runs_outside_db_session(client, monkeypatch):
    """The network LLM call must never run inside an open DB session/transaction."""
    from contextlib import contextmanager

    from app import routes
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(routes, "_gateway", lambda: object())
    real_get_session = db.get_session
    state = {"open": 0, "during_llm": None}

    @contextmanager
    def counting_get_session():
        with real_get_session() as s:
            state["open"] += 1
            try:
                yield s
            finally:
                state["open"] -= 1

    monkeypatch.setattr(db, "get_session", counting_get_session)

    def stub_extract(gateway, model, note, source):
        state["during_llm"] = state["open"]
        return []

    monkeypatch.setattr(routes, "extract_signals", stub_extract)
    r = client.post("/api/v1/signals", json={"note": "street festival next weekend"})
    assert r.status_code == 201, r.text
    assert state["during_llm"] == 0       # no pooled connection pinned during the call


def test_repair_persists_the_documented_rule(client):
    sku_id = _seed(client)
    with db.get_session() as s:
        rows = s.execute(sa.select(db.repaired_demand)
                         .where(db.repaired_demand.c.sku_id == sku_id)).mappings().all()
    flagged = [r for r in rows if r["was_stockout"]]
    assert len(flagged) == 1
    # day 7 is a Monday; clean Mondays sell 12 -> median 12; max(2, 12) = 12
    assert flagged[0]["repaired_units"] == 12.0
    assert flagged[0]["observed_units"] == 2.0
    assert flagged[0]["rule"] == "same_weekday_median"


def test_reingest_same_dates_is_idempotent(client):
    sku_id = _seed(client)
    body = client.post("/api/v1/ingest", json={"csv_text": _csv(28)}).json()
    assert body["skus"]["T-SKU"] == sku_id            # same SKU, replaced not duplicated
    with db.get_session() as s:
        n = s.execute(sa.select(sa.func.count()).select_from(db.sales_records)
                      .where(db.sales_records.c.sku_id == sku_id)).scalar_one()
    assert n == 28


def test_malformed_csv_rejected_with_row_number(client):
    r = client.post("/api/v1/ingest",
                    json={"csv_text": "sku,date,units_sold,stockout\nA,not-a-date,5,0\n"})
    assert r.status_code == 422
    assert "row 2" in r.json()["detail"]


def test_forecast_requires_history_and_sku(client):
    assert client.post("/api/v1/forecasts", json={"sku_id": 999}).status_code == 404
    r = client.post("/api/v1/ingest", json={"csv_text": _csv(28)})
    sku_id = r.json()["skus"]["T-SKU"]
    with db.get_session() as s, s.begin():
        s.execute(db.repaired_demand.delete())
    assert client.post("/api/v1/forecasts",
                       json={"sku_id": sku_id}).status_code == 422


def test_envelope_requires_forecast_and_costs(client):
    sku_id = _seed(client)
    r = client.post("/api/v1/envelopes", json={"sku_id": sku_id})
    assert r.status_code == 422                       # no forecast yet
    client.post("/api/v1/forecasts", json={"sku_id": sku_id, "horizon_days": 7})
    with db.get_session() as s, s.begin():            # drop stored economics
        s.execute(db.skus.update().values(unit_cost=None, unit_price=None))
    r = client.post("/api/v1/envelopes", json={"sku_id": sku_id})
    assert r.status_code == 422
    assert "unit_cost" in r.json()["detail"]
    r = client.post("/api/v1/envelopes",
                    json={"sku_id": sku_id, "unit_cost": 1.0, "unit_price": 2.5})
    assert r.status_code == 201                       # explicit economics work


def test_signals_without_key_fails_loud(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    r = client.post("/api/v1/signals", json={"note": "street festival next weekend"})
    assert r.status_code == 503
    assert "OPENROUTER_API_KEY" in r.json()["detail"]
    assert client.get("/api/v1/signals").json()["signals"] == []   # keyless read works


def test_bearer_auth_enforced_when_token_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "smoke_test_token", "sekrit")
    assert client.post("/api/v1/ingest", json={"csv_text": _csv(7)}).status_code == 401
    assert client.post("/api/v1/ingest", json={"csv_text": _csv(7)},
                       headers={"Authorization": "Bearer sekrit"}).status_code == 201


def test_business_reads_require_bearer_when_token_set(client, monkeypatch):
    """GET a stored forecast must not be world-readable in production.

    Found by the production business-loop audit: this endpoint served real business
    data to an unauthenticated caller over the public internet. Reads are now gated by
    the same bearer check as writes; auth stays off only while the token is empty
    (development semantics).
    """
    from app.config import settings
    monkeypatch.setattr(settings, "smoke_test_token", "sekrit")
    assert client.get("/api/v1/forecasts/1").status_code == 401
    assert client.get(
        "/api/v1/forecasts/1", headers={"Authorization": "Bearer sekrit"}).status_code != 401


def test_root_serves_a_real_html_page(client):
    """The front door must answer a browser. Every gate passed for hours while this 404ed."""
    r = client.get("/", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    assert len(body) > 500
    assert "Almanac" in body
    for placeholder in ("TODO", "Lorem", "example.com", "XXX"):
        assert placeholder not in body


def test_root_publishes_the_eval_limits_sentence_verbatim():
    """The page quotes EVAL.md, so the two cannot drift apart silently."""
    import re
    from pathlib import Path
    from app.frontpage import render

    eval_md = (Path(__file__).resolve().parent.parent / "EVAL.md").read_text(encoding="utf-8")
    limits = " ".join(re.search(r"<!-- LIMITS -->\s*(.+?)\s*<!-- /LIMITS -->",
                                eval_md, re.S).group(1).split())
    assert limits in " ".join(render().split())


def test_root_reports_unknown_rather_than_a_fake_build_stamp(monkeypatch):
    """No build args means "unknown" on the page, never a plausible-looking placeholder."""
    from app import frontpage
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    frontpage._template.cache_clear()
    body = frontpage.render()
    assert "unknown" in body and "__SHA__" not in body and "__VERSION__" not in body

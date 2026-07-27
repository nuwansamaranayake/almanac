"""Business endpoints: the ingest -> repair -> forecast -> envelope loop, persisted.

POST /api/v1/ingest                 CSV sales history (keyless); runs demand repair
POST /api/v1/forecasts              compute + persist a quantile forecast for a SKU
GET  /api/v1/forecasts/{sku_id}     latest stored forecast with points
POST /api/v1/envelopes              compute + persist an action envelope for a SKU
GET  /api/v1/envelopes/{sku_id}     latest stored envelope, signals surfaced beside it
POST /api/v1/autopsy                deterministic forecast-vs-actual miss report
POST /api/v1/signals                LLM context sensor: note -> typed signals (key-gated)
GET  /api/v1/signals                stored signals (keyless read)

The keyless CSV path is a real product feature (retailers have spreadsheets, not APIs).
The LLM path refuses loudly without a key — no silent fallback between the two
(Standard 3). Signals are stored and surfaced, never applied to quantities in Phase 1:
influence is earned in the Phase 2 backtest arena. Bearer auth on mutations when
SMOKE_TEST_TOKEN is set.
"""
from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from fastapi import APIRouter, Header, HTTPException
from groundwork import BaseConfig, LLMGateway
from pydantic import BaseModel, Field

from . import db
from .config import settings
from .engine.autopsy import run_autopsy
from .engine.forecast import Forecast, ForecastPoint, forecast_series
from .engine.ingest import IngestError, parse_sales_csv
from .engine.optimizer import CostInputs, build_envelope
from .engine.repair import DailySale, repair_series
from .engine.signals import extract_signals

router = APIRouter(prefix="/api/v1")

SIGNALS_PHASE_NOTE = ("signals are stored context and never change quantities in Phase 1; "
                      "influence is earned in the Phase 2 backtest arena")


def _auth(authorization: str | None) -> None:
    token = settings.smoke_test_token
    if token and authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


def _gateway() -> LLMGateway:
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM signal extraction requires OPENROUTER_API_KEY; the deterministic "
                   "loop (ingest/forecasts/envelopes/autopsy) is fully keyless",
        )
    return LLMGateway(BaseConfig(
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
    ))


class IngestIn(BaseModel):
    csv_text: str = Field(min_length=1)


class ForecastIn(BaseModel):
    sku_id: int
    horizon_days: int = Field(default=14, ge=1, le=56)


class EnvelopeIn(BaseModel):
    sku_id: int
    service_level: float = Field(default=0.9, gt=0.0, lt=1.0)
    on_hand: float = Field(default=0.0, ge=0.0)
    unit_cost: float | None = Field(default=None, gt=0)
    unit_price: float | None = Field(default=None, gt=0)


class AutopsyIn(BaseModel):
    sku_id: int
    forecast_id: int | None = None


class SignalIn(BaseModel):
    note: str = Field(min_length=1)
    source: str = Field(default="owner-note", min_length=1)
    sku_id: int | None = None


def _recompute_repair(s, sku_id: int) -> int:
    """Rebuild the repaired series for a SKU from its full stored history."""
    sales = s.execute(sa.select(db.sales_records)
                      .where(db.sales_records.c.sku_id == sku_id)).mappings().all()
    flagged = {r["flag_date"] for r in s.execute(
        sa.select(db.stockout_flags.c.flag_date)
        .where(db.stockout_flags.c.sku_id == sku_id)).mappings().all()}
    series = [DailySale(day=r["sale_date"], units=r["units_sold"],
                        stockout=r["sale_date"] in flagged) for r in sales]
    repaired = repair_series(series)
    s.execute(db.repaired_demand.delete().where(db.repaired_demand.c.sku_id == sku_id))
    for r in repaired:
        s.execute(db.repaired_demand.insert().values(
            sku_id=sku_id, demand_date=r.day, observed_units=r.observed,
            repaired_units=r.repaired, was_stockout=r.was_stockout, rule=r.rule))
    return len(repaired)


@router.post("/ingest", status_code=201)
def ingest(body: IngestIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    try:
        batches = parse_sales_csv(body.csv_text)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e))
    sku_ids: dict[str, int] = {}
    records = stockouts = repaired_days = 0
    with db.get_session() as s, s.begin():
        for batch in batches:
            row = s.execute(sa.select(db.skus.c.id)
                            .where(db.skus.c.sku_key == batch.sku_key)).first()
            attrs = {k: v for k, v in (("name", batch.name), ("unit_cost", batch.unit_cost),
                                       ("unit_price", batch.unit_price)) if v is not None}
            if row is None:
                sku_id = s.execute(db.skus.insert().values(
                    sku_key=batch.sku_key, **attrs)).inserted_primary_key[0]
            else:
                sku_id = row.id
                if attrs:
                    s.execute(db.skus.update().where(db.skus.c.id == sku_id).values(**attrs))
            sku_ids[batch.sku_key] = sku_id

            days = [sale.day for sale in batch.sales]
            s.execute(db.sales_records.delete().where(
                (db.sales_records.c.sku_id == sku_id)
                & db.sales_records.c.sale_date.in_(days)))
            s.execute(db.stockout_flags.delete().where(
                (db.stockout_flags.c.sku_id == sku_id)
                & db.stockout_flags.c.flag_date.in_(days)))
            for sale in batch.sales:
                s.execute(db.sales_records.insert().values(
                    sku_id=sku_id, sale_date=sale.day, units_sold=sale.units))
                records += 1
                if sale.stockout:
                    s.execute(db.stockout_flags.insert().values(
                        sku_id=sku_id, flag_date=sale.day, source="csv"))
                    stockouts += 1
            repaired_days += _recompute_repair(s, sku_id)
    return {"skus": sku_ids, "records": records, "stockout_days": stockouts,
            "repaired_days": repaired_days,
            "repair_rule": "same_weekday_median (see app/engine/repair.py)"}


def _load_forecast(s, forecast_id: int) -> Forecast:
    f = s.execute(sa.select(db.forecasts)
                  .where(db.forecasts.c.id == forecast_id)).mappings().first()
    points = s.execute(sa.select(db.forecast_points)
                       .where(db.forecast_points.c.forecast_id == forecast_id)
                       .order_by(db.forecast_points.c.target_date)).mappings().all()
    return Forecast(
        method=f["method"], train_start=f["train_start"], train_end=f["train_end"],
        horizon_days=f["horizon_days"],
        points=[ForecastPoint(day=p["target_date"], p10=p["p10"], p50=p["p50"],
                              p90=p["p90"]) for p in points])


def _latest_forecast_id(s, sku_id: int) -> int | None:
    row = s.execute(sa.select(db.forecasts.c.id)
                    .where(db.forecasts.c.sku_id == sku_id)
                    .order_by(db.forecasts.c.id.desc())).first()
    return row.id if row else None


def _require_sku(s, sku_id: int):
    sku = s.execute(sa.select(db.skus).where(db.skus.c.id == sku_id)).mappings().first()
    if sku is None:
        raise HTTPException(status_code=404, detail="sku not found")
    return sku


@router.post("/forecasts", status_code=201)
def create_forecast(body: ForecastIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    with db.get_session() as s, s.begin():
        _require_sku(s, body.sku_id)
        rows = s.execute(sa.select(db.repaired_demand)
                         .where(db.repaired_demand.c.sku_id == body.sku_id)).mappings().all()
        if not rows:
            raise HTTPException(status_code=422,
                                detail="sku has no repaired history; POST /api/v1/ingest first")
        from .engine.repair import RepairedDay
        history = [RepairedDay(day=r["demand_date"], observed=r["observed_units"],
                               repaired=r["repaired_units"], was_stockout=r["was_stockout"],
                               rule=r["rule"]) for r in rows]
        try:
            fc = forecast_series(history, body.horizon_days)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        fid = s.execute(db.forecasts.insert().values(
            sku_id=body.sku_id, method=fc.method, horizon_days=fc.horizon_days,
            train_start=fc.train_start, train_end=fc.train_end)).inserted_primary_key[0]
        for p in fc.points:
            s.execute(db.forecast_points.insert().values(
                forecast_id=fid, target_date=p.day, p10=p.p10, p50=p.p50, p90=p.p90))
    return {"forecast_id": fid, "method": fc.method, "train_start": fc.train_start.isoformat(),
            "train_end": fc.train_end.isoformat(), "horizon_days": fc.horizon_days,
            "points": [p.model_dump(mode="json") for p in fc.points]}


@router.get("/forecasts/{sku_id}")
def get_forecast(sku_id: int):
    with db.get_session() as s:
        _require_sku(s, sku_id)
        fid = _latest_forecast_id(s, sku_id)
        if fid is None:
            raise HTTPException(status_code=404, detail="sku has no forecast yet")
        fc = _load_forecast(s, fid)
    return {"forecast_id": fid, "sku_id": sku_id, "method": fc.method,
            "train_start": fc.train_start.isoformat(), "train_end": fc.train_end.isoformat(),
            "horizon_days": fc.horizon_days,
            "points": [p.model_dump(mode="json") for p in fc.points]}


def _signals_beside(s, sku_id: int) -> list[dict]:
    rows = s.execute(sa.select(db.demand_signals)
                     .where((db.demand_signals.c.sku_id == sku_id)
                            | (db.demand_signals.c.sku_id.is_(None)))
                     .order_by(db.demand_signals.c.id)).mappings().all()
    return [dict(r) for r in rows]


@router.post("/envelopes", status_code=201)
def create_envelope(body: EnvelopeIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    with db.get_session() as s, s.begin():
        sku = _require_sku(s, body.sku_id)
        fid = _latest_forecast_id(s, body.sku_id)
        if fid is None:
            raise HTTPException(status_code=422,
                                detail="sku has no forecast; POST /api/v1/forecasts first")
        unit_cost = body.unit_cost if body.unit_cost is not None else sku["unit_cost"]
        unit_price = body.unit_price if body.unit_price is not None else sku["unit_price"]
        if unit_cost is None or unit_price is None:
            raise HTTPException(
                status_code=422,
                detail="unit_cost and unit_price are required: supply them in the request "
                       "or in the ingest CSV (no invented defaults)")
        fc = _load_forecast(s, fid)
        try:
            env = build_envelope(fc, body.service_level, body.on_hand,
                                 CostInputs(unit_cost=unit_cost, unit_price=unit_price))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        eid = s.execute(db.action_envelopes.insert().values(
            sku_id=body.sku_id, forecast_id=fid, service_level=env.service_level,
            horizon_days=env.horizon_days, on_hand=env.on_hand, unit_cost=unit_cost,
            unit_price=unit_price, demand_p10=env.demand_p10, demand_p50=env.demand_p50,
            demand_p90=env.demand_p90, lower_qty=env.lower_qty, point_qty=env.point_qty,
            upper_qty=env.upper_qty, regret_lower=env.regret_lower,
            regret_upper=env.regret_upper)).inserted_primary_key[0]
        signals = _signals_beside(s, body.sku_id)
    return {"envelope_id": eid, "forecast_id": fid, **env.model_dump(),
            "signals": signals, "signals_note": SIGNALS_PHASE_NOTE}


@router.get("/envelopes/{sku_id}")
def get_envelope(sku_id: int):
    with db.get_session() as s:
        _require_sku(s, sku_id)
        row = s.execute(sa.select(db.action_envelopes)
                        .where(db.action_envelopes.c.sku_id == sku_id)
                        .order_by(db.action_envelopes.c.id.desc())).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="sku has no envelope yet")
        signals = _signals_beside(s, sku_id)
    return {"envelope": dict(row), "signals": signals, "signals_note": SIGNALS_PHASE_NOTE}


@router.post("/autopsy")
def autopsy(body: AutopsyIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    with db.get_session() as s:
        _require_sku(s, body.sku_id)
        fid = body.forecast_id or _latest_forecast_id(s, body.sku_id)
        if fid is None:
            raise HTTPException(status_code=404, detail="sku has no forecast to autopsy")
        fc = _load_forecast(s, fid)
        actual_rows = s.execute(sa.select(db.sales_records)
                                .where((db.sales_records.c.sku_id == body.sku_id)
                                       & db.sales_records.c.sale_date.in_(
                                           [p.day for p in fc.points]))).mappings().all()
        actuals: dict[date, float] = {r["sale_date"]: r["units_sold"] for r in actual_rows}
        try:
            report = run_autopsy(fc, actuals)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    return {"forecast_id": fid, **report.model_dump(mode="json")}


@router.post("/signals", status_code=201)
def create_signals(body: SignalIn, authorization: str | None = Header(default=None)):
    _auth(authorization)
    gateway = _gateway()
    with db.get_session() as s, s.begin():
        if body.sku_id is not None:
            _require_sku(s, body.sku_id)
        signals = extract_signals(gateway, settings.llm_model_extraction, body.note,
                                  body.source)
        stored = []
        for sig in signals:
            span = sig.core.evidence_ref.span
            sid = s.execute(db.demand_signals.insert().values(
                sku_id=body.sku_id, claim_id=sig.core.claim_id,
                signal_type=sig.signal_type.value, direction=sig.direction.value,
                magnitude=sig.magnitude.value, window_start=sig.window_start,
                window_end=sig.window_end, statement=sig.core.statement,
                source=sig.core.evidence_ref.source,
                span_start=span[0] if span else None, span_end=span[1] if span else None,
                model=sig.core.extracted_by.model, confidence=sig.core.confidence or 0.0,
                verification_status=sig.core.verification.status,
                gates=sig.core.verification.gates)).inserted_primary_key[0]
            stored.append({"signal_id": sid, "anchor": sig.anchor,
                           "verification_status": sig.core.verification.status})
        rejected = sum(1 for x in stored if x["verification_status"] == "rejected")
    return {"stored": len(stored), "rejected": rejected, "signals": stored,
            "signals_note": SIGNALS_PHASE_NOTE}


@router.get("/signals")
def list_signals(sku_id: int | None = None):
    with db.get_session() as s:
        q = sa.select(db.demand_signals).order_by(db.demand_signals.c.id)
        if sku_id is not None:
            q = q.where(db.demand_signals.c.sku_id == sku_id)
        rows = s.execute(q).mappings().all()
    return {"signals": [dict(r) for r in rows], "signals_note": SIGNALS_PHASE_NOTE}

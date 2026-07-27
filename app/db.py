"""Schema and session plumbing. metadata is the single source of truth; the alembic
migration applies it, and EXPECTED_TABLE_COUNT asserts the result (Standard 4)."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from .config import settings

JSON = sa.JSON().with_variant(JSONB(), "postgresql")

metadata = sa.MetaData()

skus = sa.Table(
    "skus", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_key", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text),
    sa.Column("unit_cost", sa.Float),
    sa.Column("unit_price", sa.Float),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

sales_records = sa.Table(
    "sales_records", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id"), nullable=False),
    sa.Column("sale_date", sa.Date, nullable=False),
    sa.Column("units_sold", sa.Float, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.UniqueConstraint("sku_id", "sale_date", name="uq_sales_sku_date"),
)

stockout_flags = sa.Table(
    "stockout_flags", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id"), nullable=False),
    sa.Column("flag_date", sa.Date, nullable=False),
    sa.Column("source", sa.Text, nullable=False),            # csv (Phase 1)
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.UniqueConstraint("sku_id", "flag_date", name="uq_stockout_sku_date"),
)

repaired_demand = sa.Table(
    "repaired_demand", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id"), nullable=False),
    sa.Column("demand_date", sa.Date, nullable=False),
    sa.Column("observed_units", sa.Float, nullable=False),
    sa.Column("repaired_units", sa.Float, nullable=False),
    sa.Column("was_stockout", sa.Boolean, nullable=False),
    sa.Column("rule", sa.Text, nullable=False),              # which documented rule applied
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.UniqueConstraint("sku_id", "demand_date", name="uq_repaired_sku_date"),
)

forecasts = sa.Table(
    "forecasts", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id"), nullable=False),
    sa.Column("method", sa.Text, nullable=False),            # seasonal_weekday_ma
    sa.Column("horizon_days", sa.Integer, nullable=False),
    sa.Column("train_start", sa.Date, nullable=False),
    sa.Column("train_end", sa.Date, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

forecast_points = sa.Table(
    "forecast_points", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("forecast_id", sa.Integer, sa.ForeignKey("forecasts.id"), nullable=False),
    sa.Column("target_date", sa.Date, nullable=False),
    sa.Column("p10", sa.Float, nullable=False),
    sa.Column("p50", sa.Float, nullable=False),
    sa.Column("p90", sa.Float, nullable=False),
)

action_envelopes = sa.Table(
    "action_envelopes", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id"), nullable=False),
    sa.Column("forecast_id", sa.Integer, sa.ForeignKey("forecasts.id"), nullable=False),
    sa.Column("service_level", sa.Float, nullable=False),
    sa.Column("horizon_days", sa.Integer, nullable=False),
    sa.Column("on_hand", sa.Float, nullable=False),
    sa.Column("unit_cost", sa.Float, nullable=False),
    sa.Column("unit_price", sa.Float, nullable=False),
    sa.Column("demand_p10", sa.Float, nullable=False),
    sa.Column("demand_p50", sa.Float, nullable=False),
    sa.Column("demand_p90", sa.Float, nullable=False),
    sa.Column("lower_qty", sa.Float, nullable=False),
    sa.Column("point_qty", sa.Float, nullable=False),
    sa.Column("upper_qty", sa.Float, nullable=False),
    sa.Column("regret_lower", sa.Text, nullable=False),
    sa.Column("regret_upper", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

demand_signals = sa.Table(
    "demand_signals", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("sku_id", sa.Integer, sa.ForeignKey("skus.id")),      # nullable: store-wide
    sa.Column("claim_id", sa.Text, nullable=False),
    sa.Column("signal_type", sa.Text, nullable=False),              # enum'd in the schema
    sa.Column("direction", sa.Text, nullable=False),                # increase | decrease
    sa.Column("magnitude", sa.Text, nullable=False),                # small|moderate|large
    sa.Column("window_start", sa.Date),
    sa.Column("window_end", sa.Date),
    sa.Column("statement", sa.Text, nullable=False),
    sa.Column("source", sa.Text, nullable=False),                   # note source label
    sa.Column("span_start", sa.Integer),
    sa.Column("span_end", sa.Integer),
    sa.Column("model", sa.Text, nullable=False),
    sa.Column("confidence", sa.Float, nullable=False),
    sa.Column("verification_status", sa.Text, nullable=False),      # pending|passed|rejected
    sa.Column("gates", JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        _engine = sa.create_engine(settings.database_url, pool_pre_ping=True)
        _Session = sessionmaker(bind=_engine)
    return _engine


def get_session():
    get_engine()
    return _Session()


def set_engine_for_tests(engine) -> None:
    """Tests inject their own engine (sqlite in-memory). Explicit, never automatic."""
    global _engine, _Session
    _engine = engine
    _Session = sessionmaker(bind=engine)

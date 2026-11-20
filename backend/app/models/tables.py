"""Model SQLAlchemy untuk skema backend v1."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ModelRun(Base):
    __tablename__ = "model_runs"

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="success")
    horizons: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CellRegistry(Base):
    __tablename__ = "cell_registry"

    cell_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lat_c: Mapped[float] = mapped_column(Double, nullable=False)
    lon_c: Mapped[float] = mapped_column(Double, nullable=False)
    province: Mapped[str | None] = mapped_column(Text)
    island: Mapped[str | None] = mapped_column(Text)
    peat_pct: Mapped[float | None] = mapped_column(Double)
    is_land: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PredictionLatest(Base):
    __tablename__ = "predictions_latest"

    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("model_runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    cell_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    lat_c: Mapped[float] = mapped_column(Double, nullable=False)
    lon_c: Mapped[float] = mapped_column(Double, nullable=False)
    score: Mapped[float] = mapped_column(Double, nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    province: Mapped[str | None] = mapped_column(Text)
    island: Mapped[str | None] = mapped_column(Text)
    peat_pct: Mapped[float | None] = mapped_column(Double)
    drivers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HotspotRecent(Base):
    __tablename__ = "hotspots_recent"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lon: Mapped[float] = mapped_column(Double, nullable=False)
    cell_id: Mapped[int | None] = mapped_column(BigInteger)
    confidence: Mapped[str | None] = mapped_column(Text)
    frp: Mapped[float | None] = mapped_column(Double)
    satellite: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="FIRMS_NRT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RegionDaily(Base):
    __tablename__ = "region_daily"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    level: Mapped[str] = mapped_column(Text, primary_key=True)
    region_name: Mapped[str] = mapped_column(Text, primary_key=True)
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    max_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_score: Mapped[float] = mapped_column(Double, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    very_high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_version: Mapped[str | None] = mapped_column(Text)


class MetricsDaily(Base):
    __tablename__ = "metrics_daily"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version: Mapped[str] = mapped_column(Text, primary_key=True)
    precision: Mapped[float | None] = mapped_column(Double)
    recall: Mapped[float | None] = mapped_column(Double)
    f1: Mapped[float | None] = mapped_column(Double)
    pr_auc: Mapped[float | None] = mapped_column(Double)
    base_rate: Mapped[float | None] = mapped_column(Double)
    n_positive: Mapped[int | None] = mapped_column(Integer)
    n_predicted: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

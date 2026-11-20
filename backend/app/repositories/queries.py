"""Query database yang dipakai route."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.tables import (
    CellRegistry,
    HotspotRecent,
    MetricsDaily,
    ModelRun,
    PredictionLatest,
    RegionDaily,
)


def latest_successful_run(db: Session) -> ModelRun | None:
    stmt = (
        select(ModelRun)
        .where(ModelRun.status == "success")
        .order_by(ModelRun.generated_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def predictions_for_horizon(
    db: Session,
    run_id: str,
    horizon_days: int,
    province: str | None = None,
    min_level: int | None = None,
) -> list[PredictionLatest]:
    stmt = select(PredictionLatest).where(
        PredictionLatest.run_id == run_id,
        PredictionLatest.horizon_days == horizon_days,
    )
    if province:
        stmt = stmt.where(PredictionLatest.province == province)
    if min_level is not None:
        stmt = stmt.where(PredictionLatest.level >= min_level)
    return list(db.scalars(stmt))


def latest_hotspot_at(db: Session) -> datetime | None:
    return db.scalar(select(func.max(HotspotRecent.observed_at)))


def hotspots_since(db: Session, since: datetime) -> list[HotspotRecent]:
    stmt = (
        select(HotspotRecent)
        .where(HotspotRecent.observed_at >= since)
        .order_by(HotspotRecent.observed_at.desc())
    )
    return list(db.scalars(stmt))


def cell_predictions(
    db: Session,
    run_id: str,
    cell_id: int,
    horizon_days: int | None = None,
) -> list[PredictionLatest]:
    stmt = select(PredictionLatest).where(
        PredictionLatest.run_id == run_id,
        PredictionLatest.cell_id == cell_id,
    )
    if horizon_days is not None:
        stmt = stmt.where(PredictionLatest.horizon_days == horizon_days)
    stmt = stmt.order_by(PredictionLatest.horizon_days)
    return list(db.scalars(stmt))


def cell_hotspots(db: Session, cell_id: int, since: datetime) -> list[HotspotRecent]:
    stmt = (
        select(HotspotRecent)
        .where(
            HotspotRecent.cell_id == cell_id,
            HotspotRecent.observed_at >= since,
        )
        .order_by(HotspotRecent.observed_at.desc())
    )
    return list(db.scalars(stmt))


def cell_registry(db: Session, cell_id: int) -> CellRegistry | None:
    return db.get(CellRegistry, cell_id)


def region_daily_latest(
    db: Session,
    level: str,
    horizon_days: int,
    limit: int,
) -> tuple[date | None, list[RegionDaily]]:
    latest_date = db.scalar(
        select(func.max(RegionDaily.date)).where(
            RegionDaily.level == level,
            RegionDaily.horizon_days == horizon_days,
        )
    )
    if latest_date is None:
        return None, []
    stmt = (
        select(RegionDaily)
        .where(
            RegionDaily.date == latest_date,
            RegionDaily.level == level,
            RegionDaily.horizon_days == horizon_days,
        )
        .order_by(RegionDaily.max_level.desc(), RegionDaily.max_score.desc())
        .limit(limit)
    )
    return latest_date, list(db.scalars(stmt))


def metrics_since(
    db: Session,
    days: int,
    horizon_days: int | None = None,
) -> list[MetricsDaily]:
    since = date.today() - timedelta(days=days)
    stmt = select(MetricsDaily).where(MetricsDaily.date >= since)
    if horizon_days is not None:
        stmt = stmt.where(MetricsDaily.horizon_days == horizon_days)
    stmt = stmt.order_by(MetricsDaily.date.desc(), MetricsDaily.horizon_days)
    return list(db.scalars(stmt))

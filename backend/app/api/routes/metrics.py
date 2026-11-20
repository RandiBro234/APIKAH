"""Metrik verifikasi harian."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...repositories import queries
from ...schemas.risk import MetricRecord, MetricsResponse
from ..helpers import parse_horizon

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    days: int = Query(default=30, ge=1, le=365),
    horizon: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MetricsResponse:
    horizon_days = parse_horizon(horizon) if horizon else None
    rows = queries.metrics_since(db, days, horizon_days)
    return MetricsResponse(
        metrics=[
            MetricRecord(
                date=row.date,
                horizon_days=row.horizon_days,
                precision=row.precision,
                recall=row.recall,
                f1=row.f1,
                pr_auc=row.pr_auc,
                base_rate=row.base_rate,
                model_version=row.model_version,
            )
            for row in rows
        ]
    )

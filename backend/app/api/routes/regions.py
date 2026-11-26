"""Peringkat wilayah."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...repositories import queries
from ...schemas.risk import RegionRecord, RegionResponse
from ..helpers import parse_horizon

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=RegionResponse)
def get_regions(
    level: Literal["province", "kabupaten"] = Query(...),
    horizon: str = Query(default="1"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RegionResponse:
    horizon_days = parse_horizon(horizon)
    if horizon_days == 0:
        raise HTTPException(status_code=400, detail="Peringkat wilayah butuh horizon >= 1")

    latest_date, rows = queries.region_daily_latest(db, level, horizon_days, limit)
    if latest_date is None:
        raise HTTPException(status_code=404, detail="Belum ada agregat wilayah")

    return RegionResponse(
        date=latest_date,
        horizon_days=horizon_days,
        level=level,
        regions=[
            RegionRecord(
                name=row.region_name,
                max_level=row.max_level,
                max_score=row.max_score,
                high_count=row.high_count,
                very_high_count=row.very_high_count,
                cell_count=row.cell_count,
            )
            for row in rows
        ],
    )

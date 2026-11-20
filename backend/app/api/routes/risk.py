"""Layer risiko per horizon sebagai GeoJSON."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...repositories import queries
from ...schemas.risk import (
    PolygonGeometry,
    RiskFeature,
    RiskFeatureCollection,
    RiskProperties,
)
from ..helpers import cell_polygon, parse_horizon

router = APIRouter(tags=["risk"])


@router.get("/risk/{horizon}", response_model=RiskFeatureCollection)
def get_risk(
    horizon: str,
    response: Response,
    province: str | None = Query(default=None),
    level: int | None = Query(default=None, ge=1, le=4),
    db: Session = Depends(get_db),
) -> RiskFeatureCollection:
    horizon_days = parse_horizon(horizon)

    if horizon_days == 0:
        response.headers["X-Data-Note"] = (
            "d0 adalah observasi hotspot; gunakan /v1/hotspots"
        )
        return RiskFeatureCollection(features=[])

    run = queries.latest_successful_run(db)
    if run is None:
        raise HTTPException(status_code=404, detail="Belum ada run prediksi")

    rows = queries.predictions_for_horizon(
        db, run.run_id, horizon_days, province=province, min_level=level
    )

    response.headers["ETag"] = f'"{run.run_id}-{horizon_days}"'
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"

    features = [
        RiskFeature(
            id=row.cell_id,
            properties=RiskProperties(
                cell_id=row.cell_id,
                level=row.level,
                score=row.score,
                province=row.province,
                island=row.island,
                drivers=list(row.drivers or []),
                peat_pct=row.peat_pct,
                horizon_days=row.horizon_days,
                target_date=row.target_date,
            ),
            geometry=PolygonGeometry(coordinates=cell_polygon(row.lat_c, row.lon_c)),
        )
        for row in rows
    ]
    return RiskFeatureCollection(features=features)

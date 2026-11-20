"""Detail satu sel grid."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...repositories import queries
from ...schemas.risk import CellDetail, CellHotspot, CellPrediction
from ..helpers import normalize_confidence, parse_horizon, to_local_iso, utcnow

router = APIRouter(tags=["cells"])


@router.get("/cells/{cell_id}", response_model=CellDetail)
def get_cell(
    cell_id: int,
    horizon: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CellDetail:
    horizon_days = parse_horizon(horizon) if horizon else None

    run = queries.latest_successful_run(db)
    if run is None:
        raise HTTPException(status_code=404, detail="Belum ada run prediksi")

    predictions = queries.cell_predictions(db, run.run_id, cell_id, horizon_days)
    registry = queries.cell_registry(db, cell_id)

    if not predictions and registry is None:
        raise HTTPException(status_code=404, detail="Sel tidak ditemukan")

    hotspots = queries.cell_hotspots(db, cell_id, utcnow() - timedelta(days=7))

    if registry is not None:
        lat_c, lon_c = registry.lat_c, registry.lon_c
        province, island, peat_pct = registry.province, registry.island, registry.peat_pct
    else:
        first = predictions[0]
        lat_c, lon_c = first.lat_c, first.lon_c
        province, island, peat_pct = first.province, first.island, first.peat_pct

    return CellDetail(
        cell_id=cell_id,
        lat_c=lat_c,
        lon_c=lon_c,
        province=province,
        island=island,
        peat_pct=peat_pct,
        predictions=[
            CellPrediction(
                horizon_days=row.horizon_days,
                target_date=row.target_date,
                score=row.score,
                level=row.level,
                drivers=list(row.drivers or []),
            )
            for row in predictions
        ],
        hotspots_7d=[
            CellHotspot(
                time_local=to_local_iso(row.observed_at),
                confidence=normalize_confidence(row.confidence),
                frp=row.frp,
            )
            for row in hotspots
        ],
    )

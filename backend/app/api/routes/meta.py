"""Metadata run terbaru."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...repositories import queries
from ...schemas.risk import MetaResponse
from ..helpers import to_local_iso

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaResponse)
def get_meta(db: Session = Depends(get_db)) -> MetaResponse:
    run = queries.latest_successful_run(db)
    if run is None:
        raise HTTPException(status_code=404, detail="Belum ada run prediksi")
    latest_hotspot = queries.latest_hotspot_at(db)
    return MetaResponse(
        generated_at=to_local_iso(run.generated_at),
        data_hotspot_latest_at=to_local_iso(latest_hotspot) if latest_hotspot else None,
        model_version=run.model_version,
        data_version=run.data_version,
        stale_after_hours=settings.stale_after_hours,
        is_sample=False,
        status=run.status,
        horizons=list(run.horizons or []),
    )

"""Hotspot aktual 72 jam terakhir."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...repositories import queries
from ...schemas.risk import (
    HotspotFeature,
    HotspotFeatureCollection,
    HotspotProperties,
    PointGeometry,
)
from ..helpers import normalize_confidence, to_local_iso, utcnow

router = APIRouter(tags=["hotspots"])


@router.get("/hotspots", response_model=HotspotFeatureCollection)
def get_hotspots(
    response: Response,
    hours: int = Query(default=72, ge=1, le=168),
    db: Session = Depends(get_db),
) -> HotspotFeatureCollection:
    since = utcnow() - timedelta(hours=hours)
    rows = queries.hotspots_since(db, since)

    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"

    features = [
        HotspotFeature(
            properties=HotspotProperties(
                time_local=to_local_iso(row.observed_at),
                confidence=normalize_confidence(row.confidence),
                frp=row.frp,
            ),
            geometry=PointGeometry(coordinates=[row.lon, row.lat]),
        )
        for row in rows
    ]
    return HotspotFeatureCollection(features=features)

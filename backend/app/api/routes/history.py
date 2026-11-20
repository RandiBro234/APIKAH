"""Riwayat prediksi per sel.

Arsip historis disimpan di R2 (Parquet/GeoJSON), bukan di Postgres.
Endpoint ini disiapkan agar kontrak frontend stabil, tetapi implementasinya
menyusul pada fase arsip.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["history"])


@router.get("/history")
def get_history(
    cell_id: int = Query(...),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    horizon: str | None = Query(default=None),
) -> None:
    raise HTTPException(
        status_code=501,
        detail="Arsip historis ada di R2; endpoint menyusul pada fase arsip.",
    )

"""Utilitas bersama untuk route API."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

LOCAL_TZ = ZoneInfo("Asia/Jakarta")
GRID_STEP = 0.25


def parse_horizon(value: str) -> int:
    """Terima d0-d3, h1-h21, atau angka 0-21."""
    raw = value.strip().lower()
    if raw.startswith("d"):
        raw = raw[1:]
    elif raw.startswith("h"):
        raw = raw[1:]
    try:
        horizon = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="horizon harus d0-d3, h1-h21, atau angka 0-21",
        ) from exc
    if horizon < 0 or horizon > 21:
        raise HTTPException(status_code=400, detail="horizon di luar rentang 0-21")
    return horizon


def cell_polygon(lat_c: float, lon_c: float, step: float = GRID_STEP) -> list[list[list[float]]]:
    """Poligon sel 0,25 derajat dalam urutan [lon, lat] sesuai GeoJSON."""
    half = step / 2
    west, east = lon_c - half, lon_c + half
    south, north = lat_c - half, lat_c + half
    return [
        [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]
    ]


def normalize_confidence(value: str | None) -> str | None:
    """FIRMS memakai 'l', 'n', 'h'; beberapa sumber memakai kata penuh."""
    if not value:
        return None
    text = value.strip().lower()
    if text.startswith("h"):
        return "h"
    if text.startswith("n"):
        return "n"
    if text.startswith("l"):
        return "l"
    return None


def to_local_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).isoformat()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

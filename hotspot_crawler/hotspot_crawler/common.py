"""Utilitas bersama: bulan, retry, download dengan resume, manifest, logging."""
from __future__ import annotations

import json
import logging
import math
import time
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterator

import config

log = logging.getLogger("crawler")


def setup_logging(name: str) -> None:
    config.LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(config.LOGS / f"{name}.log")],
    )


def iter_months(start: date = config.START, end: date = config.END) -> Iterator[tuple[int, int]]:
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def days_in_month(year: int, month: int) -> list[str]:
    return [f"{d:02d}" for d in range(1, monthrange(year, month)[1] + 1)]


def months_from_end(year: int, month: int, end: date = config.END) -> int:
    return (end.year - year) * 12 + (end.month - month)


def with_retry(fn: Callable, *args, retries: int = config.RETRIES,
               backoff: int = config.BACKOFF_SECONDS, **kwargs):
    last = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - sengaja luas, lalu dicatat
            last = exc
            log.warning("percobaan %d/%d gagal: %s", attempt, retries, str(exc)[:300])
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise last  # type: ignore[misc]


def done(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def download_file(url: str, dest: Path, timeout: int = config.HTTP_TIMEOUT) -> str:
    """Unduh dengan resume (.part). Return 'ok' | 'skipped' | 'missing' (404)."""
    import requests

    if done(dest):
        return "skipped"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    pos = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={pos}-"} if pos else {}
    with requests.get(url, stream=True, headers=headers, timeout=timeout) as r:
        if r.status_code == 404:
            return "missing"
        if r.status_code == 416:      # part sudah lengkap
            part.rename(dest)
            return "ok"
        r.raise_for_status()
        mode = "ab" if (pos and r.status_code == 206) else "wb"
        with open(part, mode) as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
    part.rename(dest)
    return "ok"


# ---------------------------------------------------------------- manifest
def manifest_path(name: str) -> Path:
    return config.LOGS / f"manifest_{name}.json"


def manifest_load(name: str) -> dict:
    p = manifest_path(name)
    return json.loads(p.read_text()) if p.exists() else {}


def manifest_update(name: str, key: str, status: str, note: str = "") -> None:
    config.LOGS.mkdir(parents=True, exist_ok=True)
    m = manifest_load(name)
    m[key] = {"status": status, "note": note[:300], "ts": datetime.now().isoformat(timespec="seconds")}
    manifest_path(name).write_text(json.dumps(m, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- tile helper
def floor_to(x: float, step: int) -> int:
    return int(math.floor(x / step) * step)


def tile_origins(north: float, west: float, south: float, east: float, step: int) -> list[tuple[int, int]]:
    """Daftar (lat_sw, lon_sw) tile bertepi `step` derajat yang menutupi bbox."""
    lats = range(floor_to(south, step), math.ceil(north / step) * step, step)
    lons = range(floor_to(west, step), math.ceil(east / step) * step, step)
    return [(la, lo) for la in lats for lo in lons]


def ns_ew(lat: int, lon: int) -> tuple[str, int, str, int]:
    return ("N" if lat >= 0 else "S"), abs(lat), ("E" if lon >= 0 else "W"), abs(lon)

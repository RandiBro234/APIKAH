"""NASA FIRMS daily hotspot crawler."""
from __future__ import annotations

import argparse
import io
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from ..shared import config

BBOX = "94,-11.5,141.5,6.5"
SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT")
KEEP = (
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "confidence",
    "frp",
    "bright_ti4",
    "daynight",
    "satellite",
)


def _key() -> str:
    key = os.environ.get("FIRMS_KEY", "").strip()
    if not key:
        raise RuntimeError("FIRMS_KEY belum tersedia")
    return key


def _request(source: str, start: date, days: int, retries: int) -> pd.DataFrame:
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{_key()}/{source}/{BBOX}/{days}/{start.isoformat()}"
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            text = response.text.strip()
            if not text or text.startswith("<"):
                return pd.DataFrame(columns=KEEP)
            frame = pd.read_csv(io.StringIO(text))
            return frame[[column for column in KEEP if column in frame.columns]]
        except (requests.RequestException, pd.errors.ParserError):
            if attempt + 1 == retries:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Gagal mengambil {source}")


def crawl_day(target: date, lookback_hours: int = 72, retries: int = 3) -> list[Path]:
    if lookback_hours < 24 or lookback_hours > 240:
        raise ValueError("lookback_hours harus berada di antara 24 dan 240")
    start = target - timedelta(hours=lookback_hours - 24)
    days = max(1, (target - start).days + 1)
    output_dir = config.DATA_DIR / "hotspot_indonesia" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in SOURCES:
        frame = _request(source, start, days, retries)
        if "acq_date" in frame:
            frame["acq_date"] = pd.to_datetime(frame["acq_date"], errors="coerce").dt.date.astype("string")
        path = output_dir / f"{source}_{target.isoformat()}.parquet"
        temporary = path.with_suffix(f".parquet.{os.getpid()}.tmp")
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ambil hotspot NASA FIRMS untuk observasi 72 jam terakhir")
    parser.add_argument("--date", default=None, help="tanggal target UTC YYYY-MM-DD; default hari ini")
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)
    target = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    for path in crawl_day(target, args.lookback_hours, args.retries):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

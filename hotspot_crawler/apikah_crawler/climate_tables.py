"""Persist tabular climate-index values as compact Parquet tables."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def write_climate_parquet(name: str, rows: list[tuple[int, int, float]], dest: Path) -> None:
    """Write ``year, month, <name>`` atomically with Zstandard compression."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(f"{dest.stem}.{os.getpid()}.part.parquet")
    try:
        pd.DataFrame(rows, columns=["year", "month", name]).to_parquet(
            temporary, index=False, compression="zstd")
        temporary.replace(dest)
    finally:
        temporary.unlink(missing_ok=True)

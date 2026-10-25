"""Gabungkan semua sumber menjadi satu tabel latih (TODO #19).

    python build_training_table.py                     # semua bulan yang datanya ada
    python build_training_table.py --from 2023-07 --to 2023-08
    python build_training_table.py --no-labels          # tabel fitur saja (untuk inferensi)

Masukan
    data/processed/era5_daily/YYYY-MM.parquet       16 kolom cuaca (OTORITATIF)
    data/processed/fire_daily/YYYY-MM.parquet        4 indeks api CEMS
    data/processed/features_daily/YYYY-MM.parquet   22 kolom turunan
        (12 kolom cuaca di berkas ini DIABAIKAN -- sudah diambil dari era5_daily,
         supaya tidak terhitung dua kali)
    data/processed/static_features.parquet          26 kolom statis (per sel, bila sudah ada)
    config.HOTSPOT_LABELS                           label hotspot tingkat piksel
Keluaran
    data/processed/training/YYYY-MM.parquet

ATURAN ANTI-BOCOR (bagian 7.2 dokumen)
    Baris untuk tanggal T hanya memuat informasi sampai T-1:
      - cuaca + indeks api dari era5/fire DIGESER `--lag` hari (default 1)
      - fitur turunan dari features_daily SUDAH digeser oleh build_derived_features.py,
        jadi dipakai APA ADANYA (jangan digeser dua kali -- itu kesalahan yang mudah terjadi)
      - indeks iklim: HANYA versi lag (`nino34_lag1..3`, `dmi_lag1..3`). Kolom bulan
        berjalan (`nino34`, `dmi`) DIBUANG karena rata-rata bulan T masih memuat hari T
      - statis: tidak bergantung waktu
    Untuk menggeser tanpa kehilangan hari pertama bulan, bulan SEBELUMNYA dibaca sebagai
    konteks, lalu barisnya dibuang setelah penggeseran.

Kolom target (dari label)
    n_hotspot        jumlah titik api di sel itu pada hari itu
    n_hotspot_high   jumlah dengan confidence 'h'
    max_frp          FRP maksimum (MW) -- proksi intensitas
    ada_api          1 bila n_hotspot > 0 -- target klasifikasi biner
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import config
from common import iter_months, log, setup_logging
from postprocess_era5 import cell_center

KEYS = ["date", "lat_c", "lon_c"]
TARGET_COLS = ["n_hotspot", "n_hotspot_high", "max_frp", "ada_api"]
# Kolom iklim bulan berjalan yang bocor (memuat hari T) -> dibuang
CLIMATE_LEAKY = ["nino34", "dmi"]


# ------------------------------------------------------------------ fungsi murni
def parse_ym(s: str) -> date:
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def derived_columns(features_cols, weather_cols) -> list[str]:
    """Kolom dari features_daily yang BUKAN salinan cuaca (supaya tidak terhitung dua kali)."""
    return [c for c in features_cols
            if c not in KEYS and c not in set(weather_cols)]


def aggregate_labels(raw: pd.DataFrame) -> pd.DataFrame:
    """Label piksel -> satu baris per (date, lat_c, lon_c) dengan kolom target.

    `raw` harus punya: latitude, longitude, date, confidence, frp.
    """
    if raw.empty:
        return pd.DataFrame(columns=KEYS + TARGET_COLS)
    d = raw.copy()
    d["lat_c"] = cell_center(d["latitude"].to_numpy())
    d["lon_c"] = cell_center(d["longitude"].to_numpy())
    g = d.groupby(KEYS, sort=False)
    out = pd.DataFrame({"n_hotspot": g.size(), "max_frp": g["frp"].max()})
    # confidence FIRMS: 'l' (low), 'n' (nominal), 'h' (high). Toleran terhadap 'high'.
    conf = d["confidence"].astype(str).str.lower().str.strip()
    tinggi = d[conf.str.startswith("h")]
    out["n_hotspot_high"] = (tinggi.groupby(KEYS, sort=False).size()
                            if len(tinggi) else pd.Series(dtype="int64"))
    out["n_hotspot_high"] = out["n_hotspot_high"].fillna(0).astype("int32")
    out = out.reset_index()
    out["n_hotspot"] = out["n_hotspot"].astype("int32")
    out["ada_api"] = (out["n_hotspot"] > 0).astype("int8")
    return out[KEYS + TARGET_COLS]


def shift_by_cell(df: pd.DataFrame, cols, lag: int) -> pd.DataFrame:
    """Geser `cols` sebanyak `lag` hari per sel. `df` harus sudah terurut tanggal."""
    g = df.groupby(["lat_c", "lon_c"], sort=False)
    for c in cols:
        if c in df.columns:
            df[c] = g[c].shift(lag)
    return df


# ------------------------------------------------------------------ pembaca
def read_month(folder: Path, year: int, month: int) -> pd.DataFrame:
    p = folder / f"{year}-{month:02d}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def load_labels(start: date, end: date) -> pd.DataFrame:
    """Baca label hotspot sekali, potong ke rentang, agregasi ke grid 0,25 derajat."""
    p = Path(config.HOTSPOT_LABELS)
    if not p.exists():
        log.warning("label hotspot tidak ada: %s -- tabel akan dibuat tanpa kolom target", p)
        return pd.DataFrame(columns=KEYS + TARGET_COLS)
    kolom = ["latitude", "longitude", "acq_date", "confidence", "frp"]
    d = pd.read_parquet(p, columns=kolom)
    d["date"] = pd.to_datetime(d["acq_date"]).dt.floor("D")
    awal = pd.Timestamp(start.year, start.month, 1)
    akhir = pd.Timestamp(end.year, end.month, 1) + pd.offsets.MonthEnd(0)
    d = d[(d["date"] >= awal) & (d["date"] <= akhir)]
    log.info("label: %d titik api pada rentang %s .. %s", len(d), awal.date(), akhir.date())
    return aggregate_labels(d)


def load_static() -> pd.DataFrame:
    p = config.PROCESSED / "static_features.parquet"
    if not p.exists():
        log.warning("static_features.parquet belum ada -- kolom statis dilewati "
                    "(jalankan build_static_features.py dulu)")
        return pd.DataFrame(columns=["lat_c", "lon_c"])
    d = pd.read_parquet(p)
    return d.drop_duplicates(["lat_c", "lon_c"])


# ------------------------------------------------------------------ penggabungan
def merge_month(year: int, month: int, labels: pd.DataFrame, static: pd.DataFrame,
                lag: int, pack_derived: list[str]) -> pd.DataFrame | None:
    e = read_month(config.PROCESSED / "era5_daily", year, month)
    if e.empty:
        log.warning("lewati %d-%02d: era5_daily belum ada", year, month)
        return None
    f = read_month(config.PROCESSED / "fire_daily", year, month)
    d = read_month(config.PROCESSED / "features_daily", year, month)

    # Bulan sebelumnya sebagai konteks penggeseran (supaya hari pertama bulan tidak kosong).
    py, pm = prev_month(year, month)
    e_prev = read_month(config.PROCESSED / "era5_daily", py, pm)
    f_prev = read_month(config.PROCESSED / "fire_daily", py, pm)

    cuaca = [c for c in e.columns if c not in KEYS]
    api = [c for c in f.columns if c not in KEYS]

    # --- rangkai era5 + fire (bulan ini + konteks bulan lalu)
    inti = pd.concat([e_prev, e], ignore_index=True) if not e_prev.empty else e.copy()
    if not f.empty or not f_prev.empty:
        inti = inti.merge(pd.concat([f_prev, f], ignore_index=True), on=KEYS, how="left")
    inti["_darat"] = inti["t2m_mean"].notna()        # penanda SEBELUM digeser
    inti = inti.sort_values(["lat_c", "lon_c", "date"]).reset_index(drop=True)
    inti = shift_by_cell(inti, cuaca + api, lag)     # ANTI-BOCOR

    # --- fitur turunan: SUDAH digeser di sumbernya, dipakai apa adanya
    if not d.empty and pack_derived:
        ambil = KEYS + [c for c in pack_derived if c in d.columns]
        inti = inti.merge(d[ambil], on=KEYS, how="left")

    # --- batasi ke bulan ini (buang konteks bulan lalu) + buang sel laut
    awal = pd.Timestamp(year, month, 1)
    akhir = awal + pd.offsets.MonthEnd(0)
    inti = inti[(inti["date"] >= awal) & (inti["date"] <= akhir)]
    n_sebelum = len(inti)
    inti = inti[inti["_darat"]].drop(columns=["_darat"])
    if n_sebelum != len(inti):
        log.info("  buang %d baris sel laut (tanpa cuaca)", n_sebelum - len(inti))

    # --- statis + label
    if not static.empty:
        inti = inti.merge(static, on=["lat_c", "lon_c"], how="left")
    if not labels.empty:
        inti = inti.merge(labels, on=KEYS, how="left")
        # sel-hari tanpa baris label = tidak ada api (bukan data hilang)
        inti["n_hotspot"] = inti["n_hotspot"].fillna(0).astype("int32")
        inti["n_hotspot_high"] = inti["n_hotspot_high"].fillna(0).astype("int32")
        inti["ada_api"] = inti["ada_api"].fillna(0).astype("int8")
    return inti.sort_values(KEYS).reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=parse_ym, default=config.START)
    ap.add_argument("--to", dest="end", type=parse_ym, default=config.END)
    ap.add_argument("--lag", type=int, default=1,
                    help="geser cuaca + indeks api (hari), default 1")
    ap.add_argument("--no-labels", action="store_true", help="tanpa kolom target")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)
    setup_logging("training_table")

    dest_dir = Path(args.out_dir) if args.out_dir else config.PROCESSED / "training"
    dest_dir.mkdir(parents=True, exist_ok=True)

    static = load_static()
    labels = pd.DataFrame(columns=KEYS + TARGET_COLS) if args.no_labels \
        else load_labels(args.start, args.end)

    # tentukan kolom turunan sekali saja, dari berkas pertama yang ada
    pack_derived: list[str] = []
    for y, m in iter_months(args.start, args.end):
        probe = read_month(config.PROCESSED / "features_daily", y, m)
        if not probe.empty:
            e = read_month(config.PROCESSED / "era5_daily", y, m)
            semua = derived_columns(probe.columns, [c for c in e.columns if c not in KEYS])
            bocor = [c for c in CLIMATE_LEAKY if c in semua]
            pack_derived = [c for c in semua if c not in set(bocor)]
            log.info("kolom turunan dari features_daily: %d"
                     " (+%d kolom iklim bulan berjalan DIBUANG karena bocor: %s)",
                     len(pack_derived), len(bocor), bocor)
            break

    n_tulis, total = 0, 0
    for y, m in iter_months(args.start, args.end):
        tabel = merge_month(y, m, labels, static, args.lag, pack_derived)
        if tabel is None or tabel.empty:
            continue
        dest = dest_dir / f"{y}-{m:02d}.parquet"
        tabel.to_parquet(dest, index=False)
        n_tulis += 1
        total += len(tabel)
        log.info("tulis %s (%d baris, %d kolom)", dest.name, len(tabel), len(tabel.columns))
    log.info("selesai: %d bulan, %d baris total", n_tulis, total)
    return 0 if n_tulis else 1


if __name__ == "__main__":
    sys.exit(main())

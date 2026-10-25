"""Ubah NetCDF CEMS Fire menjadi tabel harian per sel 0,25 derajat (TODO #4).

    python postprocess_fire.py                  # semua bulan yang ada
    python postprocess_fire.py --from 2023-07 --to 2023-08

Keluaran: data/processed/fire_daily/YYYY-MM.parquet
Kolom   : date, lat_c, lon_c, fwi, dc, dmc, kbdi

DUA HAL YANG DIBUKTIKAN DARI BERKAS ASLI (2023-07), BUKAN DARI DOKUMENTASI:

1. Nama variabel di dalam NetCDF BERBEDA dari nama parameter request:

       request (crawl)              isi NetCDF
       ---------------------------  ---------
       fire_weather_index       ->  fwinx
       drought_code             ->  drtcode
       duff_moisture_code       ->  dufmcode
       keetch_byram_drought_index -> kbdi

   Menebak nama request akan langsung gagal dengan KeyError.

2. Grid CEMS sudah 0,25 derajat, TETAPI pusat selnya di KELIPATAN 0,25
   (94.0, 94.25, ..., 141.5), sedangkan grid label dan ERA5 memakai
   n*0,25 + 0,125. Jadi keduanya berselisih SETENGAH SEL. Menggabungkan
   langsung berdasarkan koordinat menghasilkan NOL baris yang cocok.

   Karena pusat sel CEMS jatuh tepat di TEPI sel label, tumpang tindih areanya
   selalu 50/50 di tiap arah -> nilai sel label = rata-rata 4 sel CEMS di
   sekitarnya (masing-masing 25%). Fungsi `map_to_label_grid` melakukan itu, dan
   mengabaikan NaN supaya sel pesisir tidak ikut kosong hanya karena satu
   tetangganya laut.

CEMS Fire tidak punya pergeseran tanggal seperti ERA5-Land accum: satu nilai
per hari, tersedia juga untuk hari terakhir bulan (tidak perlu lookahead).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd

import config
from common import done, iter_months, log, setup_logging
from postprocess_era5 import time_name

# nama di NetCDF -> nama kolom keluaran (dibuktikan dari berkas, lihat docstring)
SHORT = {"fwinx": "fwi", "drtcode": "dc", "dufmcode": "dmc", "kbdi": "kbdi"}
STEP = 0.25


# ------------------------------------------------------------------ fungsi murni
def index_of(coords, values, tol: float = 1e-6) -> np.ndarray:
    """Indeks di `coords` untuk tiap nilai di `values`; -1 bila tidak ketemu."""
    c = np.asarray(coords, dtype="float64")
    v = np.asarray(values, dtype="float64")
    out = np.full(v.size, -1, dtype="int64")
    for k, val in enumerate(v):
        hit = np.flatnonzero(np.abs(c - val) <= tol)
        if hit.size:
            out[k] = int(hit[0])
    return out


def pair_mean(arr: np.ndarray, axis: int, i0, i1) -> np.ndarray:
    """Rata-ratakan dua irisan sepanjang `axis`, mengabaikan NaN.

    Dipakai untuk menggabungkan dua sel CEMS yang bertetangga. Bila kedua-duanya
    NaN, hasilnya NaN (bukan 0) -- supaya sel laut tetap dikenali sebagai kosong.
    """
    p = np.take(np.asarray(arr, dtype="float64"), np.asarray(i0), axis=axis)
    q = np.take(np.asarray(arr, dtype="float64"), np.asarray(i1), axis=axis)
    fp, fq = np.isfinite(p), np.isfinite(q)
    s = np.where(fp, p, 0.0) + np.where(fq, q, 0.0)
    n = fp.astype("float64") + fq.astype("float64")
    return np.divide(s, n, out=np.full(s.shape, np.nan), where=n > 0)


def map_to_label_grid(arr: np.ndarray, cems_lat, cems_lon, label_lat, label_lon,
                      step: float = STEP) -> np.ndarray:
    """(time, lat, lon) grid CEMS -> grid label (offset setengah sel), rata-rata 2x2.

    Pusat sel label L berimpit dengan tepi sel CEMS di L-step/2 dan L+step/2, jadi
    dua indeks CEMS itu yang dirata-ratakan (per arah). Sel label yang tidak punya
    pasangan lengkap (paling luar) dikembalikan sebagai NaN.
    """
    i0 = index_of(cems_lat, np.asarray(label_lat) - step / 2)
    i1 = index_of(cems_lat, np.asarray(label_lat) + step / 2)
    j0 = index_of(cems_lon, np.asarray(label_lon) - step / 2)
    j1 = index_of(cems_lon, np.asarray(label_lon) + step / 2)
    lat_ok = (i0 >= 0) & (i1 >= 0)
    lon_ok = (j0 >= 0) & (j1 >= 0)

    il0, il1 = np.where(lat_ok, i0, 0), np.where(lat_ok, i1, 0)
    jl0, jl1 = np.where(lon_ok, j0, 0), np.where(lon_ok, j1, 0)

    lat_avg = pair_mean(arr, 1, il0, il1)          # (time, n_lat_label, n_lon_cems)
    out = pair_mean(lat_avg, 2, jl0, jl1)          # (time, n_lat_label, n_lon_label)
    out[:, ~lat_ok, :] = np.nan
    out[:, :, ~lon_ok] = np.nan
    return out


# ---------------------------------------------------------------------- masukan
def label_grid() -> tuple[np.ndarray, np.ndarray]:
    """Grid sel 0,25 derajat acuan (konvensi sama dengan label dan era5_daily)."""
    src = config.PROCESSED / "era5_daily"
    files = sorted(src.glob("*.parquet"))
    if files:
        d = pd.read_parquet(files[0], columns=["lat_c", "lon_c"]).drop_duplicates()
        lat = np.sort(d["lat_c"].unique())
        lon = np.sort(d["lon_c"].unique())
        log.info("grid label dari %s: %d lat x %d lon", files[0].name, lat.size, lon.size)
        return lat, lon
    n, w, s, e = config.AREA
    lat = np.arange(np.floor(s / STEP) * STEP + STEP / 2, n, STEP)
    lon = np.arange(np.floor(w / STEP) * STEP + STEP / 2, e, STEP)
    log.warning("era5_daily belum ada; grid label dibuat dari bbox area (%d x %d)",
                lat.size, lon.size)
    return lat, lon


def fire_daily(ds, lat: np.ndarray, lon: np.ndarray) -> pd.DataFrame:
    """NetCDF CEMS yang sudah dibuka -> kerangka panjang per (date, lat_c, lon_c)."""
    tn = time_name(ds)
    tanggal = pd.to_datetime(ds[tn].values).floor("D")

    kolom = {}
    for asal, tujuan in SHORT.items():
        if asal not in ds:
            raise KeyError(f"variabel {asal!r} tidak ada di NetCDF; ada: {list(ds.data_vars)}")
        arr = np.asarray(ds[asal].values, dtype="float64")
        if arr.ndim == 4 and arr.shape[1] == 1:       # (time, 1, lat, lon)
            arr = arr[:, 0]
        kolom[tujuan] = map_to_label_grid(arr, ds["latitude"].values,
                                          ds["longitude"].values, lat, lon)

    n_lat, n_lon = lat.size, lon.size
    n_time = len(tanggal)
    kerangka = pd.DataFrame({
        "date": np.repeat(tanggal, n_lat * n_lon),
        "lat_c": np.tile(np.repeat(lat, n_lon), n_time),
        "lon_c": np.tile(np.tile(lon, n_lat), n_time),
    })
    for tujuan, arr in kolom.items():
        kerangka[tujuan] = arr.reshape(-1)
    return kerangka


# ------------------------------------------------------------------ pemrosesan
def process_month(year: int, month: int, lat: np.ndarray, lon: np.ndarray) -> bool:
    import xarray as xr

    src = config.RAW / "cems_fire" / f"{year}-{month:02d}.nc"
    dest = config.PROCESSED / "fire_daily" / f"{year}-{month:02d}.parquet"
    if done(dest):
        return True
    if not done(src):
        log.warning("lewati %d-%02d: berkas mentah CEMS belum ada", year, month)
        return False

    with xr.open_dataset(src) as ds:
        tabel = fire_daily(ds, lat, lon)

    # CEMS Fire tidak punya pergeseran accum: satu nilai per hari. Potong ke bulan ini
    # supaya konsisten dengan era5_daily (dan menggabungkan bulan tidak menghasilkan kunci ganda).
    awal = pd.Timestamp(year, month, 1)
    akhir = awal + pd.offsets.MonthEnd(0)
    tabel = tabel[(tabel["date"] >= awal) & (tabel["date"] <= akhir)]

    dest.parent.mkdir(parents=True, exist_ok=True)
    tabel.sort_values(["date", "lat_c", "lon_c"]).reset_index(drop=True) \
        .to_parquet(dest, index=False)
    log.info("tulis %s (%d baris, %d hari)", dest, len(tabel), tabel["date"].nunique())
    return True


def parse_ym(s: str) -> date:
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=parse_ym, default=config.START)
    ap.add_argument("--to", dest="end", type=parse_ym, default=config.END)
    args = ap.parse_args(argv)
    setup_logging("postprocess_fire")

    lat, lon = label_grid()
    n_ok = sum(process_month(y, m, lat, lon) for y, m in iter_months(args.start, args.end))
    log.info("selesai: %d bulan terproses", n_ok)
    return 0 if n_ok else 1


if __name__ == "__main__":
    sys.exit(main())

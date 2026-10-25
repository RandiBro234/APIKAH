"""Ubah NetCDF ERA5-Land mentah (instant + accum) menjadi tabel harian per sel 0,25 derajat.

    python postprocess_era5.py                 # semua bulan yang ada
    python postprocess_era5.py --from 2023-01 --to 2023-12

Keluaran: data/processed/era5_daily/YYYY-MM.parquet
Kolom   : date, lat_c, lon_c, t2m_mean/max/min, rh_mean/min, wind_mean/max, u10_mean, v10_mean,
          vpd_mean/max, swvl1_mean, swvl4_mean, precip_mm, ssrd_mjm2, pev_mm
Catatan : hari = hari UTC. Akumulasi (hujan, radiasi, PET) diambil dari nilai 00:00 UTC hari D+1
          sebagai total hari D (konvensi ERA5-Land), jadi tanggal = valid_time - 1 hari.
          Sel 0,25 derajat = rata-rata sel 0,1 derajat yang pusatnya jatuh di dalamnya;
          pusat sel = kelipatan 0,25 + 0,125.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd

import config
from common import done, iter_months, log, setup_logging

SHORT = {  # nama pendek NetCDF CDS baru -> nama internal
    "t2m": "t2m", "d2m": "d2m", "u10": "u10", "v10": "v10",
    "swvl1": "swvl1", "swvl4": "swvl4", "tp": "tp", "ssrd": "ssrd", "pev": "pev",
}


def time_name(ds) -> str:
    for n in ("valid_time", "time"):
        if n in ds.coords or n in ds.dims:
            return n
    raise KeyError("koordinat waktu tidak ditemukan")


def rh_from_t_td(t_k: np.ndarray, td_k: np.ndarray) -> np.ndarray:
    """Kelembapan relatif (%) dari suhu & titik embun (Kelvin), rumus Magnus."""
    t, td = t_k - 273.15, td_k - 273.15
    a, b = 17.625, 243.04
    rh = 100 * np.exp(a * td / (b + td)) / np.exp(a * t / (b + t))
    return np.clip(rh, 0, 100)


def es_kpa(t_c: np.ndarray) -> np.ndarray:
    """Tekanan uap jenuh (kPa) dari suhu (derajat C). Rumus Magnus (Allen dkk. 1998)."""
    return 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))


def vpd_from_t_td(t_k: np.ndarray, td_k: np.ndarray) -> np.ndarray:
    """VPD (kPa) = es(T) - es(Td), dari suhu & titik embun (Kelvin).

    VPD adalah prediktor cuaca-api terpenting setelah angin: ia menyatakan
    seberapa besar "permintaan" atmosfer terhadap air, dan menggerakkan
    pengeringan bahan bakar. Dipotong di 0 karena Td > T hanya muncul dari
    galat interpolasi.
    """
    vpd = es_kpa(t_k - 273.15) - es_kpa(td_k - 273.15)
    return np.maximum(vpd, 0.0)


def cell_center(v: np.ndarray, step: float = 0.25) -> np.ndarray:
    return np.floor(v / step) * step + step / 2


def instant_daily(ds) -> pd.DataFrame:
    tn = time_name(ds)
    df = ds.to_dataframe().reset_index()
    df = df.rename(columns={tn: "time"})
    for need in ("t2m", "d2m", "u10", "v10"):
        if need not in df:
            raise KeyError(f"variabel {need} tidak ada; ada: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["time"]).dt.floor("D")
    df["rh"] = rh_from_t_td(df["t2m"].to_numpy(), df["d2m"].to_numpy())
    df["vpd"] = vpd_from_t_td(df["t2m"].to_numpy(), df["d2m"].to_numpy())
    df["wind"] = np.hypot(df["u10"], df["v10"])
    df["lat_c"] = cell_center(df["latitude"].to_numpy())
    df["lon_c"] = cell_center(df["longitude"].to_numpy())
    keys = ["date", "lat_c", "lon_c"]
    # 1) agregasi spasial per langkah waktu, 2) agregasi harian
    step = df.groupby(keys + ["time"], as_index=False).mean(numeric_only=True)
    g = step.groupby(keys)
    out = pd.DataFrame({
        "t2m_mean": g["t2m"].mean() - 273.15, "t2m_max": g["t2m"].max() - 273.15,
        "t2m_min": g["t2m"].min() - 273.15,
        "rh_mean": g["rh"].mean(), "rh_min": g["rh"].min(),
        "wind_mean": g["wind"].mean(), "wind_max": g["wind"].max(),
        # Arah angin disimpan sebagai KOMPONEN u/v mentah, bukan sudut 0-360 derajat,
        # supaya transport asap bisa dihitung. Alasannya nyata: kabut 2026 menyeberang
        # Selat Malaka, jadi arah angin menentukan siapa yang terkena.
        "u10_mean": g["u10"].mean(), "v10_mean": g["v10"].mean(),
        "vpd_mean": g["vpd"].mean(), "vpd_max": g["vpd"].max(),
    })
    for v in ("swvl1", "swvl4"):
        if v in step:
            out[f"{v}_mean"] = g[v].mean()
    return out.reset_index()


def accum_daily(ds) -> pd.DataFrame:
    tn = time_name(ds)
    df = ds.to_dataframe().reset_index().rename(columns={tn: "time"})
    df["date"] = pd.to_datetime(df["time"]).dt.floor("D") - pd.Timedelta(days=1)
    df["lat_c"] = cell_center(df["latitude"].to_numpy())
    df["lon_c"] = cell_center(df["longitude"].to_numpy())
    g = df.groupby(["date", "lat_c", "lon_c"])
    out = pd.DataFrame(index=g.size().index)
    if "tp" in df:
        out["precip_mm"] = g["tp"].mean() * 1000.0
    if "ssrd" in df:
        out["ssrd_mjm2"] = g["ssrd"].mean() / 1e6
    if "pev" in df:
        out["pev_mm"] = -g["pev"].mean() * 1000.0     # negatif = penguapan
    return out.reset_index()


def _month_bounds(year: int, month: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    first = pd.Timestamp(year, month, 1)
    return first, first + pd.offsets.MonthEnd(0)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def process_month(year: int, month: int) -> bool:
    """Tulis parquet satu bulan penuh (hanya tanggal bulan itu).

    PENTING: nilai akumulasi (tp, ssrd, pev) pada 00:00 UTC tanggal 1 bulan BERIKUTNYA
    adalah total untuk hari terakhir bulan ini. Karena itu berkas accum bulan depan
    dibuka juga; tanpa itu hari terakhir setiap bulan kehilangan hujan, radiasi, dan PET.
    Kehilangan itu tidak kecil: `hujan_7h/14h/30h` memakai min_periods=jendela penuh,
    jadi satu nilai kosong membuat fitur hujan NaN sampai 30 hari ke depan.
    """
    import xarray as xr

    src_i = config.RAW / "era5land" / "instant" / f"{year}-{month:02d}.nc"
    src_a = config.RAW / "era5land" / "accum" / f"{year}-{month:02d}.nc"
    ny, nm = _next_month(year, month)
    src_a_next = config.RAW / "era5land" / "accum" / f"{ny}-{nm:02d}.nc"
    dest = config.PROCESSED / "era5_daily" / f"{year}-{month:02d}.parquet"
    # Bulan ini butuh berkas accum bulan BERIKUTNYA untuk melengkapi hari terakhirnya.
    # Cek kesegaran: kalau accum bulan berikutnya lebih baru dari parquet kita, parquet itu
    # pasti dibuat sebelum berkas tersebut ada, jadi hari terakhirnya masih kosong -> tulis ulang.
    # (Mengandalkan keberadaan berkas saja SALAH: parquet lama bisa dibuat saat berkas itu
    # belum ada, lalu dianggap selesai setelah berkas itu muncul.)
    if done(dest):
        if done(src_a_next) and dest.stat().st_mtime < src_a_next.stat().st_mtime:
            log.info("tulis ulang %d-%02d: accum bulan berikutnya lebih baru", year, month)
        else:
            return True
    if not (done(src_i) and done(src_a)):
        log.warning("lewati %d-%02d: file mentah belum lengkap", year, month)
        return False

    first, last = _month_bounds(year, month)

    with xr.open_dataset(src_i) as di:
        a = instant_daily(di)
    with xr.open_dataset(src_a) as da:
        b = accum_daily(da)
    if done(src_a_next):
        with xr.open_dataset(src_a_next) as dan:
            bn = accum_daily(dan)
        b = pd.concat([b, bn[bn["date"] == last]], ignore_index=True)
    else:
        log.warning("%d-%02d: accum bulan berikutnya belum ada; hari terakhir (%s) "
                    "kehilangan hujan/radiasi/PET -- jalankan ulang setelah crawl lanjut",
                    year, month, last.date())

    # Hanya tanggal milik bulan ini. Tanpa ini, hari "leak-back" (tanggal terakhir bulan
    # sebelumnya, yang cuma punya kolom akumulasi) ikut terbawa dan muncul di dua berkas.
    a = a[(a["date"] >= first) & (a["date"] <= last)]
    b = b[(b["date"] >= first) & (b["date"] <= last)]

    merged = a.merge(b, on=["date", "lat_c", "lon_c"], how="outer") \
        .sort_values(["date", "lat_c", "lon_c"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(dest, index=False)
    log.info("tulis %s (%d baris, %d hari)", dest, len(merged), merged["date"].nunique())
    return True


def parse_ym(s: str) -> date:
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=parse_ym, default=config.START)
    ap.add_argument("--to", dest="end", type=parse_ym, default=config.END)
    args = ap.parse_args(argv)
    setup_logging("postprocess")
    n_ok = sum(process_month(y, m) for y, m in iter_months(args.start, args.end))
    log.info("selesai: %d bulan terproses", n_ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Fitur turunan harian dari tabel cuaca (TODO #16).

    python build_derived_features.py                    # semua bulan
    python build_derived_features.py --from 2015-01 --to 2015-12
    python build_derived_features.py --lag 1 --no-spi

Masukan
    data/processed/era5_daily/YYYY-MM.parquet   (dari postprocess_era5.py)
    data/static/climate_index/{nino34,dmi}.csv  (dari crawl_static.py enso)
Keluaran
    data/processed/features_daily/YYYY-MM.parquet

ATURAN ANTI-BOCOR (bagian 7.2 dokumen): fitur untuk tanggal T hanya boleh memakai
data sampai T-LAG. Baris untuk tanggal T memuat cuaca mentah hari T (dipakai untuk
nowcasting) tetapi SELURUH kolom turunan sudah digeser `lag` hari, jadi turunannya
berasal dari <= T-LAG. Uji di test_derived.py membuktikan ini dengan mengubah data
hari >= T dan memastikan fitur hari T tidak berubah.

Kolom turunan
    hujan_3h/7h/14h/30h   total hujan berjalan (mm), jendela penuh saja
    kering_beruntun       jumlah hari beruntun dengan hujan < DRY_MM, berakhir di T-1
    <kolom>_anom          selisih dari klimatologi bulanan sel (t2m, rh, vpd, hujan)
    spi_30, spi_90        SPI empiris (kuantil-normal dari total berjalan)
    nino34, dmi, *_lag1..3  indeks iklim bulanan + lag
    bulan, hari_dalam_tahun, musim_kemarau   fitur kalender

CATATAN SPI: yang dipakai di sini adalah SPI EMPIRIS (peringkat -> kuantil normal),
bukan SPI gamma klasik. Alasannya: hujan Indonesia banyak bernilai nol sehingga
pemasangan gamma sering gagal/bergerigi, sedangkan transformasi peringkat kokoh dan
tidak butuh pustaka tambahan. Kalau nanti tim mau SPI gamma, ganti `empirical_spi`
dengan pustaka `climate-indices` -- kolom keluaran tidak perlu berubah.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd

import config
from common import iter_months, log, setup_logging

LAG = 1                     # hari: fitur turunan digeser sebanyak ini
DRY_MM = 1.0                # ambang hari kering (mm)
RAIN_WINDOWS = (3, 7, 14, 30)
SPI_WINDOWS = (30, 90)
ANOM_COLS = ("t2m_mean", "rh_mean", "vpd_max", "precip_mm")
CLIMATE_NAMES = ("nino34", "dmi")

# Kolom cuaca yang dibaca dari era5_daily (bukan seluruh kolom, supaya hemat memori).
WEATHER_COLS = [
    "date", "lat_c", "lon_c",
    "precip_mm", "t2m_mean", "rh_mean", "rh_min", "vpd_mean", "vpd_max",
    "u10_mean", "v10_mean", "swvl1_mean", "swvl4_mean", "ssrd_mjm2", "pev_mm",
]

DERIVED_COLS = (
    [f"hujan_{k}h" for k in RAIN_WINDOWS]
    + ["kering_beruntun"]
    + [f"{c}_anom" for c in ANOM_COLS]
    + [f"spi_{k}" for k in SPI_WINDOWS]
)


# ------------------------------------------------------------------ fungsi murni
def dry_streak(dry: pd.Series) -> pd.Series:
    """Panjang rentetan `dry` yang BERAKHIR di tiap posisi (inklusif).

    Dipakai lewat .transform() per sel, jadi indeks masukan dipertahankan.
    Contoh: T F T T T -> 1 0 1 2 3

    Vektor: untuk tiap posisi, jaraknya ke hari BASAH terakhir (atau -1 bila belum ada).
    """
    is_dry = dry.fillna(False).to_numpy(dtype=bool)
    idx = np.arange(len(is_dry))
    last_wet = np.maximum.accumulate(np.where(~is_dry, idx, -1))
    return pd.Series(np.where(is_dry, idx - last_wet, 0).astype("float32"), index=dry.index)


def empirical_spi(x) -> np.ndarray:
    """SPI empiris: peringkat nilai -> kuantil normal standar (mean 0, sd 1).

    Nilai NaN dibiarkan NaN. Butuh minimal 10 nilai sah; kalau kurang, semua NaN.
    """
    from scipy.stats import norm

    a = np.asarray(x, dtype="float64")
    out = np.full(a.shape, np.nan, dtype="float32")
    ok = np.isfinite(a)
    n = int(ok.sum())
    if n < 10:
        return out
    r = pd.Series(a[ok]).rank(method="average").to_numpy()
    p = (r - 0.5) / n
    p = np.clip(p, 1e-6, 1.0 - 1e-6)
    out[ok] = norm.ppf(p)
    return out


def month_ends(start: date, end: date) -> list[tuple[int, int]]:
    return list(iter_months(start, end))


# ---------------------------------------------------------------------- masukan
def load_weather(start: date, end: date) -> pd.DataFrame:
    src = config.PROCESSED / "era5_daily"
    files = [src / f"{y}-{m:02d}.parquet" for y, m in month_ends(start, end)]
    ada = [p for p in files if p.exists()]
    if not ada:
        return pd.DataFrame(columns=WEATHER_COLS)
    if len(ada) < len(files):
        log.warning("hanya %d dari %d bulan era5_daily yang ada", len(ada), len(files))
    frames = []
    for p in ada:
        d = pd.read_parquet(p)
        kolom = [c for c in WEATHER_COLS if c in d.columns]
        frames.append(d[kolom])
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_climate() -> pd.DataFrame:
    """Indeks iklim bulanan + lag 1..3 bulan. Kosong bila berkas belum ada."""
    frames = []
    for name in CLIMATE_NAMES:
        p = config.STATIC / "climate_index" / f"{name}.csv"
        if not p.exists():
            log.warning("indeks iklim belum ada: %s", p)
            continue
        d = pd.read_csv(p)
        if name not in d.columns or "year" not in d.columns or "month" not in d.columns:
            log.warning("format %s tidak sesuai (butuh year,month,%s): %s", name, name, list(d.columns))
            continue
        frames.append(d[["year", "month", name]].rename(columns={"year": "y", "month": "m"}))
    if not frames:
        return pd.DataFrame(columns=["y", "m"])
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=["y", "m"], how="outer")
    out = out.sort_values(["y", "m"]).reset_index(drop=True)
    for name in CLIMATE_NAMES:
        if name in out.columns:
            for k in (1, 2, 3):
                out[f"{name}_lag{k}"] = out[name].shift(k)
    return out


# -------------------------------------------------------------------- pembentukan
def build(df: pd.DataFrame, climate: pd.DataFrame, lag: int = LAG,
          with_spi: bool = True) -> pd.DataFrame:
    df = df.sort_values(["lat_c", "lon_c", "date"]).reset_index(drop=True)
    cells = ["lat_c", "lon_c"]
    g = df.groupby(cells, sort=False)

    # Kalender: diketahui sebelum hari T, jadi TIDAK perlu digeser.
    df["bulan"] = df["date"].dt.month.astype("int8")
    df["hari_dalam_tahun"] = df["date"].dt.dayofyear.astype("int16")
    # Musim kemarau: heuristik puncak kabut asap (Jul-Okt). Perlu ditinjau per wilayah,
    # karena Sumatera bagian utara punya pola kering yang berbeda.
    df["musim_kemarau"] = df["bulan"].isin([7, 8, 9, 10]).astype("int8")

    # Hujan berjalan: jendela penuh saja (min_periods=k) supaya awal rekaman NaN,
    # bukan angka setengah jendela yang menyesatkan.
    for k in RAIN_WINDOWS:
        df[f"hujan_{k}h"] = g["precip_mm"].transform(
            lambda s, k=k: s.rolling(k, min_periods=k).sum())

    # Rentetan hari kering, "berakhir di hari D"
    df["kering_beruntun"] = g["precip_mm"].transform(lambda s: dry_streak(s < DRY_MM))

    # Anomali terhadap klimatologi bulanan sel (dihitung dari seluruh rekaman)
    for col in ANOM_COLS:
        if col not in df.columns:
            continue
        clim = df.groupby(cells + ["bulan"])[col].transform("mean")
        df[f"{col}_anom"] = (df[col] - clim).astype("float32")

    # SPI empiris dari total berjalan
    if with_spi:
        for k in SPI_WINDOWS:
            tot = g["precip_mm"].transform(
                lambda s, k=k: s.rolling(k, min_periods=k).sum())
            df[f"spi_{k}"] = tot.groupby([df["lat_c"], df["lon_c"]], sort=False).transform(empirical_spi)

    # --- ANTI-BOCOR: geser SELURUH kolom turunan sebanyak `lag` hari per sel
    g2 = df.groupby(cells, sort=False)
    for col in DERIVED_COLS:
        if col in df.columns:
            df[col] = g2[col].shift(lag)

    # Indeks iklim bulanan (dipakai apa adanya; lag-nya sudah dari bulan, bukan hari)
    df["y"] = df["date"].dt.year.astype("int16")
    df["m"] = df["date"].dt.month.astype("int8")
    if not climate.empty:
        df = df.merge(climate, on=["y", "m"], how="left")
    return df.drop(columns=["y", "m"])


def process(start: date, end: date) -> int:
    df = load_weather(start, end)
    if df.empty:
        log.error("tidak ada data era5_daily pada rentang ini; jalankan postprocess_era5.py dulu")
        return 0
    log.info("memuat %d baris cuaca (%s s/d %s)", len(df), df["date"].min().date(), df["date"].max().date())

    climate = load_climate()
    if climate.empty:
        log.warning("tanpa indeks iklim: kolom nino34/dmi akan absen")

    out = build(df, climate)
    dest_dir = config.PROCESSED / "features_daily"
    dest_dir.mkdir(parents=True, exist_ok=True)
    n_tulis = 0
    for (y, m) in month_ends(start, end):
        part = out[(out["date"].dt.year == y) & (out["date"].dt.month == m)]
        if part.empty:
            continue
        dest = dest_dir / f"{y}-{m:02d}.parquet"
        part.to_parquet(dest, index=False)
        n_tulis += 1
    log.info("tulis %d berkas ke %s", n_tulis, dest_dir)
    return n_tulis


def parse_ym(s: str) -> date:
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=parse_ym, default=config.START)
    ap.add_argument("--to", dest="end", type=parse_ym, default=config.END)
    ap.add_argument("--lag", type=int, default=LAG, help="geser fitur turunan (hari), default 1")
    ap.add_argument("--no-spi", action="store_true", help="lewati SPI (lebih cepat)")
    args = ap.parse_args(argv)
    setup_logging("features")
    n = process(args.start, args.end)
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())

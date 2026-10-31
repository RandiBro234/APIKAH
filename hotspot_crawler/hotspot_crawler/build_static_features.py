"""Agregasi lapisan statis ke grid 0,25 derajat (TODO #8 dan #15).

    python build_static_features.py                       # semua lapisan raster yang ada
    python build_static_features.py --only dem,hansen
    python build_static_features.py --resolution-deg 0.005   # lebih kasar, lebih cepat
    python build_static_features.py --only osm               # terpisah, lihat catatan OSM

Masukan (dari crawl_static.py)
    data/static/dem/*.tif            Copernicus DEM 30 m      -> elevasi_mean/max, slope_mean/max
    data/static/worldcover/*.tif     ESA WorldCover 10 m 2021 -> wc_<kelas> fraksi
    data/static/hansen/*.tif         Hansen treecover2000 + lossyear
                                                              -> treecover2000_mean, loss_frac_{1,3,5}y
    data/static/worldpop/*.tif       WorldPop 1 km            -> pop_density_mean/sum
    data/static/peatlands/*.tif      peta gambut (manual)     -> peat_fraksi
    data/static/osm/*.osm.pbf        Geofabrik                -> jarak_jalan_m, jarak_sungai_m (opt-in)
Keluaran
    data/processed/static_features.parquet   satu baris per (lat_c, lon_c)

Konvensi sel SAMA dengan grid label dan era5: pusat sel = n*0,25 + 0,125.

Prinsip hemat memori: raster besar TIDAK pernah dibaca penuh. `read_decimated` memakai
`out_shape` supaya rasterio sendiri yang menurunkan resolusi (Hansen 10 derajat @30 m =
120.000 x 120.000 piksel -> disaring dulu), lalu tiap piksel dipetakan ke sel 0,25
derajatnya dan diringkas dengan `np.bincount`.

CATATAN OSM: .osm.pbf tidak bisa dibaca geopandas tanpa driver OSM dari GDAL
(pyogrio). Karena itu `osm` TIDAK ikut di jalur default: jalankan `--only osm` bila
sudah yakin pembacanya ada. Inti perhitungan jaraknya (`distance_to_features`) terpisah
dan sudah diuji, jadi begitu .pbf terbaca, sisanya tinggal tersambung.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import config
from common import log, setup_logging

STEP = 0.25                     # derajat, konvensi sel bersama dengan label
RES_DEFAULT = 0.0025            # derajat, resolusi kerja ~250 m
METERS_PER_DEG = 111_320.0

# Kelas ESA WorldCover v200
WORLDCOVER = {10: "pohon", 20: "semak", 30: "rumput", 40: "tanaman", 50: "terbangun",
              60: "gundul", 70: "salju", 80: "air", 90: "lahan_basah", 95: "mangrove",
              100: "lumut"}

LAYERS = ("dem", "worldcover", "hansen", "worldpop", "peat")
OPTIONAL_LAYERS = ("osm",)

# Nama lapisan -> nama folder di data/static/.
# PENTING: `peat` disimpan crawl_static.py di folder "peatlands", bukan "peat".
# Tanpa peta ini, lapisan gambut tidak akan pernah ditemukan (bug tertangkap uji smoke).
DIRS = {"dem": "dem", "worldcover": "worldcover", "hansen": "hansen",
        "worldpop": "worldpop", "peat": "peatlands", "osm": "osm"}

HANSEN_NAME = re.compile(r"_(treecover2000|lossyear)_(\d{2}[NS])_(\d{3}[EW])\.tiff?$", re.I)


# ------------------------------------------------------------------ fungsi murni
def decimation_for(pixel_deg: float, res_deg: float = RES_DEFAULT) -> int:
    """Faktor penurunan resolusi agar satu piksel kerja mendekati `res_deg` derajat."""
    if pixel_deg <= 0:
        return 1
    return max(1, int(round(res_deg / pixel_deg)))


def cell_index_of(lat, lon, step: float = STEP):
    """Indeks sel (baris dari utara, kolom dari barat) untuk koordinat apa pun.

    Pusat sel = n*0,25 + 0,125, jadi indeksnya n = floor(koordinat / 0,25).
    """
    r = np.floor(np.asarray(lat, dtype="float64") / step).astype("int64")
    c = np.floor(np.asarray(lon, dtype="float64") / step).astype("int64")
    return r, c


def cell_ids(row_idx, col_idx):
    """Ubah indeks sel 2-D jadi id datar padat (untuk bincount).

    Kembalikan (id, (r0, c0, n_lat, n_lon)) supaya penyusun bisa mengembalikan
    pusat sel dengan urutan yang sama.
    """
    r = np.asarray(row_idx, dtype="int64")
    c = np.asarray(col_idx, dtype="int64")
    r0, c0 = int(r.min()), int(c.min())
    n_lat = int(r.max()) - r0 + 1
    n_lon = int(c.max()) - c0 + 1
    return (r - r0) * n_lon + (c - c0), (r0, c0, n_lat, n_lon)


def aggregate(values, ids, n_ids: int, how: str = "mean") -> np.ndarray:
    """Ringkas nilai piksel per id. Nilai non-finite dibuang lebih dulu."""
    v = np.asarray(values, dtype="float64").ravel()
    i = np.asarray(ids, dtype="int64").ravel()
    ok = np.isfinite(v)
    v, i = v[ok], i[ok]
    if how == "mean":
        s = np.bincount(i, weights=v, minlength=n_ids)
        n = np.bincount(i, minlength=n_ids)
        return np.divide(s, n, out=np.full(n_ids, np.nan), where=n > 0)
    if how == "sum":
        s = np.bincount(i, weights=v, minlength=n_ids)
        s[np.bincount(i, minlength=n_ids) == 0] = np.nan
        return s
    if how == "max":
        out = np.full(n_ids, -np.inf)
        np.maximum.at(out, i, v)
        out[~np.isfinite(out)] = np.nan
        return out
    if how == "min":
        out = np.full(n_ids, np.inf)
        np.minimum.at(out, i, v)
        out[~np.isfinite(out)] = np.nan
        return out
    raise ValueError(f"agregasi tidak dikenal: {how}")


def class_fractions(values, ids, n_ids: int, classes) -> dict:
    """Fraksi tiap kelas. Kode < 0 (nodata) dibuang, jadi penyebut = piksel sah saja."""
    v = np.asarray(values).ravel()
    i = np.asarray(ids, dtype="int64").ravel()
    sah = (v.astype("float64") > -0.5) & np.isfinite(v.astype("float64"))
    v, i = v[sah], i[sah]
    total = np.bincount(i, minlength=n_ids).astype("float64")
    total[total == 0] = np.nan
    return {k: np.bincount(i[v == k], minlength=n_ids).astype("float64") / total
            for k in classes}


def slope_degrees(elev, dy_m: float, dx_m_by_row) -> np.ndarray:
    """Kemiringan (derajat) dari matriks elevasi.

    `dx_m_by_row` mengecil mendekati kutub, jadi tiap baris punya faktor skalanya sendiri.
    """
    arr = np.asarray(elev, dtype="float64")
    dz_dy, dz_dx = np.gradient(arr)
    dz_dy = dz_dy / float(dy_m)
    dz_dx = dz_dx / np.asarray(dx_m_by_row, dtype="float64")[:, None]
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))


def distance_to_features(mask: np.ndarray, res_deg: float, row_lat) -> np.ndarray:
    """Jarak tiap piksel ke fitur terdekat (meter). `mask` True = ada fitur.

    Jaraknya METRIK: indeks piksel fitur terdekat dikembalikan transformasi jarak,
    lalu selisihnya dikalikan ukuran piksel dalam meter (dx menyesuaikan lintang).
    Jadi diagonal tidak dihitung sebagai dua kali jarak.
    """
    from scipy import ndimage

    m = np.asarray(mask, dtype=bool)
    dist, (ir, ic) = ndimage.distance_transform_edt(~m, return_indices=True)
    h, w = m.shape
    dy_m = res_deg * METERS_PER_DEG
    dx_row = dy_m * np.cos(np.radians(np.asarray(row_lat, dtype="float64")))
    dy = (ir - np.arange(h)[:, None]) * dy_m
    dx = (ic - np.arange(w)[None, :]) * dx_row[:, None]
    return np.hypot(dy, dx)


# ---------------------------------------------------------------- pembaca raster
def read_decimated(path: Path, res_deg: float = RES_DEFAULT, categorical: bool = False,
                   bbox: tuple[float, float, float, float] | None = None):
    """Baca band pertama pada resolusi diturunkan. Kembalikan (data, transform).

    Kategorikal -> resampling "mode" (kelas tidak boleh dirata-rata), dan nodata
    dipetakan ke -1. Kontinu -> resampling "average", nodata dipetakan ke NaN.

    `bbox` = (barat, selatan, timur, utara) membatasi bacaan ke wilayah itu. Penting untuk
    raster GLOBAL seperti peta gambut (43.200 x 18.285 piksel): tanpa pembatasan, satu
    lapisan saja bisa memakan ratusan MB--GB padahal yang dipakai cuma Indonesia.
    bbox=None harus berperilaku PERSIS seperti sebelumnya.
    """
    import rasterio
    from rasterio import Affine
    from rasterio.enums import Resampling

    with rasterio.open(path) as src:
        if src.count < 1 or src.width < 1 or src.height < 1:
            raise ValueError(f"raster kosong: {path}")
        kwargs = {}
        win_w, win_h, base_t = src.width, src.height, src.transform
        if bbox is not None:
            from rasterio.windows import from_bounds
            # Pangkas bbox ke batas raster. Tanpa ini, bbox yang lebih luas dari raster
            # (mis. uji dengan raster 0,25 derajat) akan minta jendela raksasa berisi
            # piksel kosong -- lambat, boros memori, dan hasilnya menyesatkan.
            bb = src.bounds
            w, e = max(bbox[0], bb.left), min(bbox[2], bb.right)
            s, n = max(bbox[1], bb.bottom), min(bbox[3], bb.top)
            if not (w < e and s < n):
                raise ValueError(f"bbox {bbox} tidak beririsan dengan raster {path.name}")
            win = from_bounds(w, s, e, n, src.transform)
            win = win.round_offsets().round_lengths()
            if win.width < 1 or win.height < 1:
                raise ValueError(f"bbox {bbox} tidak menyentuh raster {path.name}")
            kwargs["window"] = win
            base_t = src.window_transform(win)
            win_w, win_h = int(win.width), int(win.height)
        k = decimation_for(abs(base_t.a), res_deg)
        out_h = max(1, win_h // k)
        out_w = max(1, win_w // k)
        band = src.read(1, out_shape=(out_h, out_w),
                        resampling=Resampling.mode if categorical else Resampling.average,
                        **kwargs)
        sx, sy = win_w / out_w, win_h / out_h
        tr = Affine(base_t.a * sx, base_t.b, base_t.c, base_t.d, base_t.e * sy, base_t.f)
        nodata = src.nodata
    band = np.asarray(band, dtype="float64")
    if nodata is not None:
        band = np.where(band == nodata, -1.0 if categorical else np.nan, band)
    return band, tr


def grid_of(tr, shape, step: float = STEP):
    """Petakan grid raster ke sel 0,25 derajat.

    Kembalikan (ids, n_ids, lat_c, lon_c, lat_axis, lon_axis); urutan lat_c/lon_c
    sejajar dengan ids 0..n_ids-1.
    """
    h, w = shape
    lat = tr.f + (np.arange(h) + 0.5) * tr.e
    lon = tr.c + (np.arange(w) + 0.5) * tr.a
    lat_grid, lon_grid = np.meshgrid(lat, lon, indexing="ij")
    ids, (r0, c0, n_lat, n_lon) = cell_ids(*cell_index_of(lat_grid, lon_grid, step))
    n_ids = n_lat * n_lon
    rr, cc = np.meshgrid(np.arange(r0, r0 + n_lat), np.arange(c0, c0 + n_lon), indexing="ij")
    return (ids.ravel(), n_ids,
            (rr * step + step / 2).ravel(), (cc * step + step / 2).ravel(),
            lat, lon)


def tiles(layer: str, ext=(".tif", ".tiff")) -> list[Path]:
    folder = config.STATIC / DIRS.get(layer, layer)
    if not folder.exists():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in ext)


def hansen_pairs() -> dict:
    """Pasangkan treecover2000 & lossyear per TILE (kunci dari nama berkas, bukan folder).

    Penting: berkas bernama `Hansen_<ver>_<layer>_<lat><NS>_<lon><EW>.tif`, jadi kunci
    tile diambil dari lat/lon di nama berkas. Mengelompokkan per folder akan salah:
    semua tile berada di satu folder.
    """
    out: dict[tuple[str, str], dict[Path, str]] = {}
    for p in tiles("hansen"):
        m = HANSEN_NAME.search(p.name)
        if not m:
            log.warning("nama berkas Hansen tidak dikenali, dilewati: %s", p.name)
            continue
        layer, lat, lon = m.group(1).lower(), m.group(2).upper(), m.group(3).upper()
        out.setdefault((lat, lon), {})[layer] = p
    return out


# --------------------------------------------------------------------- lapisan
def build_dem(res_deg: float) -> pd.DataFrame:
    frames = []
    for p in tiles("dem"):
        band, tr = read_decimated(p, res_deg, categorical=False)
        ids, n_ids, lat_c, lon_c, lat, _ = grid_of(tr, band.shape)
        dy_m = abs(tr.e) * METERS_PER_DEG
        dx_row = abs(tr.a) * METERS_PER_DEG * np.cos(np.radians(lat))
        sl = slope_degrees(band, dy_m, dx_row)
        frames.append(pd.DataFrame({
            "lat_c": lat_c, "lon_c": lon_c,
            "elevasi_mean": aggregate(band, ids, n_ids, "mean"),
            "elevasi_max": aggregate(band, ids, n_ids, "max"),
            "slope_mean": aggregate(sl, ids, n_ids, "mean"),
            "slope_max": aggregate(sl, ids, n_ids, "max"),
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_worldcover(res_deg: float) -> pd.DataFrame:
    frames = []
    for p in tiles("worldcover"):
        band, tr = read_decimated(p, res_deg, categorical=True)
        ids, n_ids, lat_c, lon_c, _, _ = grid_of(tr, band.shape)
        frac = class_fractions(band, ids, n_ids, WORLDCOVER.keys())
        frames.append(pd.DataFrame({"lat_c": lat_c, "lon_c": lon_c,
                                    **{f"wc_{n}": frac[k] for k, n in WORLDCOVER.items()}}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_hansen(res_deg: float, lag_years: tuple[int, ...] = (1, 3, 5)) -> pd.DataFrame:
    """treecover2000 (rata-rata) + fraksi area terbuka-hutan dalam 1/3/5 tahun terakhir.

    `lossyear` berisi tahun-2000 (1 = 2001, ..., 25 = 2025). Karena itu nilainya
    di-LAG relatif ke `config.HANSEN_LOSS_REF_YEAR` (bagian 7.3) supaya tidak bocor
    ke masa depan: untuk fitur tahun T hanya dipakai kehilangan sampai T-1.
    """
    frames = []
    for kunci, berkas in hansen_pairs().items():
        if "treecover2000" not in berkas:
            log.warning("tile Hansen %s tanpa treecover2000, dilewati", kunci)
            continue
        band, tr = read_decimated(berkas["treecover2000"], res_deg, categorical=False)
        ids, n_ids, lat_c, lon_c, _, _ = grid_of(tr, band.shape)
        d = {"lat_c": lat_c, "lon_c": lon_c,
             "treecover2000_mean": aggregate(band, ids, n_ids, "mean")}
        if "lossyear" in berkas:
            ly, tr2 = read_decimated(berkas["lossyear"], res_deg, categorical=True)
            if ly.shape == band.shape:
                for lag in lag_years:
                    th = config.HANSEN_LOSS_REF_YEAR - lag
                    d[f"loss_frac_{lag}y"] = aggregate(
                        (ly == (th - 2000)).astype("float64"), ids, n_ids, "mean")
            else:
                log.warning("tile Hansen %s: bentuk lossyear != treecover, dilewati", kunci)
        frames.append(pd.DataFrame(d))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_worldpop(res_deg: float) -> pd.DataFrame:
    frames = []
    for p in tiles("worldpop"):
        band, tr = read_decimated(p, res_deg, categorical=False)
        ids, n_ids, lat_c, lon_c, _, _ = grid_of(tr, band.shape)
        frames.append(pd.DataFrame({
            "lat_c": lat_c, "lon_c": lon_c,
            "pop_density_mean": aggregate(band, ids, n_ids, "mean"),
            "pop_density_sum": aggregate(band, ids, n_ids, "sum"),
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


PEAT_ROLES = {                      # peran -> nama berkas di data/static/peatlands/
    "extent": "peat_extent_1km_2000_2020.tif",
    "thickness": "peat_thickness_1km_2000_2020.tif",
    "carbon": "peat_carbon_1km_2000_2020.tif",
}
FINE_STEP = 0.05                    # derajat (~5,5 km), grid untuk mengawinkan gambut x Hansen


PEAT_ROLE_KEYS = {                  # kata kunci untuk menebak peran dari NAMA berkas
    "extent": ("extent", "luas", "peatland", "gambut"),
    "thickness": ("thickness", "tebal", "depth"),
    "carbon": ("carbon", "soc", "karbon"),
}


def peat_berkas() -> dict[str, Path]:
    """Berkas gambut yang ada, dipetakan peran -> path. `extent` yang wajib.

    Nama baku (hasil `crawl_static.py peat`) diutamakan. Kalau berkasnya bernama lain --
    mis. peta gambut Indonesia dari WRI yang diunduh manual lalu dirasterisasi -- perannya
    ditebak dari kata kunci nama berkas dan pilihannya DICATAT di log, supaya tidak ada
    lapisan yang dipakai untuk peran yang salah tanpa disadari.
    """
    folder = config.STATIC / DIRS["peat"]
    if not folder.exists():
        return {}
    out = {peran: folder / nama for peran, nama in PEAT_ROLES.items() if (folder / nama).exists()}
    if "extent" in out:
        return out
    kandidat = sorted(p for p in folder.rglob("*")
                      if p.is_file() and p.suffix.lower() in (".tif", ".tiff"))
    for peran, kunci in PEAT_ROLE_KEYS.items():
        if peran in out:
            continue
        for p in kandidat:
            if any(k in p.name.lower() for k in kunci):
                out[peran] = p
                log.info("gambut '%s' <- %s (ditebak dari nama berkas)", peran, p.name)
                break
    if "extent" not in out and len(kandidat) == 1:
        out["extent"] = kandidat[0]
        log.info("gambut 'extent' <- %s (satu-satunya berkas .tif di folder)", kandidat[0].name)
    return out


def native_pixel_deg(path: Path) -> float:
    """Ukuran piksel ASLI (derajat).

    Dipakai untuk membaca peta gambut pada resolusi aslinya. Kalau dibaca lebih kasar,
    nilai probabilitasnya DIRATA-RATAKAN lebih dulu -- mis. piksel bernilai 1 dan 100
    bercampur menjadi 50, lalu gagal ambang `== 100`. Fraksi yang dihasilkan jadi salah.
    """
    import rasterio
    with rasterio.open(path) as src:
        return abs(src.transform.a)


def _fine_cells(path: Path, categorical: bool, step: float = FINE_STEP,
                res_deg: float | None = None,
                bbox: tuple[float, float, float, float] | None = None):
    """Baca raster, lalu kumpulkan pikselnya ke sel berukuran `step`.

    `res_deg` = sasaran resolusi SAAT MEMBACA; sengaja dipisah dari `step` (ukuran sel hasil).
    Menggabungkan keduanya berbahaya: pembacaan yang terlalu kasar merata-ratakan nilai
    sebelum diperiksa, sehingga ambang batas dan fraksi kehilangan hutan jadi keliru.
    """
    band, tr = read_decimated(path, res_deg if res_deg is not None else step,
                              categorical=categorical, bbox=bbox)
    ids, n_ids, lat_c, lon_c, _, _ = grid_of(tr, band.shape, step=step)
    return band, ids, n_ids, lat_c, lon_c


def _step_centers(info: tuple) -> tuple[np.ndarray, np.ndarray]:
    """Pusat sel (lat_c, lon_c) untuk sel-sel yang tercakup.

    `info` = (r0, c0, n_lat, n_lon) keluaran `cell_ids` -- BUKAN keluaran `cell_index_of`
    (yang berbentuk (r, c)). Tertukar di antara keduanya menghasilkan galat unpack.
    """
    r0, c0, n_lat, n_lon = info
    rr, cc = np.meshgrid(np.arange(r0, r0 + n_lat), np.arange(c0, c0 + n_lon), indexing="ij")
    return (rr * STEP + STEP / 2).ravel(), (cc * STEP + STEP / 2).ravel()


def build_peat(res_deg: float, lag_years: tuple[int, ...] = (1, 3, 5)) -> pd.DataFrame:
    """Fitur gambut: luas, ketebalan, karbon, dan deforestasi DI ATAS gambut.

    `extent` berisi PROBABILITAS 0-100: berapa dari 3 peta sumber (WRI/GFW, PEATGRIDS,
    Global Peatlands Map 2.0) yang menyebut piksel itu gambut. Karena itu ambangnya
    `config.PEAT_THRESHOLD` -- lihat komentar panjang di config.py. Memakai `> 0` SALAH:
    terukur menandai 98,6 juta ha (7x lipat literatur Indonesia).

    `thickness`/`carbon` dirata-ratakan HANYA di piksel gambut, jadi maknanya "tebal gambut
    di sel ini", bukan "tebal rata-rata seluruh sel".

    Deforestasi gambut DIKAWINKAN lebih dulu pada grid halus FINE_STEP (~5,5 km), baru
    dirata-ratakan ke sel 0,25 derajat. Mengalikan dua fraksi langsung di sel 0,25 derajat
    (25 km) menyimpang sistematis: kehilangan hutan di dalam satu sel tidak menyebar merata,
    ia memusat di bagian gambut yang sudah dibuka -- jadi hasilnya akan TERTEKAN.

    Gambut dan hutan itu DUA SUMBU BERBEDA (jenis tanah vs tutupan di atasnya). Yang
    menjawab "dampak kalau terbakar" adalah gabungannya, bukan salah satu saja.
    """
    berkas = peat_berkas()
    if "extent" not in berkas:
        log.warning("peta gambut tidak ada di %s -- jalankan: python crawl_static.py peat",
                    config.STATIC / DIRS["peat"])
        return pd.DataFrame()

    bbox = (config.AREA[1], config.AREA[2], config.AREA[3], config.AREA[0])  # W,S,E,N
    nat = native_pixel_deg(berkas["extent"])   # baca pada resolusi ASLI, jangan dirata-ratakan

    # ---- 1. kolom per sel 0,25 derajat -----------------------------------------------
    band, ids, n_ids, lat_c, lon_c = _fine_cells(berkas["extent"], False, STEP, nat, bbox)
    is_peat = np.isfinite(band) & (band >= config.PEAT_THRESHOLD)
    kasar = pd.DataFrame({"lat_c": lat_c, "lon_c": lon_c,
                          "peat_fraksi": aggregate(is_peat.astype("float64"), ids, n_ids, "mean")})
    log.info("gambut: %d piksel asli, %.1f%% di antaranya gambut (ambang %d)",
             band.size, 100 * float(is_peat.mean()), config.PEAT_THRESHOLD)

    for peran, kolom in (("thickness", "peat_thickness_mean"), ("carbon", "peat_carbon_mean")):
        if peran not in berkas:
            log.warning("lapisan gambut '%s' tidak ada -> kolom %s kosong", peran, kolom)
            continue
        b2, _, _, _, _ = _fine_cells(berkas[peran], False, STEP, nat, bbox)
        if b2.shape != band.shape:
            log.warning("bentuk %s (%s) != extent (%s); dilewati", peran, b2.shape, band.shape)
            continue
        kasar[kolom] = aggregate(np.where(is_peat, b2, np.nan), ids, n_ids, "mean")

    # ---- 2. deforestasi di atas gambut ------------------------------------------------
    halus = None
    for kunci, bk in hansen_pairs().items():
        if "lossyear" not in bk:
            log.warning("tile Hansen %s tanpa lossyear; dilewati untuk gambut", kunci)
            continue
        ly, ids2, n2, lat2, lon2 = _fine_cells(bk["lossyear"], True, FINE_STEP, res_deg)
        bagian = pd.DataFrame({"lat_c": lat2, "lon_c": lon2})
        for lag in lag_years:
            # `lossyear` menyimpan TAHUN - 2000 (1..25 = 2001..2025), bukan tahun penuh.
            # Lupa mengurangi 2000 membuat fitur ini SEMUANYA NOL tanpa error apa pun.
            th = config.HANSEN_LOSS_REF_YEAR - lag - 2000
            bagian[f"loss{lag}"] = aggregate((ly == th).astype("float64"), ids2, n2, "mean")
        halus = bagian if halus is None else pd.concat([halus, bagian], ignore_index=True)

    if halus is None:
        log.warning("Hansen lossyear tidak ada -> fitur deforestasi gambut dilewati")
        return kasar

    # Gabung tile yang bertumpang tindih, lalu kawinkan dengan lapisan gambut pada grid halus.
    halus = halus.groupby(["lat_c", "lon_c"], as_index=False).mean(numeric_only=True)
    pf, ids3, n3, lat3, lon3 = _fine_cells(berkas["extent"], False, FINE_STEP, nat, bbox)
    gambut_halus = pd.DataFrame({
        "lat_c": lat3, "lon_c": lon3,
        "peat_f": aggregate((np.isfinite(pf) & (pf >= config.PEAT_THRESHOLD)).astype("float64"),
                            ids3, n3, "mean")})
    m = gambut_halus.merge(halus, on=["lat_c", "lon_c"], how="inner")
    # JANGAN buang sel halus yang bukan gambut. Penyebutnya harus SELURUH sel, supaya
    # artinya tetap "bagian SEL yang gambut DAN kehilangan hutan" (langsung bisa dikali
    # luas sel). Kalau yang bukan gambut dibuang, artinya berubah menjadi "bagian dari
    # luas GAMBUT yang hilang" -- besaran yang berbeda, dan mudah tertukar.
    if m.empty:
        log.warning("tidak ada irisan gambut x lossyear; fitur deforestasi gambut dilewati")
        return kasar

    ids4_rc = cell_index_of(m["lat_c"].to_numpy(), m["lon_c"].to_numpy(), STEP)
    ids4, info4 = cell_ids(*ids4_rc)            # info4 = (r0, c0, n_lat, n_lon)
    n4 = info4[2] * info4[3]
    lat_o, lon_o = _step_centers(info4)
    halus_out = pd.DataFrame({"lat_c": lat_o, "lon_c": lon_o})
    for lag in lag_years:
        # rata-rata (bagian gambut x bagian yang hilang) di tiap sel 0,25 derajat
        halus_out[f"peat_loss_frac_{lag}y"] = aggregate(
            (m["peat_f"] * m[f"loss{lag}"]).to_numpy(), ids4, n4, "mean")
    log.info("  + %d kolom deforestasi gambut dari %d piksel halus", len(lag_years), len(m))
    return kasar.merge(halus_out, on=["lat_c", "lon_c"], how="outer")


def build_osm(res_deg: float, kelas: tuple[str, ...] = ("jalan", "sungai")) -> pd.DataFrame:
    """Jarak ke jalan/sungai dari .osm.pbf. Butuh driver OSM GDAL; lihat catatan modul."""
    import rasterio.features

    pbfs = sorted((config.STATIC / "osm").glob("*.osm.pbf"))
    if not pbfs:
        log.warning("tidak ada .osm.pbf di %s", config.STATIC / "osm")
        return pd.DataFrame()
    try:
        import geopandas as gpd
    except ImportError:
        log.error("geopandas tidak terpasang; `pip install geopandas`")
        return pd.DataFrame()

    n, w, s, e = config.AREA
    grid = 0.005                                  # ~550 m, cukup halus untuk jarak
    h = max(1, int(round((n - s) / grid)))
    ww = max(1, int(round((e - w) / grid)))
    tr = rasterio.transform.from_bounds(w, s, e, n, ww, h)
    row_lat = tr.f + (np.arange(h) + 0.5) * tr.e
    lon_ax = tr.c + (np.arange(ww) + 0.5) * tr.a
    ids, n_ids, lat_c, lon_c, _, _ = grid_of(tr, (h, ww))

    frames = []
    for p in pbfs:
        try:
            gdf = gpd.read_file(p, layer="lines")
        except Exception as exc:  # noqa: BLE001
            log.error("tidak bisa membaca %s (%s: %s). Perlu pyogrio/GDAL dengan driver OSM "
                      "-- lihat catatan modul.", p.name, type(exc).__name__, str(exc)[:120])
            return pd.DataFrame()
        d = {"lat_c": lat_c, "lon_c": lon_c}
        for nama, kolom in (("jalan", "highway"), ("sungai", "waterway")):
            if nama not in kelas or kolom not in gdf.columns:
                continue
            sub = gdf[gdf[kolom].notna()]
            if len(sub) == 0:
                continue
            mask = rasterio.features.rasterize(
                ((g, 1) for g in sub.geometry if g is not None),
                out_shape=(h, ww), transform=tr, fill=0, dtype="uint8")
            jarak = distance_to_features(mask, grid, row_lat).ravel()
            d[f"jarak_{nama}_m"] = aggregate(jarak, ids, n_ids, "mean")
            d[f"jarak_{nama}_min_m"] = aggregate(jarak, ids, n_ids, "min")
        if len(d) > 2:
            frames.append(pd.DataFrame(d))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


BUILDERS = {"dem": build_dem, "worldcover": build_worldcover, "hansen": build_hansen,
            "worldpop": build_worldpop, "peat": build_peat, "osm": build_osm}


# ------------------------------------------------------------------------ target
def target_cells() -> pd.DataFrame:
    """Grid sel 0,25 derajat acuan.

    Diambil dari era5_daily bila ada, supaya selnya PASTI sama dengan tabel cuaca
    (dan otomatis hanya sel darat). Kalau belum ada, dipakai seluruh bbox area.
    """
    src = config.PROCESSED / "era5_daily"
    files = sorted(src.glob("*.parquet"))
    if files:
        d = pd.read_parquet(files[0], columns=["lat_c", "lon_c"]).drop_duplicates()
        log.info("grid acuan dari %s (%d sel)", files[0].name, len(d))
        return d.sort_values(["lat_c", "lon_c"]).reset_index(drop=True)
    n, w, s, e = config.AREA
    lats = np.arange(np.floor(s / STEP) * STEP + STEP / 2, n, STEP)
    lons = np.arange(np.floor(w / STEP) * STEP + STEP / 2, e, STEP)
    log.warning("era5_daily belum ada; grid acuan dibuat dari bbox area (%d x %d sel)",
                len(lats), len(lons))
    return pd.DataFrame([(la, lo) for la in lats for lo in lons], columns=["lat_c", "lon_c"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default=",".join(LAYERS),
                    help=f"lapisan dipisah koma (tersedia: {','.join(LAYERS + OPTIONAL_LAYERS)})")
    ap.add_argument("--resolution-deg", type=float, default=RES_DEFAULT,
                    help="resolusi kerja dalam derajat (default 0.0025 = ~250 m)")
    ap.add_argument("--out", default=None, help="berkas keluaran parquet")
    args = ap.parse_args(argv)
    setup_logging("static_features")

    diminta = [s.strip() for s in args.only.split(",") if s.strip()]
    tidak_kenal = [s for s in diminta if s not in BUILDERS]
    if tidak_kenal:
        log.error("lapisan tidak dikenal: %s (pilihan: %s)", tidak_kenal, list(BUILDERS))
        return 2

    gabung = target_cells()
    for nama in diminta:
        berkas = tiles(nama) if nama != "osm" else sorted((config.STATIC / "osm").glob("*.osm.pbf"))
        if not berkas:
            log.warning("lapisan %-11s: tidak ada berkas di %s -- dilewati",
                        nama, config.STATIC / DIRS.get(nama, nama))
            continue
        log.info("lapisan %-11s: %d berkas", nama, len(berkas))
        try:
            feats = BUILDERS[nama](args.resolution_deg)
        except Exception as exc:  # noqa: BLE001
            log.error("lapisan %s gagal: %s: %s", nama, type(exc).__name__, exc)
            continue
        if feats.empty:
            log.warning("lapisan %s tidak menghasilkan fitur", nama)
            continue
        feats = feats.groupby(["lat_c", "lon_c"], as_index=False).mean(numeric_only=True)
        gabung = gabung.merge(feats, on=["lat_c", "lon_c"], how="left")
        log.info("  -> %d kolom fitur", len(feats.columns) - 2)

    dest = Path(args.out) if args.out else config.PROCESSED / "static_features.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    gabung = gabung.sort_values(["lat_c", "lon_c"]).reset_index(drop=True)
    gabung.to_parquet(dest, index=False)
    log.info("tulis %s (%d baris, %d kolom)", dest, len(gabung), len(gabung.columns))
    print(f"\n{dest}\n  baris : {len(gabung)}\n  kolom : {', '.join(gabung.columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

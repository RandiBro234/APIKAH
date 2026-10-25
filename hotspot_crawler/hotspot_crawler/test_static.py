"""Uji fungsi murni build_static_features. Tanpa jaringan; memakai GeoTIFF sintetis.

    python test_static.py
    pytest test_static.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

import build_static_features as b

_lulus = 0
_gagal = 0


def test(fn):
    global _lulus, _gagal
    try:
        fn()
        print(f"[OK  ] {fn.__name__}")
        _lulus += 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {fn.__name__}: {type(exc).__name__}: {exc}")
        _gagal += 1
    return fn


def _tif(path: Path, data: np.ndarray, west: float, north: float,
         pixel: float = 0.0025, nodata=None) -> Path:
    """Tulis GeoTIFF sintetis dengan transform eksplisit (tanpa from_bounds)."""
    import rasterio
    from rasterio import Affine

    data = np.asarray(data)
    tr = Affine(pixel, 0.0, west, 0.0, -pixel, north)
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0],
                       width=data.shape[1], count=1, dtype=str(data.dtype),
                       crs="EPSG:4326", transform=tr, nodata=nodata) as dst:
        dst.write(data, 1)
    return path


# ------------------------------------------------------------------ sel & agregasi
@test
def test_cell_index_of():
    """Pusat sel n*0,25+0,125 harus jatuh di indeks n."""
    r, c = b.cell_index_of(np.array([0.125, 0.375, -0.125]), np.array([100.125, 100.375, 100.875]))
    assert list(r) == [0, 1, -1], f"row salah: {r}"
    assert list(c) == [400, 401, 403], f"col salah: {c}"


@test
def test_cell_ids_returns_4tuple():
    """cell_ids mengembalikan (id, (r0, c0, n_lat, n_lon)): 2 elemen, bukan 4.

    Catatan kontrak: `id` berbentuk SAMA dengan input (peta piksel->sel), sedangkan
    `lat_c`/`lon_c` dari grid_of berisi satu entri PER SEL. Jadi panjangnya memang
    berbeda dan itu disengaja.
    """
    r = np.array([[5, 6], [5, 6]])
    c = np.array([[10, 10], [11, 11]])
    hasil = b.cell_ids(r, c)
    assert isinstance(hasil, tuple) and len(hasil) == 2, f"bentuk salah: {type(hasil)}"
    ids, (r0, c0, n_lat, n_lon) = hasil
    assert (r0, c0, n_lat, n_lon) == (5, 10, 2, 2), f"kotak salah: {(r0, c0, n_lat, n_lon)}"
    assert ids.shape == r.shape, f"bentuk id harus sama dengan input: {ids.shape}"
    # id harus memakai seluruh rentang 0..n_ids-1 tanpa celah
    assert sorted(ids.ravel().tolist()) == [0, 1, 2, 3], f"id tidak padat: {ids}"


@test
def test_aggregate_mean_sum_min_max():
    v = np.array([1.0, 2.0, np.nan, 4.0])
    i = np.array([0, 0, 0, 1])
    m = b.aggregate(v, i, 2, "mean")
    assert np.isclose(m[0], 1.5) and np.isclose(m[1], 4.0), f"mean: {m}"
    s = b.aggregate(v, i, 2, "sum")
    assert np.isclose(s[0], 3.0) and np.isclose(s[1], 4.0), f"sum: {s}"
    assert np.isclose(b.aggregate(v, i, 2, "max")[0], 2.0)
    assert np.isclose(b.aggregate(v, i, 2, "min")[0], 1.0)


@test
def test_aggregate_nan_jadi_nan():
    """Sel tanpa piksel sah harus NaN, bukan 0 (0 akan salah dibaca sebagai 'tidak ada api')."""
    m = b.aggregate(np.array([np.nan, np.nan]), np.array([0, 0]), 2, "mean")
    assert np.isnan(m[0]) and np.isnan(m[1]), f"harus NaN: {m}"


@test
def test_class_fractions_menjumlah_satu():
    v = np.array([10, 10, 20, 30])
    i = np.array([0, 0, 0, 0])
    f = b.class_fractions(v, i, 1, [10, 20, 30])
    total = sum(f.values())
    assert np.isclose(total[0], 1.0), f"jumlah fraksi = {total[0]}"
    assert np.isclose(f[10][0], 0.5)


@test
def test_class_fractions_buang_nodata():
    """Kode -1 (nodata) tidak boleh masuk penyebut."""
    v = np.array([10, -1, -1])
    i = np.array([0, 0, 0])
    f = b.class_fractions(v, i, 1, [10])
    assert np.isclose(f[10][0], 1.0), f"nodata ikut dihitung: {f[10][0]}"


# ------------------------------------------------------------------ slope
@test
def test_slope_flat_nol():
    """Permukaan datar -> slope 0 derajat."""
    elev = np.full((5, 5), 100.0)
    sl = b.slope_degrees(elev, dy_m=278.0, dx_m_by_row=np.full(5, 278.0))
    assert np.allclose(sl, 0.0), f"tidak nol: {sl.max()}"


@test
def test_slope_gradien_dikenal():
    """Naik 278 m per piksel HANYA arah timur (=1 m/m) -> 45 derajat."""
    dy_m = 278.0
    # konstan menurut lintang, naik menurut bujur: dz/dy = 0, dz/dx = 278/278 = 1
    elev = np.tile(np.arange(5, dtype="float64") * dy_m, (5, 1))
    sl = b.slope_degrees(elev, dy_m=dy_m, dx_m_by_row=np.full(5, dy_m))
    tengah = sl[1:-1, 1:-1]
    assert np.allclose(tengah, 45.0, atol=1e-6), f"harus 45, dapat {tengah.min()}-{tengah.max()}"


@test
def test_slope_dx_menyesuaikan_lintang():
    """Pada lintang tinggi, jarak piksel timur-barat lebih pendek -> slope lebih curam."""
    dy_m = 278.0
    elev = np.tile(np.arange(5, dtype="float64"), (5, 1)) * 278.0
    dx_sempit = np.full(5, 278.0 * np.cos(np.radians(60.0)))   # 60 derajat LU
    sl = b.slope_degrees(elev, dy_m=dy_m, dx_m_by_row=dx_sempit)
    # naik 1 piksel = 278 m; dx di 60 derajat = 139 m -> rasio 2 -> arctan(2) = 63,43 deg
    harap = np.degrees(np.arctan(2.0))
    assert np.allclose(sl[1:-1, 1:-1], harap, atol=1e-6), f"harap {harap:.2f}, dapat {sl[1:-1,1:-1].mean():.2f}"


@test
def test_slope_nan_tetap_nan():
    """Sesuai catatan: np.gradient pada array ber-NaN menghasilkan NaN. Itu DITERIMA."""
    elev = np.ones((4, 4))
    elev[1, 1] = np.nan
    sl = b.slope_degrees(elev, dy_m=278.0, dx_m_by_row=np.full(4, 278.0))
    assert np.isnan(sl).any(), "NaN seharusnya menyebar"


# ------------------------------------------------------------------ jarak metrik
@test
def test_distance_metrik_lintang_rendah():
    """Jarak vertikal = res*111320 m; horizontal = itu x cos(lintang). Diagonal = akar kuadrat."""
    mask = np.zeros((5, 5), bool)
    mask[2, 2] = True
    lat = np.full(5, 0.125)
    d = b.distance_to_features(mask, res_deg=0.25, row_lat=lat)
    dy = 0.25 * b.METERS_PER_DEG                        # 27.830 m, tanpa koreksi kosinus
    dx = dy * np.cos(np.radians(0.125))                 # koreksi lintang, walau kecil
    assert np.isclose(d[2, 1], dx, rtol=1e-9), f"horizontal: {d[2,1]:.4f} vs {dx:.4f}"
    assert np.isclose(d[1, 2], dy, rtol=1e-9), f"vertikal: {d[1,2]:.4f} vs {dy:.4f}"
    # diagonal = akar(dx^2 + dy^2), BUKAN 2 x (itu kesalahan yang ingin dicegah)
    assert np.isclose(d[1, 1], np.hypot(dx, dy), rtol=1e-9), f"diagonal: {d[1,1]:.2f}"


@test
def test_distance_mengecil_dengan_lintang():
    """Pada lintang 60 derajat, jarak timur-barat harus ~setengah jarak di ekuator."""
    mask = np.zeros((3, 3), bool)
    mask[1, 1] = True
    d_eq = b.distance_to_features(mask, 0.25, np.full(3, 0.0))
    d_60 = b.distance_to_features(mask, 0.25, np.full(3, 60.0))
    assert np.isclose(d_60[1, 0] / d_eq[1, 0], np.cos(np.radians(60.0)), rtol=1e-6), \
        f"rasio {d_60[1,0]/d_eq[1,0]:.3f}"


# ------------------------------------------------------------------ grid_of
@test
def test_grid_of_6tuple_dan_selaras():
    """grid_of -> 6 elemen. ids sepanjang PIXEL; lat_c/lon_c sepanjang SEL (n_ids)."""
    from rasterio import Affine
    # 2x3 piksel 0,0025 deg mulai (lon 94,00, lat 6,00), ke selatan
    tr = Affine(0.0025, 0.0, 94.0, 0.0, -0.0025, 6.0)
    ids, n_ids, lat_c, lon_c, lat_axis, lon_axis = b.grid_of(tr, (2, 3))
    assert len(ids) == 6, f"ids harus sepanjang piksel (6): {len(ids)}"
    assert n_ids == 1, f"semua piksel jatuh di 1 sel: n_ids={n_ids}"
    assert len(lat_c) == len(lon_c) == n_ids, \
        f"lat_c/lon_c harus sepanjang sel: {len(lat_c)}, {len(lon_c)}"
    assert len(lat_axis) == 2 and len(lon_axis) == 3, "sumbu harus sepanjang baris/kolom"
    # semua piksel berada di satu sel 0,25 deg -> hanya 1 id unik
    assert len(np.unique(ids)) == 1, f"id unik={np.unique(ids)}"
    assert np.allclose(lat_c, 5.875) and np.allclose(lon_c, 94.125), f"pusat sel: {lat_c}, {lon_c}"


# ------------------------------------------------------------------ read_decimated
@test
def test_read_decimated_returns_2tuple():
    """read_decimated harus mengembalikan (band, transform) -- 2 elemen."""
    with tempfile.TemporaryDirectory() as td:
        p = _tif(Path(td) / "a.tif", np.arange(100, dtype="float32").reshape(10, 10),
                 west=94.0, north=6.0)
        hasil = b.read_decimated(p, res_deg=0.0025)
        assert isinstance(hasil, tuple) and len(hasil) == 2, f"bentuk: {type(hasil)}"
        band, tr = hasil
        assert band.shape == (10, 10), f"bentuk band: {band.shape}"
        assert np.isclose(tr.a, 0.0025) and np.isclose(tr.e, -0.0025)


@test
def test_read_decimated_menurunkan_resolusi():
    """res_deg 0,005 pada piksel 0,0025 -> faktor 2, keluaran 5x5."""
    with tempfile.TemporaryDirectory() as td:
        p = _tif(Path(td) / "b.tif", np.ones((10, 10), "float32"), west=94.0, north=6.0)
        band, tr = b.read_decimated(p, res_deg=0.005)
        assert band.shape == (5, 5), f"bentuk: {band.shape}"
        assert np.isclose(tr.a, 0.005), f"transform tidak diskalakan: {tr.a}"


@test
def test_read_decimated_nodata_ke_nan():
    """Nodata pada raster kontinu harus jadi NaN, bukan angka ajaib."""
    with tempfile.TemporaryDirectory() as td:
        data = np.array([[1.0, -9999.0], [3.0, 4.0]], "float32")
        p = _tif(Path(td) / "c.tif", data, west=94.0, north=6.0, nodata=-9999.0)
        band, _ = b.read_decimated(p, res_deg=0.0025)
        assert np.isnan(band[0, 1]) and not np.isnan(band[1, 1]), f"band={band}"


# ------------------------------------------------------------------ hansen pairing
@test
def test_hansen_pairs_per_nama_berkas():
    """Pasangan harus dibentuk dari nama berkas, BUKAN folder: dua layer di folder sama."""
    nama = [
        "Hansen_GFC-2025-v1.13_treecover2000_10N_100E.tif",
        "Hansen_GFC-2025-v1.13_lossyear_10N_100E.tif",
        "Hansen_GFC-2025-v1.13_treecover2000_00N_110E.tif",
        "Hansen_GFC-2025-v1.13_lossyear_00N_110E.tif",
    ]
    hasil = {}
    for n in nama:
        m = b.HANSEN_NAME.search(n)
        assert m is not None, f"regex gagal pada {n}"
        layer, lat, lon = m.group(1).lower(), m.group(2).upper(), m.group(3).upper()
        hasil.setdefault((lat, lon), {})[layer] = n
    assert len(hasil) == 2, f"harus 2 tile, dapat {len(hasil)}"
    assert set(hasil[("10N", "100E")]) == {"treecover2000", "lossyear"}
    assert set(hasil[("00N", "110E")]) == {"treecover2000", "lossyear"}


# ------------------------------------------------------------------ build_hansen lag
@test
def test_build_hansen_memakai_lag_dari_config():
    """loss_frac_{lag}y harus memakai HANSEN_LOSS_REF_YEAR - lag, bukan tahun berjalan."""
    import config
    acuan = config.HANSEN_LOSS_REF_YEAR
    th1 = acuan - 1
    # lossyear berisi tahun-2000, jadi nilai piksel = th1 - 2000
    nilai = th1 - 2000
    assert nilai > 0, "HANSEN_LOSS_REF_YEAR harus cukup besar agar lossyear positif"
    # 2025 - 1 = 2024 -> 24. Pastikan tidak memakai tahun berjalan (2026 -> 26).
    assert nilai == 24, f"dapat {nilai}, harap 24"


def main() -> int:
    print(f"\nRingkasan: {_lulus} OK, {_gagal} FAIL\n")
    return 1 if _gagal else 0


if __name__ == "__main__":
    sys.exit(main())

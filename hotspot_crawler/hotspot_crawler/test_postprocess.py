"""Uji fungsi murni untuk skrip postprocess. Tanpa jaringan.

    python test_postprocess.py        # standalone, cetak hasil
    pytest test_postprocess.py        # bila pytest tersedia

Menambah fungsi murni baru? Tambahkan juga ujinya di sini.
"""
from __future__ import annotations

import sys
import traceback

import numpy as np
import pandas as pd
import xarray as xr

import config  # noqa: F401  (dipastikan bisa diimpor dari folder ini)
from common import ns_ew, tile_origins
from postprocess_era5 import (accum_daily, cell_center, es_kpa, instant_daily,
                             rh_from_t_td, vpd_from_t_td, time_name)

TESTS: list[tuple[str, callable]] = []


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


# --------------------------------------------------------------- konvensi grid
@test
def test_cell_center_mengikuti_konvensi_label():
    """Pusat sel 0,25 derajat = n*0,25 + 0,125 (sama dengan grid label hotspot)."""
    got = cell_center(np.array([0.0, 0.05, 0.125, 0.2499, 0.25, 0.3, -0.01]))
    want = np.array([0.125, 0.125, 0.125, 0.125, 0.375, 0.375, -0.125])
    assert np.allclose(got, want), f"dapat {got}, harusnya {want}"


@test
def test_time_name_menerima_kedua_konvensi():
    ds_baru = xr.Dataset(coords={"valid_time": pd.date_range("2023-07-01", periods=1)})
    ds_lama = xr.Dataset(coords={"time": pd.date_range("2023-07-01", periods=1)})
    assert time_name(ds_baru) == "valid_time"
    assert time_name(ds_lama) == "time"


# ------------------------------------------------------------------- fisika RH
@test
def test_rh_jenuh_seratus_persen():
    """Bila suhu = titik embun, udara jenuh, RH harus 100%."""
    rh = rh_from_t_td(np.array([300.0]), np.array([300.0]))
    assert rh[0] >= 99.9, f"dapat {rh[0]}"


@test
def test_rh_selalu_antara_0_dan_100():
    t = np.array([250.0, 300.0, 320.0])
    td = np.array([200.0, 290.0, 320.0])
    rh = rh_from_t_td(t, td)
    assert np.all(rh >= 0) and np.all(rh <= 100), f"dapat {rh}"


# ---------------------------------------------------------------------- fisika VPD
@test
def test_es_kpa_nilai_acuan():
    """Nilai acuan tabel: es(0)=0,611 kPa, es(20)=2,338 kPa, es(30)=4,243 kPa."""
    got = es_kpa(np.array([0.0, 20.0, 30.0]))
    want = np.array([0.611, 2.338, 4.243])
    assert np.allclose(got, want, atol=0.01), f"dapat {got}, harusnya ~{want}"


@test
def test_vpd_nol_saat_jenuh():
    """T = Td -> VPD = 0."""
    vpd = vpd_from_t_td(np.array([300.0]), np.array([300.0]))
    assert abs(vpd[0]) < 1e-9, f"dapat {vpd[0]}"


@test
def test_vpd_tidak_negatif_meski_td_lebih_besar():
    """Galat interpolasi bisa membuat Td > T; VPD harus dipotong di 0, bukan negatif."""
    vpd = vpd_from_t_td(np.array([290.0]), np.array([295.0]))
    assert vpd[0] == 0.0, f"dapat {vpd[0]}"


@test
def test_vpd_nilai_acuan():
    """T=20 C, Td=10 C -> VPD = es(20) - es(10) = 2,338 - 1,228 = 1,110 kPa."""
    vpd = vpd_from_t_td(np.array([293.15]), np.array([283.15]))
    assert abs(vpd[0] - 1.110) < 0.02, f"dapat {vpd[0]}, harusnya ~1,110"


# ------------------------------------------------------------ agregasi harian
def _ds_instant(t2m=300.0, d2m=290.0, u=3.0, v=4.0, ntime=4):
    """2 sel 0,1 derajat di dalam SATU sel 0,25 derajat (lat 0,05 & 0,15 -> lat_c 0,125)."""
    times = pd.date_range("2023-07-01", periods=ntime, freq="6h")
    shape = (ntime, 2, 1)
    vals = {"t2m": t2m, "d2m": d2m, "u10": u, "v10": v, "swvl1": 0.30, "swvl4": 0.40}
    return xr.Dataset(
        {n: (("valid_time", "latitude", "longitude"), np.full(shape, val))
         for n, val in vals.items()},
        coords={"valid_time": times, "latitude": [0.05, 0.15], "longitude": [100.05]},
    )


@test
def test_instant_daily_kolom_baru_ada():
    """u10_mean, v10_mean, vpd_mean, vpd_max harus muncul (TODO #14)."""
    out = instant_daily(_ds_instant())
    for col in ("u10_mean", "v10_mean", "vpd_mean", "vpd_max"):
        assert col in out.columns, f"kolom {col} tidak ada; ada: {list(out.columns)}"


@test
def test_instant_daily_kecepatan_angin_benar():
    """u=3, v=4 -> kecepatan angin = 5 m/s, dan komponen tersimpan terpisah."""
    out = instant_daily(_ds_instant(u=3.0, v=4.0))
    assert np.allclose(out["wind_mean"], 5.0), f"wind_mean={out['wind_mean'].tolist()}"
    assert np.allclose(out["u10_mean"], 3.0), f"u10_mean={out['u10_mean'].tolist()}"
    assert np.allclose(out["v10_mean"], 4.0), f"v10_mean={out['v10_mean'].tolist()}"


@test
def test_instant_daily_t2m_dikonversi_ke_celsius():
    out = instant_daily(_ds_instant(t2m=300.0))
    assert np.allclose(out["t2m_mean"], 26.85), f"dapat {out['t2m_mean'].tolist()}"


@test
def test_instant_daily_vpd_masuk_akal():
    """T=26,85 C, Td=16,85 C -> VPD sekitar 1,6 kPa."""
    out = instant_daily(_ds_instant(t2m=300.0, d2m=290.0))
    assert 1.0 < out["vpd_mean"].iloc[0] < 2.5, f"dapat {out['vpd_mean'].iloc[0]}"
    assert out["vpd_max"].iloc[0] >= out["vpd_mean"].iloc[0]


@test
def test_instant_daily_agregasi_spasial_ke_sel_025():
    """Dua sel 0,1 derajat di dalam sel 0,25 yang sama harus jadi SATU baris."""
    out = instant_daily(_ds_instant())
    assert len(out) == 1, f"dapat {len(out)} baris, harusnya 1"
    assert out["lat_c"].iloc[0] == 0.125 and out["lon_c"].iloc[0] == 100.125


@test
def test_accum_daily_tanggal_digeser_satu_hari_dan_satuan_benar():
    """tp 0,005 m -> 5 mm; ssrd 2e7 -> 20 MJ/m2; pev -0,002 m -> 2 mm; tanggal = D+1 - 1 hari."""
    times = pd.date_range("2023-07-01", periods=2, freq="1D")
    ds = xr.Dataset(
        {"tp": (("valid_time", "latitude", "longitude"), np.full((2, 1, 1), 0.005)),
         "ssrd": (("valid_time", "latitude", "longitude"), np.full((2, 1, 1), 2e7)),
         "pev": (("valid_time", "latitude", "longitude"), np.full((2, 1, 1), -0.002))},
        coords={"valid_time": times, "latitude": [0.05], "longitude": [100.05]},
    )
    out = accum_daily(ds).sort_values("date").reset_index(drop=True)
    assert len(out) == 2
    assert out["date"].iloc[0] == pd.Timestamp("2023-06-30"), f"dapat {out['date'].iloc[0]}"
    assert np.allclose(out["precip_mm"], 5.0), f"dapat {out['precip_mm'].tolist()}"
    assert np.allclose(out["ssrd_mjm2"], 20.0), f"dapat {out['ssrd_mjm2'].tolist()}"
    assert np.allclose(out["pev_mm"], 2.0), f"dapat {out['pev_mm'].tolist()}"


# -------------------------------------------------------------- tile (common.py)
@test
def test_tile_origins_pola_sumkal():
    """sumkal: Hansen 6 tile, WorldCover 36 tile, DEM 312 tile (terverifikasi 2026-10-25)."""
    n, w, s, e = config.AREAS["sumkal"]
    assert len(tile_origins(n, w, s, e, 10)) == 6
    assert len(tile_origins(n, w, s, e, 3)) == 36
    assert len(tile_origins(n, w, s, e, 1)) == 312


@test
def test_tile_origins_pola_indonesia():
    """indonesia menutupi sumkal: tile harus >= jumlah sumkal, dan tetap berisi tile sumkal."""
    n, w, s, e = config.AREAS["indonesia"]
    ns, ws, ss, es_ = config.AREAS["sumkal"]
    besar = set(tile_origins(n, w, s, e, 10))
    kecil = set(tile_origins(ns, ws, ss, es_, 10))
    assert kecil <= besar, "tile sumkal harus himpunan bagian tile indonesia"


@test
def test_ns_ew_penamaan():
    assert ns_ew(0, 100) == ("N", 0, "E", 100)
    assert ns_ew(-6, 100) == ("S", 6, "E", 100)
    assert ns_ew(10, -50) == ("N", 10, "W", 50)


# --------------------------------------------------------------------- runner
def main() -> int:
    lulus, gagal = 0, 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"[OK  ] {name}")
            lulus += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            gagal += 1
    print(f"\nRingkasan: {lulus} OK, {gagal} FAIL")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())

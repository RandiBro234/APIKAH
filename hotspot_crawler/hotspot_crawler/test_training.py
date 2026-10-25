"""Uji fungsi murni build_training_table. Tanpa jaringan, tanpa berkas.

    python test_training.py
    pytest test_training.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from build_training_table import (KEYS, TARGET_COLS, aggregate_labels,
                                  derived_columns, prev_month, shift_by_cell)

TESTS = []


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


# ------------------------------------------------------------------ prev_month
@test
def test_prev_month_biasa():
    assert prev_month(2023, 7) == (2023, 6)


@test
def test_prev_month_januari_mundur_tahun():
    assert prev_month(2023, 1) == (2022, 12)


@test
def test_prev_month_desember():
    assert prev_month(2023, 12) == (2023, 11)


# ------------------------------------------------------------------ derived_columns
@test
def test_derived_columns_membuang_kunci_dan_cuaca():
    """Kolom cuaca yang disalin features_daily harus dibuang (sumbernya era5_daily)."""
    weather = ["precip_mm", "t2m_mean", "rh_mean"]
    features_cols = KEYS + weather + ["hujan_7h", "spi_30", "bulan"]
    got = derived_columns(features_cols, weather)
    assert got == ["hujan_7h", "spi_30", "bulan"], f"dapat {got}"


@test
def test_derived_columns_tidak_menghitung_dua_kali():
    """Menghitung mentah akan 2x; derived_columns harus mencegah itu."""
    weather = ["precip_mm", "t2m_mean"]
    dup = KEYS + weather + ["hujan_7h"]
    assert set(derived_columns(dup, weather)).isdisjoint(weather)


# ------------------------------------------------------------------ aggregate_labels
def _raw(rows) -> pd.DataFrame:
    """rows: list of (lat, lon, date, confidence, frp)"""
    return pd.DataFrame(rows, columns=["latitude", "longitude", "date", "confidence", "frp"])


@test
def test_aggregate_labels_kolom_lengkap():
    d = aggregate_labels(_raw([(-1.0, 110.0, "2023-07-01", "n", 5.0)]))
    assert list(d.columns) == KEYS + TARGET_COLS, f"kolom: {list(d.columns)}"


@test
def test_aggregate_labels_menghitung_per_sel_hari():
    """3 api di sel sama/hari sama -> 1 baris, n_hotspot=3."""
    d = aggregate_labels(_raw([
        (-1.0, 110.0, "2023-07-01", "n", 5.0),
        (-1.0, 110.0, "2023-07-01", "l", 7.0),
        (-1.0, 110.0, "2023-07-01", "h", 9.0),
    ]))
    assert len(d) == 1, f"dapat {len(d)} baris"
    assert int(d["n_hotspot"].iloc[0]) == 3
    assert int(d["n_hotspot_high"].iloc[0]) == 1, "hanya confidence 'h' yang dihitung tinggi"
    assert abs(d["max_frp"].iloc[0] - 9.0) < 1e-9
    assert int(d["ada_api"].iloc[0]) == 1


@test
def test_aggregate_labels_memakai_pusat_sel_yang_benar():
    """-1,0 -> sel -0,875 (floor(-1,0/0,25)*0,25 + 0,125); 110,0 -> 110,125."""
    d = aggregate_labels(_raw([(-1.0, 110.0, "2023-07-01", "n", 1.0)]))
    assert abs(d["lat_c"].iloc[0] - (-0.875)) < 1e-9, f"lat_c={d['lat_c'].iloc[0]}"
    assert abs(d["lon_c"].iloc[0] - 110.125) < 1e-9, f"lon_c={d['lon_c'].iloc[0]}"


@test
def test_aggregate_labels_memisahkan_sel_berbeda():
    d = aggregate_labels(_raw([
        (-1.0, 110.0, "2023-07-01", "n", 1.0),    # sel -0,875 / 110,125
        (-1.0, 110.5, "2023-07-01", "n", 2.0),    # sel -0,875 / 110,625
    ]))
    assert len(d) == 2, f"dapat {len(d)} baris"


@test
def test_aggregate_labels_confidence_besar_huruf():
    """'H' dan 'high' harus tetap dihitung sebagai confidence tinggi."""
    d = aggregate_labels(_raw([
        (-1.0, 110.0, "2023-07-01", "H", 1.0),
        (-1.0, 110.0, "2023-07-01", "high", 2.0),
        (-1.0, 110.0, "2023-07-01", "n", 3.0),
    ]))
    assert int(d["n_hotspot_high"].iloc[0]) == 2, f"dapat {d['n_hotspot_high'].iloc[0]}"


@test
def test_aggregate_labels_kosong():
    """Masukan kosong harus mengembalikan kerangka berkolom benar, bukan error."""
    d = aggregate_labels(_raw([]))
    assert list(d.columns) == KEYS + TARGET_COLS
    assert len(d) == 0


@test
def test_aggregate_labels_tanpa_confidence_tinggi():
    d = aggregate_labels(_raw([(-1.0, 110.0, "2023-07-01", "n", 1.0)]))
    assert int(d["n_hotspot_high"].iloc[0]) == 0


# ------------------------------------------------------------------ shift_by_cell
def _cell_frame():
    """2 sel x 4 hari, nilai = nomor hari (mudah dibaca setelah digeser)."""
    rows = []
    for la in (0.125, 0.375):
        for i, tgl in enumerate(pd.date_range("2023-07-01", periods=4)):
            rows.append({"date": tgl, "lat_c": la, "lon_c": 100.125,
                         "nilai": float(i + (100 if la > 0.2 else 0))})
    return pd.DataFrame(rows).sort_values(["lat_c", "lon_c", "date"]).reset_index(drop=True)


@test
def test_shift_by_cell_menggeser_satu_hari():
    d = shift_by_cell(_cell_frame(), ["nilai"], 1)
    sel = d[d.lat_c == 0.125].sort_values("date").reset_index(drop=True)
    assert np.isnan(sel["nilai"].iloc[0]), "hari pertama harus kosong"
    assert list(sel["nilai"].iloc[1:]) == [0.0, 1.0, 2.0], f"dapat {list(sel['nilai'])}"


@test
def test_shift_by_cell_tidak_bocor_antar_sel():
    """Nilai sel sebelah tidak boleh masuk -- kesalahan yang paling mudah terjadi."""
    d = shift_by_cell(_cell_frame(), ["nilai"], 1)
    sel = d[d.lat_c == 0.125]["nilai"].dropna()
    assert (sel < 100).all(), "nilai sel lain (>=100) bocor ke sel ini"


@test
def test_shift_by_cell_lag_nol_tidak_mengubah():
    asli = _cell_frame()
    d = shift_by_cell(asli.copy(), ["nilai"], 0)
    assert np.allclose(d["nilai"], asli["nilai"])


def main() -> int:
    lulus, gagal = 0, 0
    for nama, fn in TESTS:
        try:
            fn()
            print(f"[OK  ] {nama}")
            lulus += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {nama}: {type(exc).__name__}: {exc}")
            gagal += 1
    print(f"\nRingkasan: {lulus} OK, {gagal} FAIL")
    return 1 if gagal else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Uji build_derived_features. Tanpa jaringan.

    python test_derived.py
    pytest test_derived.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import config
from build_derived_features import (DERIVED_COLS, build, dry_streak,
                                    empirical_spi, load_climate)

TESTS = []


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


EMPTY_CLIM = pd.DataFrame(columns=["y", "m"])


def _weather(ndays=250, start="2012-01-01", cells=((0.125, 100.125), (0.125, 100.375))):
    """Dua sel, hujan berpola 0,1,2,3,4 berulang supaya bisa dihitung tangan."""
    dates = pd.date_range(start, periods=ndays)
    rows = []
    for i, (la, lo) in enumerate(cells):
        for j, d in enumerate(dates):
            rows.append({
                "date": d, "lat_c": la, "lon_c": lo,
                "precip_mm": float((j + i) % 5),
                "t2m_mean": 25.0 + (j % 7), "rh_mean": 80.0, "rh_min": 60.0,
                "vpd_mean": 1.0, "vpd_max": 2.0,
                "u10_mean": 1.0, "v10_mean": 1.0,
                "swvl1_mean": 0.3, "swvl4_mean": 0.4,
                "ssrd_mjm2": 20.0, "pev_mm": 2.0,
            })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ dry_streak
@test
def test_dry_streak_pola_dasar():
    s = pd.Series([True, False, True, True, True])
    got = dry_streak(s).to_numpy()
    assert list(got) == [1, 0, 1, 2, 3], f"dapat {list(got)}"


@test
def test_dry_streak_nan_dianggap_basah():
    """NaN bukan hari kering: harus memutus rentetan, bukan memperpanjangnya."""
    s = pd.Series([True, np.nan, True])
    got = dry_streak(s).to_numpy()
    assert list(got) == [1, 0, 1], f"dapat {list(got)}"


@test
def test_dry_streak_semua_kering():
    got = dry_streak(pd.Series([True] * 5)).to_numpy()
    assert list(got) == [1, 2, 3, 4, 5], f"dapat {list(got)}"


@test
def test_dry_streak_mempertahankan_indeks():
    """transform() mencocokkan indeks; indeks tidak boleh diganti RangeIndex."""
    idx = [10, 20, 30]
    got = dry_streak(pd.Series([True, False, True], index=idx))
    assert list(got.index) == idx, f"indeks jadi {list(got.index)}"


# ---------------------------------------------------------------- empirical_spi
@test
def test_spi_terlalu_sedikit_data_semua_nan():
    got = empirical_spi(np.arange(5.0))
    assert np.all(np.isnan(got)), f"dapat {got}"


@test
def test_spi_menghasilkan_sebaran_normal():
    """Mean ~0 dan sd ~1 (ciri indeks terstandar)."""
    rng = np.random.default_rng(0)
    got = empirical_spi(rng.gamma(2.0, 1.0, 5000))
    assert abs(np.nanmean(got)) < 0.05, f"mean={np.nanmean(got)}"
    assert abs(np.nanstd(got) - 1) < 0.05, f"sd={np.nanstd(got)}"


@test
def test_spi_terbesar_dapat_nilai_tertinggi():
    got = empirical_spi(np.array([1.0, 2.0, 3.0, 4.0, 5.0,
                                  6.0, 7.0, 8.0, 9.0, 100.0]))
    assert got[9] == np.nanmax(got), f"dapat {got}"
    assert got[0] == np.nanmin(got)


# ------------------------------------------------------------------- build()
@test
def test_build_menghasilkan_semua_kolom_turunan():
    out = build(_weather(), EMPTY_CLIM)
    hilang = [c for c in DERIVED_COLS if c not in out.columns]
    assert not hilang, f"kolom hilang: {hilang}"


@test
def test_build_kolom_kalender():
    out = build(_weather(), EMPTY_CLIM)
    for c in ("bulan", "hari_dalam_tahun", "musim_kemarau"):
        assert c in out.columns, f"{c} tidak ada"
    row = out[out["date"] == pd.Timestamp("2012-08-05")]
    assert (row["bulan"] == 8).all()
    assert (row["musim_kemarau"] == 1).all(), "Agustus harus di musim kemarau"
    row = out[out["date"] == pd.Timestamp("2012-02-05")]
    assert (row["musim_kemarau"] == 0).all(), "Februari bukan musim kemarau"


@test
def test_hujan_berjalan_hanya_jendela_penuh():
    """min_periods=k lalu shift(1) -> 7 hari pertama kosong, hari ke-8 dan seterusnya terisi."""
    out = build(_weather(), EMPTY_CLIM)
    sel = out[(out["lat_c"] == 0.125) & (out["lon_c"] == 100.125)].sort_values("date")
    assert sel["hujan_7h"].head(7).isna().all(), "7 hari pertama harus NaN"
    assert sel["hujan_7h"].iloc[7:].notna().all(), "hari ke-8 dan seterusnya harus terisi"


@test
def test_hujan_30h_nilai_benar_untuk_pola_berulang():
    """Hujan 0,1,2,3,4 berulang: total 30 hari yang berakhir di T-1 harus = 6 siklus x 10 = 60.

    Tepatnya: 30 hari terakhir dari pola 0..4 berulang selalu berisi 6 dari tiap nilai
    -> 6*(0+1+2+3+4) = 60.
    """
    out = build(_weather(), EMPTY_CLIM)
    sel = out[(out["lat_c"] == 0.125) & (out["lon_c"] == 100.125)].sort_values("date")
    baris = sel.iloc[40]                      # aman: jauh dari tepi
    assert abs(baris["hujan_30h"] - 60.0) < 1e-6, f"dapat {baris['hujan_30h']}"


# --------------------------------------------------------------- UJI ANTI-BOCOR
@test
def test_anti_bocor_fitur_kausal_tidak_terpengaruh_masa_depan():
    """Inti bagian 7.2: mengubah cuaca pada hari >= T tidak boleh mengubah fitur di T."""
    df = _weather(ndays=120)
    T = pd.Timestamp("2012-03-01")

    out1 = build(df.copy(), EMPTY_CLIM)

    df2 = df.copy()
    mask = df2["date"] >= T
    df2.loc[mask, "precip_mm"] = 99.0
    df2.loc[mask, "t2m_mean"] = 99.0
    out2 = build(df2, EMPTY_CLIM)

    kausal = ["hujan_3h", "hujan_7h", "hujan_14h", "hujan_30h", "kering_beruntun"]
    for col in kausal:
        a = out1.loc[out1["date"] == T, col].to_numpy()
        b = out2.loc[out2["date"] == T, col].to_numpy()
        assert np.allclose(a, b, equal_nan=True), f"{col} berubah: {a} -> {b}"


@test
def test_anti_bocor_cuaca_mentah_hari_T_memang_berubah():
    """Kontrol: kolom cuaca mentah TIDAK digeser, jadi wajar ia berubah. Ini membuktikan
    uji sebelumnya menguji hal yang benar, bukan sekadar semuanya kebetulan sama."""
    df = _weather(ndays=120)
    T = pd.Timestamp("2012-03-01")
    out1 = build(df.copy(), EMPTY_CLIM)
    df2 = df.copy()
    df2.loc[df2["date"] >= T, "precip_mm"] = 99.0
    out2 = build(df2, EMPTY_CLIM)
    a = out1.loc[out1["date"] == T, "precip_mm"].to_numpy()
    b = out2.loc[out2["date"] == T, "precip_mm"].to_numpy()
    assert not np.allclose(a, b), "cuaca mentah hari T seharusnya ikut berubah"


@test
def test_lag_bisa_diubah():
    """--lag 3 harus menggeser lebih jauh; nilai di T harus sama dengan nilai di T-2 pada lag 1."""
    df = _weather(ndays=120)
    a = build(df.copy(), EMPTY_CLIM, lag=1)
    b = build(df.copy(), EMPTY_CLIM, lag=3)
    sel_a = a[(a["lat_c"] == 0.125) & (a["lon_c"] == 100.125)].sort_values("date").reset_index(drop=True)
    sel_b = b[(b["lat_c"] == 0.125) & (b["lon_c"] == 100.125)].sort_values("date").reset_index(drop=True)
    # hujan_7h pada lag=3 di baris ke-i harus sama dengan lag=1 di baris ke-i-2
    for i in range(40, 60):
        assert abs(sel_b["hujan_7h"].iloc[i] - sel_a["hujan_7h"].iloc[i - 2]) < 1e-6, \
            f"baris {i}: {sel_b['hujan_7h'].iloc[i]} vs {sel_a['hujan_7h'].iloc[i - 2]}"


# ------------------------------------------------------------------ indeks iklim
@test
def test_build_menempelkan_indeks_iklim_pada_bulan_yang_benar():
    clim = pd.DataFrame({"y": [2012, 2012, 2012], "m": [1, 2, 3],
                         "nino34": [0.1, 0.2, 0.3], "dmi": [0.0, 0.1, 0.2]})
    out = build(_weather(), clim)
    assert "nino34" in out.columns
    jan = out[out["date"].dt.month == 1]
    mar = out[out["date"].dt.month == 3]
    assert np.allclose(jan["nino34"], 0.1), f"dapat {jan['nino34'].unique()}"
    assert np.allclose(mar["nino34"], 0.3), f"dapat {mar['nino34'].unique()}"


@test
def test_load_climate_membuat_lag_bulanan():
    """nino34_lag1 di bulan M harus sama dengan nino34 bulan M-1, dan seterusnya."""
    tmp = Path(config.STATIC) / "climate_index"
    ada = tmp.exists()
    tmp.mkdir(parents=True, exist_ok=True)
    dibuat = []
    bulan = [1, 2, 3, 4, 5, 6]
    for name, vals in (("nino34", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
                       ("dmi", [0.0, 0.1, 0.2, 0.3, 0.4, 0.5])):
        p = tmp / f"{name}.csv"
        if p.exists():
            continue
        pd.DataFrame({"year": [2012] * len(bulan), "month": bulan, name: vals}).to_csv(p, index=False)
        dibuat.append(p)
    try:
        clim = load_climate()
        assert not clim.empty, "load_climate mengembalikan kosong"
        for col in ("nino34_lag1", "nino34_lag2", "nino34_lag3"):
            assert col in clim.columns, f"{col} tidak ada"
        jun = clim[(clim["y"] == 2012) & (clim["m"] == 6)]
        assert np.allclose(jun["nino34"], 0.6), f"dapat {jun['nino34'].to_numpy()}"
        assert np.allclose(jun["nino34_lag1"], 0.5), f"lag1={jun['nino34_lag1'].to_numpy()}"
        assert np.allclose(jun["nino34_lag2"], 0.4), f"lag2={jun['nino34_lag2'].to_numpy()}"
        assert np.allclose(jun["nino34_lag3"], 0.3), f"lag3={jun['nino34_lag3'].to_numpy()}"
    finally:
        if not ada:
            for p in dibuat:
                p.unlink(missing_ok=True)


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

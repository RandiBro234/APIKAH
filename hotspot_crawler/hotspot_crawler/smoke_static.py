"""Uji end-to-end build_static_features.py dengan GeoTIFF sintetis. Tanpa jaringan.

Memakai direktori sementara dan mengganti config.STATIC/PROCESSED/LOGS, jadi TIDAK
menyentuh data asli. Menguji rantai lengkap: penemuan berkas -> agregasi -> gabung ->
parquet, plus perilaku defensif build_osm saat tidak ada .osm.pbf.

Uji ini menemukan bug nyata: lapisan `peat` mencari folder "peat", padahal
crawl_static.py menyimpannya di "peatlands". Karena itu ada peta DIRS di modul.

    python smoke_static.py            # lulus -> direktori sementara dihapus
    python smoke_static.py --keep     # pertahankan direktori untuk diperiksa
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

import build_static_features as b
import config

PX = 0.0025          # derajat, ~250 m


def tif(path: Path, data, west: float, north: float, nodata=None) -> None:
    """Tulis GeoTIFF satu band dengan Affine eksplisit (bukan from_bounds)."""
    import rasterio
    from rasterio import Affine

    data = np.asarray(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    tr = Affine(PX, 0.0, west, 0.0, -PX, north)
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0],
                       width=data.shape[1], count=1, dtype=str(data.dtype),
                       crs="EPSG:4326", transform=tr, nodata=nodata) as dst:
        dst.write(data, 1)


def siapkan_lapisan(static: Path) -> None:
    """Buat 5 lapisan sintetis yang saling konsisten."""
    ny, nx = 40, 40
    w, n = 94.0, -5.0            # di dalam bbox area uji

    # DEM: bidang datar 100 m -> slope harus 0
    tif(static / "dem" / "Copernicus_sintetis.tif",
        np.full((ny, nx), 100.0, "float32"), w, n)

    # WorldCover: separuh hutan (10), separuh terbangun (50)
    wc = np.full((ny, nx), 10, "uint8")
    wc[:, nx // 2:] = 50
    tif(static / "worldcover" / "ESA_WorldCover_sintetis.tif", wc, w, n)

    # Hansen: dua layer, satu tile -> wajib dipasangkan dari NAMA berkas
    tif(static / "hansen" / "Hansen_GFC-2025-v1.13_treecover2000_06S_094E.tif",
        np.full((ny, nx), 80.0, "float32"), w, n)
    ly = np.zeros((ny, nx), "uint8")
    ly[:, : nx // 2] = 24        # 2024 = HANSEN_LOSS_REF_YEAR(2025) - 1
    tif(static / "hansen" / "Hansen_GFC-2025-v1.13_lossyear_06S_094E.tif", ly, w, n)

    # WorldPop: konstan 10
    tif(static / "worldpop" / "idn_ppp_2020_1km_sintetis.tif",
        np.full((ny, nx), 10.0, "float32"), w, n)

    # Gambut: 1 di kuadran kiri-atas. PENTING: folder bernama "peatlands".
    peat = np.zeros((ny, nx), "float32")
    peat[: ny // 2, : nx // 2] = 1.0
    tif(static / "peatlands" / "peat_sintetis.tif", peat, w, n)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    keep = "--keep" in argv

    tmp = Path(tempfile.mkdtemp(prefix="smoke_static_"))
    # Ganti arah config ke pohon sementara. Semua path di config bersifat relatif,
    # jadi ini aman dan tidak menyentuh data asli.
    config.STATIC = tmp / "static"
    config.PROCESSED = tmp / "processed"
    config.LOGS = tmp / "logs"
    config.AREA = [6.0, 94.0, -6.0, 95.0]
    config.ACTIVE_AREA = "smoke"

    gagal = 0

    def cek(nama: str, syarat: bool, detail: str = "") -> None:
        nonlocal gagal
        if syarat:
            print(f"  [OK  ] {nama}")
        else:
            print(f"  [FAIL] {nama} {detail}")
            gagal += 1

    try:
        siapkan_lapisan(config.STATIC)

        print("=== berkas sintetis ===")
        for layer, folder in b.DIRS.items():
            if layer == "osm":
                continue
            n_berkas = len(list((config.STATIC / folder).glob("*")))
            print(f"  {layer:12s} {n_berkas} berkas")
        print()

        out = tmp / "out.parquet"
        kode = b.main(["--only", "dem,worldcover,hansen,worldpop,peat",
                       "--out", str(out)])
        cek("main() berhasil (exit 0)", kode == 0, f"kode={kode}")
        cek("berkas keluaran ada", out.exists())

        if not out.exists():
            print(f"\nGAGAL: keluaran tidak dibuat\n(pohon: {tmp})")
            return 1

        import pandas as pd
        d = pd.read_parquet(out)
        print(f"\n=== hasil: {len(d)} baris, {len(d.columns)} kolom ===\n")

        # --- DEM
        se = d["elevasi_mean"].dropna()
        cek("elevasi_mean terisi", len(se) > 0, f"n={len(se)}")
        cek("elevasi_mean ~100", np.allclose(se.unique(), 100.0), f"nilai={se.unique()[:4]}")
        sl = d["slope_mean"].dropna()
        cek("slope_mean ~0 (datar)", np.allclose(sl.unique(), 0.0, atol=1e-6),
            f"nilai={sl.unique()[:4]}")

        # --- WorldCover. Kolom kelas yang tidak ada bernilai NaN; pandas menjumlahkannya
        #     0, jadi baris berisi harus disaring dulu.
        wc_cols = [c for c in d.columns if c.startswith("wc_")]
        sub = d[wc_cols]
        punya = sub.notna().any(axis=1)
        cek("ada sel tercakup WorldCover", punya.sum() > 0, f"n={punya.sum()}")
        total = sub[punya].sum(axis=1)
        cek("jumlah fraksi kelas ~1", np.allclose(total.unique(), 1.0, atol=1e-6),
            f"nilai={total.unique()[:4]}")
        cek("wc_pohon ~0.5", np.allclose(d.loc[punya, "wc_pohon"].unique(), 0.5, atol=1e-6))
        cek("wc_terbangun ~0.5", np.allclose(d.loc[punya, "wc_terbangun"].unique(), 0.5, atol=1e-6))
        cek("kolom wc lengkap 11", len(wc_cols) == 11, f"ada {len(wc_cols)}")

        # --- Hansen: pasangan dari nama berkas + lag dari config
        cek("treecover2000_mean ~80", np.allclose(d["treecover2000_mean"].dropna().unique(), 80.0))
        cek("loss_frac_1y ~0.5 (lag 2024)", np.allclose(d["loss_frac_1y"].dropna().unique(), 0.5,
                                                        atol=1e-6))
        cek("loss_frac_3y ~0 (lag 2022)", np.allclose(d["loss_frac_3y"].dropna().unique(), 0.0))

        # --- WorldPop
        cek("pop_density_mean ~10", np.allclose(d["pop_density_mean"].dropna().unique(), 10.0))

        # --- Gambut (bug yang ditemukan smoke test: folder "peatlands", bukan "peat")
        cek("peat_fraksi ADA (folder peatlands terbaca)", "peat_fraksi" in d.columns)
        pf = d.get("peat_fraksi", pd.Series(dtype="float64")).dropna()
        cek("peat_fraksi antara 0..1", len(pf) > 0 and bool(((pf >= 0) & (pf <= 1)).all()),
            f"n={len(pf)}, rentang {pf.min() if len(pf) else '-'}..{pf.max() if len(pf) else '-'}")

        # --- bentuk tabel
        cek("jumlah baris = 192", len(d) == 192, f"dapat {len(d)}")
        cek("kunci tidak ganda", not d.duplicated(["lat_c", "lon_c"]).any())

        # --- build_osm defensif: tanpa .osm.pbf harus kosong, bukan melempar
        print()
        try:
            osm = b.build_osm(0.0025)
            cek("build_osm defensif tanpa .pbf", isinstance(osm, pd.DataFrame) and osm.empty,
                f"hasil={type(osm).__name__} len={len(osm)}")
        except Exception as exc:  # noqa: BLE001
            cek("build_osm defensif tanpa .pbf", False, f"melempar {type(exc).__name__}: {exc}")

        print(f"\nRingkasan smoke test: {'LULUS' if gagal == 0 else f'{gagal} GAGAL'}")
        if gagal and not keep:
            print(f"(pohon dipertahankan untuk diperiksa: {tmp})")
        return 1 if gagal else 0

    finally:
        if gagal == 0 and not keep:
            shutil.rmtree(tmp, ignore_errors=True)
        elif keep:
            print(f"\n(pohon dipertahankan: {tmp})")


if __name__ == "__main__":
    sys.exit(main())

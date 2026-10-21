"""Preflight: cek library, kredensial, jangkauan endpoint, keberadaan dataset, dan limitasi
SEBELUM crawl. Jalankan dari komputer/server kalian (bukan dari sandbox yang jaringannya dibatasi).

    python preflight.py             # semua
    python preflight.py --only cds ewds noaa
Kode keluar: 0 = semua yang dipilih siap, 1 = ada yang gagal.
"""
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
import time
from pathlib import Path

import config
from common import ns_ew, tile_origins
from crawl_copernicus import CDS_URL, EWDS_URL, read_rc

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []


def rec(level: str, name: str, msg: str) -> None:
    results.append((level, name, msg))
    print(f"[{level}] {name:28s} {msg}")


# ------------------------------------------------------------------ 1. library
def check_libs() -> None:
    need = {"requests": True, "cdsapi": True, "xarray": True, "netCDF4": True, "pandas": True,
            "pyarrow": True, "earthaccess": False}
    for mod, required in need.items():
        try:
            importlib.import_module(mod)
            rec(OK, f"lib:{mod}", "terpasang")
        except ImportError:
            rec(FAIL if required else WARN, f"lib:{mod}",
                "belum terpasang (pip install -r requirements.txt)" if required else "opsional (burned area)")


# ------------------------------------------------------------------ 2. kredensial
def check_creds(only: set[str]) -> None:
    if "cds" in only:
        rc = read_rc(Path.home() / ".cdsapirc")
        key = os.getenv("CDSAPI_KEY") or rc.get("key")
        rec(OK if key else FAIL, "kredensial CDS", "ada" if key else "buat ~/.cdsapirc (url + key dari profil CDS)")
    if "ewds" in only:
        rc = read_rc(Path.home() / ".ewdsapirc")
        key = os.getenv("EWDS_API_KEY") or rc.get("key")
        rec(OK if key else FAIL, "kredensial EWDS",
            "ada" if key else "buat ~/.ewdsapirc (url=https://ewds.climate.copernicus.eu/api + key dari profil EWDS)")
    if "earthdata" in only:
        ok = os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD")
        rec(OK if ok else WARN, "kredensial Earthdata", "ada" if ok else "belum diset (hanya perlu untuk burned area)")


# ------------------------------------------------------------------ 3. endpoint
def probe(name: str, url: str, need_auth_ok: bool = False) -> None:
    import requests

    t0 = time.time()
    try:
        r = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=25, allow_redirects=True)
        dt = time.time() - t0
        r.close()
        if r.status_code < 400:
            rec(OK, name, f"HTTP {r.status_code} ({dt:.1f}s)")
        elif r.status_code in (401, 403) and need_auth_ok:
            rec(WARN, name, f"HTTP {r.status_code}: terjangkau tapi butuh login")
        elif r.status_code == 404:
            rec(FAIL, name, f"HTTP 404: link berubah/mati -> {url}")
        else:
            rec(FAIL, name, f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        rec(FAIL, name, f"tidak terjangkau: {type(exc).__name__}: {str(exc)[:100]}")


def probe_json(name: str, url: str) -> None:
    import requests

    try:
        r = requests.get(url, timeout=25)
        rec(OK if r.status_code == 200 else FAIL, name, f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        rec(FAIL, name, f"tidak terjangkau: {type(exc).__name__}")


def sample_tile_urls() -> dict[str, str]:
    N, W, S, E = config.AREA
    la, lo = tile_origins(N, W, S, E, 10)[0]
    ns, a, ew, b = ns_ew(la + 10, lo)
    hansen = config.HANSEN_URL.format(ver=config.HANSEN_VERSION, layer="lossyear", lat=a, ns=ns, lon=b, ew=ew)
    ns, a, ew, b = ns_ew(0, 102)
    wc = config.WORLDCOVER_URL.format(ns=ns, lat=a, ew=ew, lon=b)
    dem = config.DEM_URL.format(ns=ns, lat=a, ew=ew, lon=b)
    return {"hansen": hansen, "worldcover": wc, "dem": dem}


def check_endpoints(only: set[str]) -> None:
    if "cds" in only:
        probe("CDS API root", CDS_URL)
        probe_json("CDS dataset era5-land", f"{CDS_URL}/catalogue/v1/collections/{config.CDS_DATASET}")
    if "ewds" in only:
        probe("EWDS API root", EWDS_URL)
        probe_json("EWDS dataset cems-fire", f"{EWDS_URL}/catalogue/v1/collections/{config.EWDS_DATASET}")
    if "noaa" in only:
        for k, u in config.ENSO_URLS.items():
            probe(f"NOAA {k}", u)
    if "static" in only:
        probe("geoBoundaries API", config.GEOBOUNDARIES_API.format(level="ADM1"))
        tiles = sample_tile_urls()
        probe("Hansen sampel tile", tiles["hansen"])
        probe("WorldCover sampel tile", tiles["worldcover"])
        probe("Copernicus DEM sampel", tiles["dem"])
        probe("Geofabrik sumatra", config.GEOFABRIK_URLS["sumatra"])
        probe("WorldPop IDN 1km", config.WORLDPOP_URL)
    if "earthdata" in only:
        probe("Earthdata MCD64A1", "https://www.earthdata.nasa.gov/data/catalog/lpcloud-mcd64a1-061", True)


# ------------------------------------------------------------------ 4. limitasi + disk
def show_limits() -> None:
    from common import iter_months

    n_months = len(list(iter_months()))
    n_inst = len(config.ERA5_INSTANT) * 31 * len(config.ERA5_INSTANT_TIMES)
    n_acc = len(config.ERA5_ACCUM) * 31 * len(config.ERA5_ACCUM_TIMES)
    print("\n--- Limitasi & catatan ---")
    print(f"Periode  : {config.START} s/d {config.END} = {n_months} bulan, area={config.ACTIVE_AREA} {config.AREA}")
    print(f"ERA5-Land: {n_months*2} request (instant + accum per bulan); field per request maks "
          f"{max(n_inst, n_acc)} dari batas {config.ERA5_FIELD_LIMIT}")
    print("CDS/EWDS : request melebihi batas masuk ANTRIAN (bukan ditolak); jumlah request per user "
          "tidak dipublikasikan dan sering berubah. Skrip kirim satu per satu + resume (aman diulang).")
    print("Lisensi  : WAJIB diterima manual di halaman dataset (ERA5-Land dan CEMS Fire) sebelum "
          "request pertama; kalau belum, API menolak dengan error lisensi.")
    print("Disk     : ERA5-Land area sumkal ~100 MB/bulan-grup (perkiraan kasar) -> puluhan GB total; "
          "area 'indonesia' bisa >2x. Cek ruang di bawah.")
    free_gb = shutil.disk_usage(".").free / 1e9
    rec(OK if free_gb > 60 else WARN, "ruang disk bebas", f"{free_gb:.0f} GB (disarankan >= 60 GB untuk sumkal)")
    print("NASA     : MCD64A1 butuh akun Earthdata; data VIIRS S-NPP berhenti 2 Nov 2026 (tidak memengaruhi MODIS MCD64A1).")
    print("Open-Meteo tidak dipakai di pipeline ini (diganti Copernicus); untuk real-time pakai CDS ERA5T/forecast terpisah.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=["cds", "ewds", "noaa", "static", "earthdata"],
                    choices=["cds", "ewds", "noaa", "static", "earthdata"])
    args = ap.parse_args(argv)
    only = set(args.only)
    check_libs()
    check_creds(only)
    check_endpoints(only)
    show_limits()
    fails = [r for r in results if r[0] == FAIL]
    print(f"\nRingkasan: {sum(r[0]==OK for r in results)} OK, "
          f"{sum(r[0]==WARN for r in results)} WARN, {len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

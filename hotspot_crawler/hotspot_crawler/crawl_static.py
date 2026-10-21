"""Crawler sumber non-Copernicus: ENSO/IOD, batas wilayah, Hansen, WorldCover, DEM, OSM,
WorldPop, MCD64A1 (burned area), dan petunjuk manual untuk peta gambut.

Pakai:
    python crawl_static.py enso bounds hansen dem osm worldpop
    python crawl_static.py burned          # butuh EARTHDATA_USERNAME/PASSWORD + pip install earthaccess
    python crawl_static.py worldcover      # BESAR (puluhan tile, beberapa GB) -> opt-in
    python crawl_static.py peat            # hanya cek/menampilkan petunjuk manual
    python crawl_static.py all             # semua kecuali worldcover dan burned
    python crawl_static.py hansen --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import config
from common import (done, download_file, log, manifest_update, ns_ew, setup_logging,
                    tile_origins, with_retry)

N, W, S, E = config.AREA


# ------------------------------------------------------------------ ENSO / IOD
def parse_psl(text: str) -> list[tuple[int, int, float]]:
    """Format PSL: baris pertama 'tahun_awal tahun_akhir', lalu 'tahun v1..v12'.
    Nilai hilang: -99.99 / -9999 / -999. Baris non-numerik di akhir (catatan) diabaikan."""
    rows: list[tuple[int, int, float]] = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 13:
            continue
        try:
            year = int(parts[0])
            vals = [float(x) for x in parts[1:]]
        except ValueError:
            continue
        for month, v in enumerate(vals, start=1):
            if v <= -99:
                continue
            rows.append((year, month, v))
    return rows


def do_enso(dry: bool) -> None:
    import requests

    for name, url in config.ENSO_URLS.items():
        dest = config.STATIC / "climate_index" / f"{name}.csv"
        if dry:
            print("ENSO", name, url, "->", dest)
            continue
        if done(dest):
            log.info("lewati: %s", dest)
            continue
        try:
            r = with_retry(requests.get, url, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            rows = [x for x in parse_psl(r.text) if config.START.year <= x[0] <= config.END.year]
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["year", "month", name])
                w.writerows(rows)
            (dest.with_suffix(".raw.txt")).write_text(r.text)
            manifest_update("static", f"enso/{name}", "ok", f"{len(rows)} baris")
        except Exception as exc:  # noqa: BLE001
            log.error("GAGAL ENSO %s: %s", name, exc)
            manifest_update("static", f"enso/{name}", "failed", str(exc))


# ------------------------------------------------------------------ batas wilayah
def do_bounds(dry: bool) -> None:
    import requests

    for level in config.GEOBOUNDARIES_LEVELS:
        api = config.GEOBOUNDARIES_API.format(level=level)
        dest = config.STATIC / "boundaries" / f"idn_{level.lower()}.geojson"
        if dry:
            print("BOUNDS", api, "->", dest)
            continue
        if done(dest):
            log.info("lewati: %s", dest)
            continue
        try:
            meta = with_retry(lambda: requests.get(api, timeout=config.HTTP_TIMEOUT).json())
            (dest.parent).mkdir(parents=True, exist_ok=True)
            (dest.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=1))
            url = meta.get("gjDownloadURL") or meta.get("simplifiedGeometryGeoJSON")
            status = with_retry(download_file, url, dest)
            manifest_update("static", f"bounds/{level}", status, f"license={meta.get('boundaryLicense')}")
        except Exception as exc:  # noqa: BLE001
            log.error("GAGAL bounds %s: %s", level, exc)
            manifest_update("static", f"bounds/{level}", "failed", str(exc))


# ------------------------------------------------------------------ Hansen GFC
def hansen_tiles() -> list[tuple[int, int]]:
    """Tile Hansen 10x10 derajat, dinamai sudut KIRI-ATAS (lat atas, lon kiri)."""
    return [(la + 10, lo) for la, lo in tile_origins(N, W, S, E, 10)]


def do_hansen(dry: bool) -> None:
    for lat_top, lon_left in hansen_tiles():
        ns, la, ew, lo = ns_ew(lat_top, lon_left)
        for layer in config.HANSEN_LAYERS:
            url = config.HANSEN_URL.format(ver=config.HANSEN_VERSION, layer=layer,
                                           lat=la, ns=ns, lon=lo, ew=ew)
            dest = config.STATIC / "hansen" / url.rsplit("/", 1)[1]
            fetch("hansen", url, dest, dry)


# ------------------------------------------------------------------ WorldCover, DEM
def do_worldcover(dry: bool) -> None:
    for lat, lon in tile_origins(N, W, S, E, 3):          # tile 3x3, nama = sudut barat-daya
        ns, la, ew, lo = ns_ew(lat, lon)
        url = config.WORLDCOVER_URL.format(ns=ns, lat=la, ew=ew, lon=lo)
        fetch("worldcover", url, config.STATIC / "worldcover" / url.rsplit("/", 1)[1], dry)


def do_dem(dry: bool) -> None:
    for lat, lon in tile_origins(N, W, S, E, 1):
        ns, la, ew, lo = ns_ew(lat, lon)
        url = config.DEM_URL.format(ns=ns, lat=la, ew=ew, lon=lo)
        fetch("dem", url, config.STATIC / "dem" / url.rsplit("/", 1)[1], dry)


# ------------------------------------------------------------------ OSM, WorldPop
def do_osm(dry: bool) -> None:
    for name, url in config.GEOFABRIK_URLS.items():
        fetch("osm", url, config.STATIC / "osm" / f"{name}-latest.osm.pbf", dry)


def do_worldpop(dry: bool) -> None:
    fetch("worldpop", config.WORLDPOP_URL,
          config.STATIC / "worldpop" / config.WORLDPOP_URL.rsplit("/", 1)[1], dry)


# ------------------------------------------------------------------ MCD64A1 (Earthdata)
def do_burned(dry: bool) -> None:
    if dry:
        print("BURNED", config.MCD64A1, "bbox", (W, S, E, N), "->", config.STATIC / "mcd64a1")
        return
    try:
        import earthaccess
    except ImportError:
        log.error("pip install earthaccess dulu (opsional, hanya untuk burned area)")
        return
    if not (os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD")):
        log.error("Set EARTHDATA_USERNAME dan EARTHDATA_PASSWORD (akun gratis urs.earthdata.nasa.gov)")
        return
    earthaccess.login(strategy="environment")
    results = earthaccess.search_data(
        short_name=config.MCD64A1["short_name"], version=config.MCD64A1["version"],
        bounding_box=(W, S, E, N),
        temporal=(config.START.isoformat(), config.END.isoformat()),
    )
    log.info("MCD64A1: %d granule ditemukan", len(results))
    out = config.STATIC / "mcd64a1"
    out.mkdir(parents=True, exist_ok=True)
    with_retry(earthaccess.download, results, str(out))
    manifest_update("static", "mcd64a1", "ok", f"{len(results)} granule")


# ------------------------------------------------------------------ gambut (manual)
def do_peat(dry: bool) -> None:
    folder = config.STATIC / "peatlands"
    folder.mkdir(parents=True, exist_ok=True)
    have = [p.name for p in folder.glob("*") if p.is_file()]
    print("Peta gambut TIDAK diunduh otomatis (tidak ada URL langsung yang terverifikasi).")
    print("Unduh manual dari: https://data.globalforestwatch.org/datasets/gfw::global-peatlands/about")
    print(f"Taruh file di: {folder.resolve()}")
    print("File saat ini:", have or "(kosong)")
    manifest_update("static", "peatlands", "ok" if have else "manual_pending", ", ".join(have))


# ------------------------------------------------------------------ util unduh + CLI
def fetch(group: str, url: str, dest: Path, dry: bool) -> None:
    if dry:
        print(group, url, "->", dest)
        return
    key = f"{group}/{dest.name}"
    try:
        status = with_retry(download_file, url, dest)
        log.info("%s: %s", status, dest.name)
        manifest_update("static", key, status)
    except Exception as exc:  # noqa: BLE001
        log.error("GAGAL %s: %s", url, exc)
        manifest_update("static", key, "failed", str(exc))
    time.sleep(0.5)


JOBS = {"enso": do_enso, "bounds": do_bounds, "hansen": do_hansen, "worldcover": do_worldcover,
        "dem": do_dem, "osm": do_osm, "worldpop": do_worldpop, "burned": do_burned, "peat": do_peat}
DEFAULT_ALL = ["enso", "bounds", "hansen", "dem", "osm", "worldpop", "peat"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="+", choices=[*JOBS, "all"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    setup_logging("static")
    jobs = DEFAULT_ALL if "all" in args.jobs else args.jobs
    for j in jobs:
        log.info("== %s ==", j)
        JOBS[j](args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import json
import os
import sys
import time
from pathlib import Path

from . import config
from .common import (done, download_file, log, manifest_load, manifest_update, ns_ew,
                     setup_logging, target_lock, tile_origins, with_retry)
from .climate_tables import write_climate_parquet

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
        raw = config.STATIC / "climate_index" / f"{name}.raw.txt"
        dest = config.PROCESSED / "climate_index" / f"{name}.parquet"
        if dry:
            print("ENSO", name, url, "raw ->", raw, "Parquet ->", dest)
            continue
        with target_lock(dest):
            if done(dest):
                log.info("lewati: %s", dest)
                continue
            try:
                if done(raw):
                    text = raw.read_text(encoding="utf-8")
                else:
                    response = with_retry(requests.get, url, timeout=config.HTTP_TIMEOUT)
                    response.raise_for_status()
                    text = response.text
                    raw.parent.mkdir(parents=True, exist_ok=True)
                    temporary = raw.with_name(f"{raw.name}.{os.getpid()}.tmp")
                    temporary.write_text(text, encoding="utf-8")
                    temporary.replace(raw)
                rows = [x for x in parse_psl(text) if config.START.year <= x[0] <= config.END.year]
                if not rows:
                    raise ValueError(f"tidak ada baris indeks iklim yang dapat diparse: {raw}")
                write_climate_parquet(name, rows, dest)
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
    out = config.MCD64A1_DIR
    if dry:
        print("BURNED", config.MCD64A1, "bbox", (W, S, E, N), "->", out)
        return
    with target_lock(out / "mcd64a1-dataset"):
        previous = manifest_load("static").get("mcd64a1", {})
        try:
            expected = int(previous.get("note", "").split(maxsplit=1)[0])
        except (ValueError, IndexError):
            expected = -1
        existing = [path for path in out.glob("*.hdf") if done(path)]
        if previous.get("status") == "ok" and expected >= 0 and len(existing) == expected:
            log.info("lewati MCD64A1: %d granule sudah lengkap", expected)
            return
        try:
            import earthaccess
        except ImportError:
            log.error("pip install earthaccess dulu (opsional, hanya untuk burned area)")
            return
        if not (os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD")):
            log.error("Set EARTHDATA_USERNAME dan EARTHDATA_PASSWORD (akun gratis urs.earthdata.nasa.gov)")
            return
        try:
            earthaccess.login(strategy="environment")
            results = earthaccess.search_data(
                short_name=config.MCD64A1["short_name"], version=config.MCD64A1["version"],
                bounding_box=(W, S, E, N),
                temporal=(config.START.isoformat(), config.END.isoformat()),
            )
            log.info("MCD64A1: %d granule ditemukan", len(results))
            out.mkdir(parents=True, exist_ok=True)
            with_retry(earthaccess.download, results, str(out))
            manifest_update("static", "mcd64a1", "ok", f"{len(results)} granule")
        except Exception as exc:  # noqa: BLE001
            log.error("GAGAL MCD64A1: %s", exc)
            manifest_update("static", "mcd64a1", "failed", str(exc))


# ------------------------------------------------------------------ gambut
def do_peat(dry: bool) -> None:
    """Unduh peta gambut 1 km (paket Open-Earth-Monitor di Zenodo).

    Dulu langkah MANUAL lewat browser karena tidak ada URL langsung yang terverifikasi,
    dan server WRI (gis-gfw.wri.org) memang tidak bisa dihubungi dari mesin ini.
    Sejak 28 Okt 2026 diunduh otomatis: ketiga berkasnya GeoTIFF 1 km EPSG:4326 tanpa akun.
    """
    folder = config.STATIC / "peatlands"
    folder.mkdir(parents=True, exist_ok=True)
    for peran, berkas in config.PEAT_FILES.items():
        url = config.PEAT_BASE_URL + berkas + "?download=1"
        dest = folder / f"peat_{peran}_1km_2000_2020.tif"
        fetch("peatlands", url, dest, dry)
    log.info("versi WRI/Miettinen 2016 (paling akurat untuk Indonesia) tetap perlu manual: "
             "https://data.globalforestwatch.org/datasets/indonesia-peat-lands -> %s", folder)


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

"""Crawler Copernicus: ERA5-Land (CDS) dan CEMS Fire Historical (EWDS).

Pakai:
    python crawl_copernicus.py era5            # semua bulan START..END
    python crawl_copernicus.py fire
    python crawl_copernicus.py all --from 2023-01 --to 2023-12
    python crawl_copernicus.py era5 --dry-run  # hanya cetak request, tidak mengirim

Kredensial:
    CDS  : ~/.cdsapirc  (url=https://cds.climate.copernicus.eu/api, key=<token>)
    EWDS : ~/.ewdsapirc (url=https://ewds.climate.copernicus.eu/api, key=<token>)
           atau env EWDS_API_KEY. Format file sama dengan .cdsapirc.
Lisensi tiap dataset HARUS diterima manual di halaman dataset (bagian bawah form unduhan).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import config
from common import (days_in_month, done, iter_months, log, manifest_update,
                    months_from_end, setup_logging, with_retry)

CDS_URL = "https://cds.climate.copernicus.eu/api"
EWDS_URL = "https://ewds.climate.copernicus.eu/api"


# ------------------------------------------------------------------ klien
def read_rc(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def make_client(service: str):
    import cdsapi

    if service == "cds":
        rc = read_rc(Path.home() / ".cdsapirc")
        url = os.getenv("CDSAPI_URL", rc.get("url", CDS_URL))
        key = os.getenv("CDSAPI_KEY", rc.get("key"))
    else:
        rc = read_rc(Path.home() / ".ewdsapirc")
        url = os.getenv("EWDS_API_URL", rc.get("url", EWDS_URL))
        key = os.getenv("EWDS_API_KEY", rc.get("key"))
    if not key:
        raise SystemExit(f"Kredensial {service.upper()} tidak ditemukan. Jalankan preflight.py dulu.")
    return cdsapi.Client(url=url, key=key, quiet=True, progress=False)


# ------------------------------------------------------------------ ERA5-Land
def era5_request(year: int, month: int, group: str) -> dict:
    days = days_in_month(year, month)
    variables, times = ((config.ERA5_INSTANT, config.ERA5_INSTANT_TIMES) if group == "instant"
                        else (config.ERA5_ACCUM, config.ERA5_ACCUM_TIMES))
    n_fields = len(variables) * len(days) * len(times)
    # CDS membatasi "cost" (= 2 x field untuk dataset ini), bukan jumlah field.
    cost = n_fields * config.ERA5_COST_PER_FIELD
    if cost > config.ERA5_COST_LIMIT:
        raise ValueError(
            f"cost {cost} > batas CDS {config.ERA5_COST_LIMIT} "
            f"({n_fields} field x {config.ERA5_COST_PER_FIELD}); kurangi variabel/hari/jam")
    return {
        "variable": variables, "year": str(year), "month": f"{month:02d}",
        "day": days, "time": times,
        "data_format": "netcdf", "download_format": "unarchived",
        "area": config.AREA,
    }


def era5_target(year: int, month: int, group: str) -> Path:
    return config.RAW / "era5land" / group / f"{year}-{month:02d}.nc"


def run_era5(months, dry_run: bool) -> None:
    client = None if dry_run else make_client("cds")
    for year, month in months:
        for group in ("instant", "accum"):
            target = era5_target(year, month, group)
            key = f"era5land/{group}/{year}-{month:02d}"
            if done(target):
                log.info("lewati (sudah ada): %s", target)
                continue
            req = era5_request(year, month, group)
            if dry_run:
                print(key, req)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_suffix(".nc.part")
            try:
                log.info("kirim request %s", key)
                with_retry(client.retrieve, config.CDS_DATASET, req, str(part))
                part.rename(target)
                manifest_update("era5land", key, "ok")
            except Exception as exc:  # noqa: BLE001
                log.error("GAGAL %s: %s", key, exc)
                manifest_update("era5land", key, "failed", str(exc))
            time.sleep(config.SLEEP_BETWEEN_REQUESTS)


# ------------------------------------------------------------------ CEMS Fire
def fire_request(year: int, month: int, dataset_type: str, with_area: bool) -> dict:
    # CEMS Fire punya batas biaya sendiri (3720), terpisah dari batas ERA5-Land.
    n_fields = len(config.FIRE_VARIABLES) * len(days_in_month(year, month))
    cost = n_fields * config.FIRE_COST_PER_FIELD
    if cost > config.FIRE_COST_LIMIT:
        raise ValueError(
            f"cost CEMS {cost} > batas {config.FIRE_COST_LIMIT} "
            f"({n_fields} field x {config.FIRE_COST_PER_FIELD}); kurangi variabel/hari")
    req = {
        "product_type": config.FIRE_PRODUCT_TYPE,
        "variable": config.FIRE_VARIABLES,
        "dataset_type": dataset_type,
        "system_version": config.FIRE_SYSTEM_VERSION,
        "year": [str(year)], "month": [f"{month:02d}"],
        "day": days_in_month(year, month),
        "grid": config.FIRE_GRID,
        "data_format": "netcdf",
    }
    if with_area:
        req["area"] = config.AREA
    return req


def run_fire(months, dry_run: bool) -> None:
    client = None if dry_run else make_client("ewds")
    for year, month in months:
        target = config.RAW / "cems_fire" / f"{year}-{month:02d}.nc"
        key = f"cems_fire/{year}-{month:02d}"
        if done(target):
            log.info("lewati (sudah ada): %s", target)
            continue
        recent = months_from_end(year, month) < config.FIRE_INTERMEDIATE_LAST_N_MONTHS
        types = ([config.FIRE_DATASET_TYPE, "intermediate_dataset"] if not recent
                 else ["intermediate_dataset", config.FIRE_DATASET_TYPE])
        area_opts = [True, False] if config.FIRE_TRY_AREA else [False]
        if dry_run:
            print(key, fire_request(year, month, types[0], area_opts[0]))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(".nc.part")
        ok, last_err = False, ""
        for dtype in types:
            for with_area in area_opts:
                try:
                    log.info("kirim request %s (%s, area=%s)", key, dtype, with_area)
                    req = fire_request(year, month, dtype, with_area)
                    with_retry(client.retrieve, config.EWDS_DATASET, req, str(part), retries=2)
                    part.rename(target)
                    manifest_update("cems_fire", key, "ok", f"{dtype} area={with_area}")
                    ok = True
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = str(exc)
                    log.warning("kombinasi %s area=%s gagal: %s", dtype, with_area, last_err[:200])
            if ok:
                break
        if not ok:
            log.error("GAGAL %s: %s", key, last_err)
            manifest_update("cems_fire", key, "failed", last_err)
        time.sleep(config.SLEEP_BETWEEN_REQUESTS)


# ------------------------------------------------------------------ CLI
def parse_ym(s: str) -> date:
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["era5", "fire", "all"])
    ap.add_argument("--from", dest="start", type=parse_ym, default=config.START)
    ap.add_argument("--to", dest="end", type=parse_ym, default=config.END)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    setup_logging("copernicus")
    months = list(iter_months(args.start, args.end))
    log.info("%d bulan, area=%s, dry_run=%s", len(months), config.ACTIVE_AREA, args.dry_run)
    if args.what in ("era5", "all"):
        run_era5(months, args.dry_run)
    if args.what in ("fire", "all"):
        run_fire(months, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

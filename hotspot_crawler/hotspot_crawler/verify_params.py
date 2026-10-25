"""Validasi parameter di config.py terhadap definisi RESMI dataset CDS/EWDS.

Dua lapis, karena satu lapis saja terbukti tidak cukup:

  LAPIS 1 - tanpa kredensial. Membandingkan nama parameter di config.py dengan
      enum/form resmi dataset. Menangkap salah ketik nama variabel.

  LAPIS 2 - butuh kredensial. Menguji request NYATA hasil builder crawler
      (era5_request/fire_request) lewat apply_constraints() milik API.
      Ini menangkap KOMBINASI terlarang, yang tidak terlihat dari pengecekan nama:
      misalnya grid=original_grid hanya sah dengan data_format=grib, sehingga
      original_grid + netcdf ditolak 400 meskipun kedua nama itu ada di enum.
      Lapis 2 juga membaca estimate_costs() untuk memastikan beban request
      di bawah batas biaya yang dilaporkan API sendiri.

Ditemukan lewat skrip ini (21 Okt 2026): bug original_grid+netcdf, batas biaya
CEMS Fire 3720 yang tidak dijaga kode, dan dataset_type yang bergantung bulan.

Pakai:
    python verify_params.py
Kode keluar: 0 = semua cocok, 1 = ada yang tidak cocok.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

import config
from common import days_in_month, iter_months, months_from_end
from crawl_copernicus import CDS_URL, EWDS_URL, era5_request, fire_request, read_rc

CDS_BASE = CDS_URL
EWDS_BASE = EWDS_URL

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []

# Dimensi bebas: tidak pernah dibatasi berkas constraints, jadi jangan diperiksa subset.
FREE_DIMS = {"area"}

# Bulan contoh untuk lapis 2. Menyertakan batas rentang dan daerah peralihan
# consolidated <-> intermediate, tempat aturan dataset_type berubah.
SAMPLE_MONTHS = [(2012, 1), (2012, 6), (2015, 7), (2018, 4), (2020, 1),
                 (2022, 1), (2024, 7), (2026, 5), (2026, 8), (2026, 9)]


def rec(level: str, name: str, msg: str) -> None:
    results.append((level, name, msg))
    print(f"[{level}] {name:44s} {msg}")


def get_json(url: str) -> dict:
    r = requests.get(url, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ definisi resmi
def collection(base: str, dataset: str) -> dict:
    return get_json(f"{base}/catalogue/v1/collections/{dataset}")


def link_href(coll: dict, rel: str) -> str | None:
    for lk in coll.get("links", []):
        if lk.get("rel") == rel:
            return lk.get("href")
    return None


def form_fields(base: str, dataset: str) -> dict[str, list[str]]:
    """name field -> daftar nilai sah, dari berkas 'form' resmi (link dinamis)."""
    href = link_href(collection(base, dataset), "form")
    return _walk_form(get_json(href)) if href else {}


def _walk_form(node) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not isinstance(node, list):
        return out
    for fld in node:
        if not isinstance(fld, dict):
            continue
        name = fld.get("name")
        if not name:
            continue
        vals: list[str] = []

        def collect(n) -> None:
            if isinstance(n, dict):
                for k, v in n.items():
                    if k == "values" and isinstance(v, list):
                        vals.extend([x for x in v if isinstance(x, str)])
                    elif k == "values" and isinstance(v, str):
                        vals.append(v)
                    else:
                        collect(v)
            elif isinstance(n, list):
                for x in n:
                    collect(x)

        collect(fld.get("details", {}))
        seen: list[str] = []
        for v in vals:
            if v not in seen:
                seen.append(v)
        out[name] = seen
    return out


def process_inputs(base: str, dataset: str) -> dict[str, dict]:
    js = get_json(f"{base}/retrieve/v1/processes/{dataset}")
    ins = js.get("inputs", {})
    return ins if isinstance(ins, dict) else {}


# ------------------------------------------------------------------ pemeriksa lapis 1
def check_enum(label: str, allowed: list[str], used: list[str]) -> None:
    if not allowed:
        rec(WARN, label, "daftar nilai resmi tidak tersedia (form tidak terbaca)")
        return
    bad = [u for u in used if u not in allowed]
    if bad:
        rec(FAIL, label, f"tidak ada di daftar resmi: {bad}")
    else:
        rec(OK, label, f"{len(used)} nilai dipakai, semuanya sah (dari {len(allowed)})")


def check_inputs_exact(label: str, inputs: dict, sent: list[str]) -> None:
    want, got = set(inputs), set(sent)
    extra, missing = sorted(got - want), sorted(want - got)
    if extra or missing:
        rec(FAIL, label, f"beda dari API. dikirim tapi bukan input: {extra}; "
                         f"input resmi tidak dikirim: {missing}")
    else:
        rec(OK, label, f"cocok persis ({len(want)} input)")


def check_area(label: str, inputs: dict, area: list[float]) -> None:
    schema = (inputs.get("area") or {}).get("schema", {})
    n, w, s, e = area
    problems = []
    if schema.get("minItems") != 4 or schema.get("maxItems") != 4:
        problems.append(f"skema minta {schema.get('minItems')}..{schema.get('maxItems')} item")
    if not n > s:
        problems.append(f"north({n}) harus > south({s})")
    if not w < e:
        problems.append(f"west({w}) harus < east({e})")
    if problems:
        rec(FAIL, label, "; ".join(problems))
    else:
        rec(OK, label, f"urutan N,W,S,E sesuai skema (default API {schema.get('default')}); "
                       f"{config.ACTIVE_AREA}=[{n}, {w}, {s}, {e}]")


def check_days() -> None:
    bad = [f"{y}-{m:02d}" for y, m in iter_months()
           if not 28 <= len(days_in_month(y, m)) <= 31]
    if bad:
        rec(FAIL, "daftar hari per bulan", f"aneh di {bad[:5]}")
    else:
        rec(OK, "daftar hari per bulan",
            f"benar untuk {len(list(iter_months()))} bulan "
            f"(Feb 2024={len(days_in_month(2024, 2))}, Feb 2023={len(days_in_month(2023, 2))})")


def check_local_guard() -> None:
    """Guard lokal (tanpa kredensial): puncak field per request vs config.ERA5_FIELD_LIMIT."""
    worst_i = worst_a = 0
    for y, m in iter_months():
        nd = len(days_in_month(y, m))
        worst_i = max(worst_i, len(config.ERA5_INSTANT) * nd * len(config.ERA5_INSTANT_TIMES))
        worst_a = max(worst_a, len(config.ERA5_ACCUM) * nd * len(config.ERA5_ACCUM_TIMES))
    worst = max(worst_i, worst_a)
    if worst > config.ERA5_FIELD_LIMIT:
        rec(FAIL, "guard lokal field ERA5", f"puncak {worst} > batas {config.ERA5_FIELD_LIMIT}")
    else:
        rec(OK, "guard lokal field ERA5",
            f"puncak {worst} <= batas lokal {config.ERA5_FIELD_LIMIT}")


# ------------------------------------------------------------------ pemeriksa config
def check_config_consistency() -> None:
    """Invarian di dalam config.py sendiri. Tidak butuh jaringan, jadi dijalankan pertama.

    Tujuannya menangkap kesalahan yang tidak akan dilaporkan API: area yang tidak
    sinkron dengan pilihannya, tahun acuan Hansen yang basi setelah versi dinaikkan,
    atau lapisan statis yang menunjuk folder yang tidak ada.
    """
    # 1) ACTIVE_AREA <-> AREAS <-> AREA harus sinkron
    if config.ACTIVE_AREA not in config.AREAS:
        rec(FAIL, "daftar area",
            f"ACTIVE_AREA={config.ACTIVE_AREA!r} tidak ada di AREAS {list(config.AREAS)}")
    elif config.AREA != config.AREAS[config.ACTIVE_AREA]:
        rec(FAIL, "daftar area",
            f"AREA={config.AREA} tidak sama dengan AREAS[{config.ACTIVE_AREA!r}]="
            f"{config.AREAS[config.ACTIVE_AREA]}")
    else:
        rec(OK, "daftar area",
            f"ACTIVE_AREA={config.ACTIVE_AREA} sinkron, AREA={config.AREA}")

    # 2) bentuk bbox: [N, W, S, E] dengan N > S dan E > W, di dalam batas bumi
    rusak = []
    for nama, kotak in config.AREAS.items():
        n, w, s, e = kotak
        if n <= s:
            rusak.append(f"{nama}: N={n} <= S={s}")
        if e <= w:
            rusak.append(f"{nama}: E={e} <= W={w}")
        if not (-90 <= s <= 90 and -90 <= n <= 90):
            rusak.append(f"{nama}: lintang di luar -90..90")
        if not (-180 <= w <= 180 and -180 <= e <= 180):
            rusak.append(f"{nama}: bujur di luar -180..180")
    if rusak:
        rec(FAIL, "bentuk bbox area", "; ".join(rusak))
    else:
        rec(OK, "bentuk bbox area", f"{len(config.AREAS)} area valid, semuanya [N,W,S,E]")

    # 3) rentang waktu
    if not (config.START < config.END):
        rec(FAIL, "rentang waktu", f"START={config.START} tidak sebelum END={config.END}")
    else:
        rec(OK, "rentang waktu", f"{config.START} s/d {config.END}")

    # 4) tahun acuan Hansen harus ikut versi GFC, kalau tidak lag lossyear akan salah
    try:
        th = int(config.HANSEN_VERSION.split("-")[1])
    except (IndexError, ValueError):
        th = None
    dipakai = getattr(config, "HANSEN_LOSS_REF_YEAR", None)
    if th is None:
        rec(WARN, "tahun acuan Hansen",
            f"tahun tidak terbaca dari HANSEN_VERSION={config.HANSEN_VERSION!r}")
    elif dipakai != th:
        rec(FAIL, "tahun acuan Hansen",
            f"HANSEN_LOSS_REF_YEAR={dipakai} != {th} (dari HANSEN_VERSION={config.HANSEN_VERSION!r})"
            " -- perbarui setelah menaikkan versi Hansen")
    else:
        rec(OK, "tahun acuan Hansen", f"{th} cocok dengan {config.HANSEN_VERSION}")

    # 5) batas biaya: field limit harus benar-benar turunan dari limit/rasio
    e5_ok = config.ERA5_FIELD_LIMIT == config.ERA5_COST_LIMIT // config.ERA5_COST_PER_FIELD
    if not e5_ok:
        rec(FAIL, "batas biaya ERA5",
            "ERA5_FIELD_LIMIT tidak sama dengan ERA5_COST_LIMIT // ERA5_COST_PER_FIELD")
    else:
        rec(OK, "batas biaya ERA5",
            f"{config.ERA5_COST_LIMIT} / {config.ERA5_COST_PER_FIELD} = "
            f"{config.ERA5_FIELD_LIMIT} field per request")

    # 6) setiap lapisan statis harus punya folder di DIRS.
    #    Ini penjaga bug nyata: lapisan `peat` disimpan di folder "peatlands",
    #    jadi tanpa peta DIRS berkas gambut tidak akan pernah ditemukan.
    try:
        import build_static_features as bsf
        kurang = [x for x in (*bsf.LAYERS, *bsf.OPTIONAL_LAYERS) if x not in bsf.DIRS]
        if kurang:
            rec(FAIL, "folder lapisan statis", f"lapisan tanpa folder di DIRS: {kurang}")
        else:
            beda = {k: v for k, v in bsf.DIRS.items() if k != v}
            rec(OK, "folder lapisan statis",
                f"{len(bsf.DIRS)} lapisan punya folder; nama berbeda: {beda or 'tidak ada'}")
    except Exception as exc:  # noqa: BLE001
        rec(WARN, "folder lapisan statis", f"tidak bisa diperiksa: {type(exc).__name__}")


# ------------------------------------------------------------------ pemeriksa lapis 2
def authed_client(base: str, rc_name: str):
    """Klien ber-kredensial, atau None bila tidak ada (lapis 2 dilewati)."""
    key = read_rc(Path.home() / rc_name).get("key")
    if not key:
        return None
    try:
        from ecmwf.datastores import Client
    except ImportError:
        return None
    return Client(url=base, key=key, progress=False)


def check_request_valid(cli, dataset: str, label: str, req: dict) -> None:
    """Sah = tiap nilai request adalah subset nilai yang diizinkan API untuk dimensi itu."""
    try:
        out = cli.apply_constraints(dataset, req)
    except Exception as exc:  # noqa: BLE001
        rec(FAIL, label, f"apply_constraints gagal: {type(exc).__name__}: {str(exc)[:110]}")
        return
    bad: dict[str, tuple[list, list]] = {}
    for dim, vals in req.items():
        if dim in FREE_DIMS:
            continue
        allowed = out.get(dim)
        if not allowed:
            continue
        want = vals if isinstance(vals, list) else [vals]
        miss = [v for v in want if v not in allowed]
        if miss:
            bad[dim] = (miss, list(allowed)[:4])
    if bad:
        detail = "; ".join(f"{d}: {m} tidak ada di {a}" for d, (m, a) in bad.items())
        rec(FAIL, label, detail[:190])
    else:
        rec(OK, label, "kombinasi nilai sah")


def check_cost(cli, dataset: str, label: str, req: dict) -> None:
    """Baca batas biaya yang dilaporkan API sendiri, lalu bandingkan dengan request ini."""
    try:
        c = cli.estimate_costs(dataset, req)
        cost, limit = float(c.get("cost", 0)), float(c.get("limit", 0))
    except Exception as exc:  # noqa: BLE001
        rec(WARN, label, f"estimate_costs gagal: {type(exc).__name__}")
        return
    if limit <= 0:
        rec(WARN, label, f"API tidak melaporkan limit (cost={cost})")
        return
    pct = 100 * cost / limit
    level = OK if pct < 50 else (WARN if pct < 100 else FAIL)
    rec(level, label, f"cost {cost:.0f} dari limit {limit:.0f} ({pct:.1f}%)")


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    print("Validasi config.py terhadap definisi resmi CDS/EWDS\n")

    print("=== LAPIS 0: konsistensi config.py (tanpa jaringan) ===")
    check_config_consistency()

    try:
        e5_inputs = process_inputs(CDS_BASE, config.CDS_DATASET)
        cf_inputs = process_inputs(EWDS_BASE, config.EWDS_DATASET)
        e5_form = form_fields(CDS_BASE, config.CDS_DATASET)
        cf_form = form_fields(EWDS_BASE, config.EWDS_DATASET)
    except Exception as exc:  # noqa: BLE001
        rec(FAIL, "akses Catalogue API", f"{type(exc).__name__}: {str(exc)[:120]}")
        return 1
    rec(OK, "akses Catalogue API", "CDS + EWDS terjangkau")

    # ---------------- LAPIS 1: nama parameter ----------------
    print("\n=== LAPIS 1: nama parameter (tanpa kredensial) ===")

    print("\n--- ERA5-Land (CDS) ---")
    check_enum("era5 variable (instant+accum)", e5_form.get("variable", []),
               config.ERA5_INSTANT + config.ERA5_ACCUM)
    check_enum("era5 time", e5_form.get("time", []),
               config.ERA5_INSTANT_TIMES + config.ERA5_ACCUM_TIMES)
    check_enum("era5 data_format", e5_form.get("data_format", []), ["netcdf"])
    check_enum("era5 download_format", e5_form.get("download_format", []), ["unarchived"])
    check_enum("era5 month", e5_form.get("month", []), [f"{m:02d}" for m in range(1, 13)])
    check_inputs_exact("era5 kunci request", e5_inputs,
                       ["variable", "year", "month", "day", "time",
                        "data_format", "download_format", "area"])
    check_area("era5 area", e5_inputs, config.AREA)

    print("\n--- CEMS Fire (EWDS) ---")
    check_enum("fire variable", cf_form.get("variable", []), config.FIRE_VARIABLES)
    check_enum("fire product_type", cf_form.get("product_type", []), config.FIRE_PRODUCT_TYPE)
    check_enum("fire system_version", cf_form.get("system_version", []), config.FIRE_SYSTEM_VERSION)
    check_enum("fire dataset_type", cf_form.get("dataset_type", []),
               [config.FIRE_DATASET_TYPE, "intermediate_dataset"])
    check_enum("fire grid", cf_form.get("grid", []), [config.FIRE_GRID])
    check_enum("fire data_format", cf_form.get("data_format", []), ["netcdf"])
    check_inputs_exact("fire kunci request", cf_inputs,
                       ["product_type", "variable", "dataset_type", "system_version",
                        "year", "month", "day", "grid", "data_format", "area"])
    check_area("fire area", cf_inputs, config.AREA)

    check_days()
    check_local_guard()

    # ---------------- LAPIS 2: kombinasi nyata ----------------
    print("\n=== LAPIS 2: kombinasi request (butuh kredensial) ===")
    cds_cli = authed_client(CDS_BASE, ".cdsapirc")
    ewds_cli = authed_client(EWDS_BASE, ".ewdsapirc")
    if cds_cli is None or ewds_cli is None:
        rec(WARN, "lapis 2 dilewati",
            "kredensial belum lengkap; kombinasi terlarang TIDAK diperiksa")
    else:
        rec(OK, "klien ber-kredensial", "CDS + EWDS siap")

        print("\n--- ERA5-Land: request nyata per bulan contoh ---")
        for ym in SAMPLE_MONTHS:
            for group in ("instant", "accum"):
                req = era5_request(*ym, group)
                check_request_valid(cds_cli, config.CDS_DATASET,
                                    f"era5 {group} {ym[0]}-{ym[1]:02d}", req)
        # biaya: bulan terpanjang (31 hari) adalah beban terbesar
        check_cost(cds_cli, config.CDS_DATASET, "era5 biaya (31 hari, instant)",
                   era5_request(2023, 7, "instant"))
        check_cost(cds_cli, config.CDS_DATASET, "era5 biaya (31 hari, accum)",
                   era5_request(2023, 7, "accum"))

        print("\n--- CEMS Fire: rantai fallback dataset_type per bulan contoh ---")
        for ym in SAMPLE_MONTHS:
            recent = months_from_end(*ym) < config.FIRE_INTERMEDIATE_LAST_N_MONTHS
            tried = (["intermediate_dataset", config.FIRE_DATASET_TYPE] if recent
                     else [config.FIRE_DATASET_TYPE, "intermediate_dataset"])
            valid_types = []
            for dtype in tried:
                req = fire_request(*ym, dtype, True)
                try:
                    out = ewds_cli.apply_constraints(config.EWDS_DATASET, req)
                    allowed = out.get("dataset_type") or []
                    if dtype in allowed:
                        valid_types.append(dtype)
                except Exception:  # noqa: BLE001
                    pass
            if valid_types:
                rec(OK, f"fire {ym[0]}-{ym[1]:02d} dataset_type",
                    f"tersedia: {valid_types} (fallback run_fire: {tried})")
            else:
                rec(FAIL, f"fire {ym[0]}-{ym[1]:02d} dataset_type",
                    f"TIDAK ADA dataset_type sah dari {tried} - bulan ini akan gagal")

        check_request_valid(ewds_cli, config.EWDS_DATASET,
                            "fire 2023-07 consolidated",
                            fire_request(2023, 7, "consolidated_dataset", True))
        check_request_valid(ewds_cli, config.EWDS_DATASET,
                            "fire 2026-08 intermediate",
                            fire_request(2026, 8, "intermediate_dataset", True))
        check_cost(ewds_cli, config.EWDS_DATASET, "fire biaya (4 var, 31 hari)",
                   fire_request(2023, 7, "consolidated_dataset", True))

    fails = [r for r in results if r[0] == FAIL]
    print(f"\nRingkasan: {sum(r[0] == OK for r in results)} OK, "
          f"{sum(r[0] == WARN for r in results)} WARN, {len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

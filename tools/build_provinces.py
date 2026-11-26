"""Bangun batas provinsi dan pecahan kabupaten untuk peta Level 1.

Pakai:
    pip install "shapely>=2.0"
    python tools/build_provinces.py

Masukan
    data/geo/adm2_idn_simplified.geojson   519 poligon kabupaten/kota
    data/geo/adm2_risk.json                risiko contoh per kabupaten (h1)
    frontend/public/data/provinsi.geojson  metadata provinsi lama (shape_id/iso)
    frontend/public/data/risk_d*.sample.geojson  level sel contoh per horizon

Keluaran
    frontend/public/data/provinsi.geojson
    frontend/public/data/kabupaten/<slug>.geojson

Aturan agregasi provinsi
    - level          = level tertinggi dari kabupaten yang punya data (h1)
    - level_d0..d3   = level tertinggi sel contoh per horizon
    - kabupaten_terdampak = jumlah kabupaten dengan has_data=true
    - hotspot_72h    = jumlah hotspot_72h seluruh kabupaten
    - score          = skor tertinggi kabupaten (bila ada)

Catatan: `kabupaten_risk.json` memakai kode sintetis IDN-ADM2-*, sedangkan
geometri memakai shapeID. Karena itu join risiko memakai nama kabupaten +
provinsi, bukan kode.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

try:
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    from shapely.validation import make_valid
except ImportError:
    print('shapely belum terpasang. Jalankan: pip install "shapely>=2.0"')
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
ADM2_FULL_PATH = ROOT / "data" / "geo" / "geoBoundaries-IDN-ADM2.geojson"
ADM2_PATH = ROOT / "data" / "geo" / "adm2_idn_simplified.geojson"
RISK_PATH = ROOT / "data" / "geo" / "adm2_risk.json"
PROVINCE_PATH = ROOT / "frontend" / "public" / "data" / "provinsi.geojson"
DATA_DIR = ROOT / "frontend" / "public" / "data"
KABUPATEN_DIR = DATA_DIR / "kabupaten"
HORIZONS = ("d0", "d1", "d2", "d3")
# Provinsi boleh lebih kasar; kabupaten butuh tepi halus untuk extrusion.
PROVINCE_SIMPLIFY_TOLERANCE = 0.01
KABUPATEN_SIMPLIFY_TOLERANCE = 0.0015

# Nama provinsi di ADM2 tidak selalu sama dengan nama tampilan.
ALIASES = {
    "BangkaBelitung": "Kepulauan Bangka Belitung",
    "JakartaRaya": "DKI Jakarta",
    "Yogyakarta": "DI Yogyakarta",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"Berkas tidak ada: {path}")
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "provinsi"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> int:
    # Pakai geometri penuh bila tersedia; berkas simplified 0,004 derajat terlalu
    # kasar untuk tepi extrusion kabupaten. Berkas penuh tidak memuat nama
    # provinsi, jadi metadata diambil dari berkas simplified lewat shapeID.
    adm2_meta = load_json(ADM2_PATH)
    adm2 = load_json(ADM2_FULL_PATH if ADM2_FULL_PATH.exists() else ADM2_PATH)
    meta_by_id = {
        feature["properties"]["kode"]: feature["properties"]
        for feature in adm2_meta["features"]
    }
    normalized_features = []
    for feature in adm2["features"]:
        raw = feature.get("properties", {})
        meta = meta_by_id.get(raw.get("shapeID"), {})
        normalized_features.append({
            "type": "Feature",
            "properties": {
                "kode": meta.get("kode", raw.get("shapeID")),
                "kabupaten": meta.get("kabupaten", raw.get("shapeName")),
                "provinsi": meta.get("provinsi", "TIDAK DIKETAHUI"),
            },
            "geometry": feature.get("geometry"),
        })
    risk = load_json(RISK_PATH)
    old_provinces = load_json(PROVINCE_PATH)

    old_by_norm = {
        normalize(feature["properties"]["province"]): feature["properties"]
        for feature in old_provinces["features"]
    }

    def canonical(name: str) -> str:
        if name in ALIASES:
            return ALIASES[name]
        return old_by_norm.get(normalize(name), {}).get("province", name)

    risk_by_name = {
        (row["kabupaten"], row["provinsi"]): row
        for row in risk["kabupaten"]
    }

    groups: dict[str, list[dict]] = defaultdict(list)
    for feature in normalized_features:
        province = canonical(feature["properties"]["provinsi"])
        groups[province].append(feature)

    horizon_levels: dict[str, dict[str, int]] = {}
    unmatched_horizon: set[str] = set()
    for horizon in HORIZONS:
        path = DATA_DIR / f"risk_{horizon}.sample.geojson"
        if not path.exists():
            horizon_levels[horizon] = {}
            continue
        levels: dict[str, int] = {}
        for feature in load_json(path)["features"]:
            province = canonical(feature["properties"]["province"])
            if province not in groups:
                unmatched_horizon.add(feature["properties"]["province"])
                continue
            levels[province] = max(levels.get(province, 0), feature["properties"]["level"])
        horizon_levels[horizon] = levels

    province_features = []
    for province, features in sorted(groups.items()):
        geometries = [
            make_valid(shape(feature["geometry"]))
            for feature in features
            if feature.get("geometry")
        ]
        if not geometries:
            continue
        geometry = unary_union(geometries).simplify(PROVINCE_SIMPLIFY_TOLERANCE, preserve_topology=True)
        if geometry.is_empty:
            continue

        rows = [
            risk_by_name[(feature["properties"]["kabupaten"], feature["properties"]["provinsi"])]
            for feature in features
            if (feature["properties"]["kabupaten"], feature["properties"]["provinsi"]) in risk_by_name
        ]
        with_data = [row for row in rows if row.get("has_data")]
        old = old_by_norm.get(normalize(province), {})

        properties = {
            "province": province,
            "source_name": features[0]["properties"]["provinsi"],
            "shape_iso": old.get("shape_iso", ""),
            "shape_id": old.get("shape_id", slugify(province)),
            "has_data": bool(with_data),
            "hotspot_72h": sum(int(row.get("hotspot_72h", 0)) for row in rows),
            "kabupaten_terdampak": len(with_data),
            "kabupaten_total": len(features),
        }
        if with_data:
            properties["level"] = max(int(row["level"]) for row in with_data)
            properties["score"] = max(float(row.get("score", 0)) for row in with_data)
        for horizon, levels in horizon_levels.items():
            if province in levels:
                properties[f"level_{horizon}"] = levels[province]

        province_features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": mapping(geometry),
        })

    write_json(PROVINCE_PATH, {"type": "FeatureCollection", "features": province_features})

    KABUPATEN_DIR.mkdir(parents=True, exist_ok=True)
    for stale in KABUPATEN_DIR.glob("*.geojson"):
        stale.unlink()

    for province, features in groups.items():
        output_features = []
        for feature in features:
            props = feature["properties"]
            row = risk_by_name.get((props["kabupaten"], props["provinsi"]))
            properties = {
                "kode": props["kode"],
                "kabupaten": props["kabupaten"],
                "provinsi": province,
            }
            if row:
                for key in (
                    "has_data", "level", "score", "n_sel", "n_sel_penuh",
                    "cakupan_pct", "luas_kabupaten_ha", "luas_terdampak_ha_min",
                    "luas_terdampak_ha_max", "hotspot_72h", "unmatched",
                ):
                    if key in row:
                        properties[key] = row[key]
            else:
                properties["has_data"] = False
                properties["unmatched"] = True
            geometry = make_valid(shape(feature["geometry"])).simplify(
                KABUPATEN_SIMPLIFY_TOLERANCE,
                preserve_topology=True,
            )
            output_features.append({
                "type": "Feature",
                "properties": properties,
                "geometry": mapping(geometry),
            })
        write_json(
            KABUPATEN_DIR / f"{slugify(province)}.geojson",
            {"type": "FeatureCollection", "features": output_features},
        )

    print(f"OK: {len(province_features)} provinsi -> {PROVINCE_PATH}")
    print(f"OK: {len(groups)} berkas kabupaten -> {KABUPATEN_DIR}")
    if unmatched_horizon:
        print("Provinsi di data sel tanpa batas provinsi: " + ", ".join(sorted(unmatched_horizon)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

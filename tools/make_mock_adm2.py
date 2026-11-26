"""Bangkitkan fixture risiko kabupaten/kota dari poligon ADM2.

Memakai data contoh (is_mock=true) selama pipeline nyata belum siap, tetapi
*tetap* mematuhi semua invariant di docs/KONTRAK-DATA-KABUPATEN.md.

Pakai:
    python tools/make_mock_adm2.py                 # baca data/geo/adm2_idn_simplified.geojson
    python tools/make_mock_adm2.py --selftest      # uji logika dengan geojson sintetis
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

R_EARTH_KM = 6371.0088
CELL_HA = 62500  # 1 sel 0,25 derajat = 625 km2 = 62.500 ha
SRC = Path("data/geo/adm2_idn_simplified.geojson")
OUT = Path("data/geo/adm2_risk.json")


def ring_area_km2(ring: list[list[float]]) -> float:
    """Luas cincin poligon di permukaan bola (aproksimasi spherical excess)."""
    if len(ring) < 3:
        return 0.0
    total = 0.0
    for i in range(len(ring)):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i - 1][0]), math.radians(ring[i - 1][1])
        dlon = lon2 - lon1
        if dlon > math.pi:
            dlon -= 2 * math.pi
        elif dlon < -math.pi:
            dlon += 2 * math.pi
        total += dlon * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(total) * R_EARTH_KM**2 / 2.0


def geom_area_km2(geom: dict) -> float:
    if not geom:
        return 0.0
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return 0.0
    area = 0.0
    for poly in polys:
        if not poly:
            continue
        area += ring_area_km2(poly[0])
        for hole in poly[1:]:
            area -= ring_area_km2(hole)
    return max(area, 0.0)


def seeded(name: str, tag: str) -> float:
    """Angka deterministik 0..1 supaya fixture stabil antar-jalan."""
    h = hashlib.sha256(f"{name}|{tag}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def build_record(feature: dict, idx: int) -> dict:
    props = feature.get("properties", {}) or {}
    nama = props.get("shapeName") or props.get("kabupaten") or f"Unit-{idx:04d}"
    prov = props.get("shapeGroup") or props.get("provinsi") or "TIDAK DIKETAHUI"
    luas_km2 = geom_area_km2(feature.get("geometry"))

    if luas_km2 <= 0:
        return {
            "kode": f"IDN-ADM2-{idx:04d}",
            "kabupaten": nama,
            "provinsi": prov,
            "has_data": False,
            "n_sel": 0,
            "n_sel_penuh": 0,
            "cakupan_pct": 0.0,
            "luas_kabupaten_ha": 0,
            "hotspot_72h": 0,
            "unmatched": True,
        }

    luas_ha = int(round(luas_km2 * 100))
    cakupan_pct = round(seeded(nama, "cakupan") * 100, 1)
    terdampak_ha = luas_ha * cakupan_pct / 100.0

    # Rentang luas: jaga agar max tidak pernah melampaui luas kabupaten.
    luas_max = int(min(terdampak_ha, luas_ha))
    luas_min = int(min(terdampak_ha * 0.6, luas_max))

    n_sel = max(1, math.ceil(luas_max / CELL_HA))
    n_sel_penuh = min(n_sel, int(luas_min // CELL_HA))
    hotspot_72h = int(seeded(nama, "hotspot") * 40)

    has_data = luas_max > 0
    level = 0
    if has_data:
        # Level mengikuti cakupan supaya konsisten dengan luas yang dilaporkan.
        if cakupan_pct >= 75:
            level = 4
        elif cakupan_pct >= 50:
            level = 3
        elif cakupan_pct >= 25:
            level = 2
        else:
            level = 1

    rec = {
        "kode": f"IDN-ADM2-{idx:04d}",
        "kabupaten": nama,
        "provinsi": prov,
        "has_data": has_data,
        "n_sel": n_sel if has_data else 0,
        "n_sel_penuh": n_sel_penuh if has_data else 0,
        "cakupan_pct": cakupan_pct if has_data else 0.0,
        "luas_kabupaten_ha": luas_ha,
        "hotspot_72h": hotspot_72h,
        "unmatched": False,
    }
    if has_data:
        rec["level"] = level
        rec["score"] = round(seeded(nama, "score"), 3)
        rec["luas_terdampak_ha_min"] = luas_min
        rec["luas_terdampak_ha_max"] = luas_max
    return rec


def validate(rows: list[dict]) -> list[str]:
    errs: list[str] = []
    for r in rows:
        tag = r["kabupaten"]
        if r["n_sel_penuh"] > r["n_sel"]:
            errs.append(f"{tag}: n_sel_penuh > n_sel")
        if not (0 <= r["cakupan_pct"] <= 100):
            errs.append(f"{tag}: cakupan_pct di luar 0..100")
        if r.get("has_data"):
            if "luas_terdampak_ha_max" not in r:
                errs.append(f"{tag}: has_data tapi luas_terdampak_ha_max hilang")
                continue
            if r["luas_terdampak_ha_max"] > r["luas_kabupaten_ha"]:
                errs.append(
                    f"{tag}: luas_terdampak_ha_max ({r['luas_terdampak_ha_max']}) "
                    f"> luas_kabupaten_ha ({r['luas_kabupaten_ha']})"
                )
            if r["luas_terdampak_ha_min"] > r["luas_terdampak_ha_max"]:
                errs.append(f"{tag}: min > max")
            if "level" not in r:
                errs.append(f"{tag}: has_data tapi level hilang")
        else:
            if "level" in r or "score" in r:
                errs.append(f"{tag}: tanpa data tapi level/score terisi")
    return errs


def run(features: list[dict]) -> int:
    rows = [build_record(f, i) for i, f in enumerate(features, start=1)]
    errs = validate(rows)
    if errs:
        print(f"GAGAL: {len(errs)} pelanggaran invariant")
        for e in errs[:15]:
            print("  -", e)
        return 1
    payload = {
        "periode": "2026-11-04",
        "horizon": "h1",
        "sumber": "model-per-provinsi",
        "is_mock": True,
        "kabupaten": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(rows)} kabupaten, {len(json.dumps(payload))/1024:.0f} KB -> {OUT}")
    return 0


def selftest() -> int:
    """Tiga poligon sintetis: normal, sangat kecil, dan rusak (tanpa geometri)."""
    def sq(lon: float, lat: float, d: float) -> dict:
        return {
            "type": "Polygon",
            "coordinates": [[[lon, lat], [lon + d, lat], [lon + d, lat + d],
                             [lon, lat + d], [lon, lat]]],
        }

    feats = [
        {"properties": {"shapeName": "Uji Besar", "shapeGroup": "Riau"}, "geometry": sq(101.0, 0.0, 1.0)},
        {"properties": {"shapeName": "Uji Kecil", "shapeGroup": "Bali"}, "geometry": sq(115.0, -8.5, 0.05)},
        {"properties": {"shapeName": "Uji Rusak", "shapeGroup": "Papua"}, "geometry": None},
    ]
    rc = run(feats)
    if rc == 0:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        for k in data["kabupaten"]:
            print(
                f"  {k['kabupaten']:<10} luas={k['luas_kabupaten_ha']:>10} ha "
                f"terdampak={k.get('luas_terdampak_ha_min', '-')}..{k.get('luas_terdampak_ha_max', '-')} "
                f"n_sel={k['n_sel']} cakupan={k['cakupan_pct']}%"
            )
    OUT.unlink(missing_ok=True)
    return rc


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if not SRC.exists():
        print(f"Berkas sumber tidak ada: {SRC}")
        print("Unduh dulu sesuai docs/KONTRAK-DATA-KABUPATEN.md bagian 5.")
        sys.exit(2)
    gj = json.loads(SRC.read_text(encoding="utf-8"))
    sys.exit(run(gj["features"]))

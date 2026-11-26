"""Siapkan batas kabupaten/kota (ADM2) untuk mockup.

Tiga pekerjaan:
  1. Join kabupaten -> provinsi memakai batas ADM1 (gadm41_IDN_1.json), karena
     geoBoundaries ADM2 hanya memuat shapeGroup='IDN' (kode negara, bukan provinsi).
  2. Sederhanakan geometri (Douglas-Peucker) agar ringan untuk browser.
  3. Laporkan kabupaten yang tidak dapat dicocokkan ke provinsi mana pun.

Tanpa dependensi luar (shapely/geopandas tidak tersedia).

Pakai:
    python tools/prepare_adm2.py
"""

from __future__ import annotations

import json
from pathlib import Path

SRC = Path("data/geo/geoBoundaries-IDN-ADM2.geojson")
ADM1 = Path("gadm41_IDN_1.json")
OUT = Path("data/geo/adm2_idn_simplified.geojson")

# Toleransi penyederhanaan dalam derajat (~0,004 deg = +-440 m). Cukup halus untuk
# tampilan peta nasional, jauh lebih ringan untuk browser.
TOLERANCE = 0.004
MIN_RING_POINTS = 4


# ---------------------------------------------------------------- geometri
def point_in_ring(pt, ring) -> bool:
    """Ray casting. pt = (lon, lat)."""
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygon(pt, rings) -> bool:
    """rings[0] = luar, sisanya lubang."""
    if not rings or not point_in_ring(pt, rings[0]):
        return False
    return not any(point_in_ring(pt, hole) for hole in rings[1:])


def point_in_geom(pt, geom) -> bool:
    if not geom:
        return False
    if geom["type"] == "Polygon":
        return point_in_polygon(pt, geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return any(point_in_polygon(pt, poly) for poly in geom["coordinates"])
    return False


def poly_area_approx(rings) -> float:
    """Luas kasar (derajat^2) untuk memilih poligon terbesar."""
    if not rings:
        return 0.0
    ring = rings[0]
    s = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def representative_point(geom):
    """Titik wakil: pusat bbox poligon terbesar."""
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    if not polys:
        return None
    best = max(polys, key=poly_area_approx)
    ring = best[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def candidate_points(geom):
    """Titik-titik uji, urut dari yang paling mungkin berada di dalam provinsi.

    Kabupaten pesisir/berkelok sering punya centroid di luar wilayahnya, jadi
    dicoba beberapa cadangan. Cadangan terakhir dan paling andal: verteks pada
    cincin luar itu sendiri, yang menurut definisi berada di dalam poligon.
    """
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    if not polys:
        return []

    pts = []
    best = max(polys, key=poly_area_approx)
    ring = best[0][:-1] if best[0][0] == best[0][-1] else best[0]
    # 1. Titik tengah verteks poligon terbesar.
    if ring:
        pts.append((sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)))
    # 2. Pusat bbox poligon terbesar.
    pts.append(representative_point(geom))
    # 3. Centroid tiap poligon.
    for poly in polys:
        r = poly[0]
        if r:
            pts.append((sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)))
    # 4. Verteks cincin luar poligon terbesar, disebar merata.
    if ring:
        step = max(1, len(ring) // 16)
        pts.extend((p[0], p[1]) for p in ring[::step])
    # 5. Verteks cincin luar semua poligon lain.
    for poly in polys:
        if poly and poly[0]:
            step = max(1, len(poly[0]) // 4)
            pts.extend((p[0], p[1]) for p in poly[0][::step])
    return [p for p in pts if p]


def geom_bbox(geom):
    """Bbox benar untuk Polygon maupun MultiPolygon (termasuk seluruh anggota)."""
    if not geom:
        return None
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return None
    xs, ys = [], []
    for poly in polys:
        if not poly:
            continue
        for ring in poly:
            for p in ring:
                xs.append(p[0])
                ys.append(p[1])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def find_province(geom, prov_index):
    """Cari provinsi yang memuat geometri, mencoba beberapa titik uji.

    prov_index: daftar (bbox, feature) yang bbox-nya sudah dihitung sekali.
    """
    for pt in candidate_points(geom):
        for bb, p in prov_index:
            minx, miny, maxx, maxy = bb
            if not (minx <= pt[0] <= maxx and miny <= pt[1] <= maxy):
                continue
            if point_in_geom(pt, p.get("geometry")):
                return (p.get("properties") or {}).get("NAME_1")
    return None


# -------------------------------------------------------- Douglas-Peucker
def perp_dist(pt, a, b) -> float:
    ax, ay = a
    bx, by = b
    px, py = pt
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def simplify_ring(ring, tol: float):
    if len(ring) < MIN_RING_POINTS:
        return ring
    closed = ring[0] == ring[-1]
    pts = ring[:-1] if closed else ring[:]
    if len(pts) < 3:
        return ring

    # Bagi menjadi dua busur agar titik awal tidak memaksa bentuk.
    mid = len(pts) // 2
    keep = [False] * len(pts)

    def dp(lo: int, hi: int) -> None:
        keep[lo] = True
        keep[hi] = True
        stack = [(lo, hi)]
        while stack:
            a, b = stack.pop()
            best_d, best_i = -1.0, -1
            for i in range(a + 1, b):
                d = perp_dist(pts[i], pts[a], pts[b])
                if d > best_d:
                    best_d, best_i = d, i
            if best_i != -1 and best_d > tol:
                keep[best_i] = True
                stack.append((a, best_i))
                stack.append((best_i, b))

    dp(0, mid)
    dp(mid, len(pts) - 1)

    out = [pts[i] for i in range(len(pts)) if keep[i]]
    if len(out) < 3:
        return ring
    if closed:
        out.append(out[0])
    return out


def simplify_geom(geom, tol: float) -> dict:
    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [simplify_ring(r, tol) for r in geom["coordinates"]]}
    if geom["type"] == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [[simplify_ring(r, tol) for r in poly] for poly in geom["coordinates"]],
        }
    return geom


def count_vertices(geom) -> int:
    if not geom:
        return 0
    if geom["type"] == "Polygon":
        return sum(len(r) for r in geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return sum(len(r) for p in geom["coordinates"] for r in p)
    return 0


# ------------------------------------------------------------------- utama
def main() -> int:
    if not SRC.exists():
        print(f"Sumber tidak ada: {SRC}")
        return 2
    if not ADM1.exists():
        print(f"Batas provinsi tidak ada: {ADM1}")
        return 2

    kab = json.loads(SRC.read_text(encoding="utf-8"))["features"]
    prov = json.loads(ADM1.read_text(encoding="utf-8"))["features"]
    prov_index = [(geom_bbox(p.get("geometry")), p) for p in prov]
    prov_index = [(bb, p) for bb, p in prov_index if bb]

    out_features = []
    unmatched = []
    total_before = total_after = 0

    for feat in kab:
        geom = feat.get("geometry")
        props = feat.get("properties", {}) or {}
        nama = props.get("shapeName") or "Tanpa Nama"

        nama_prov = None
        if geom:
            nama_prov = find_province(geom, prov_index)
        if not nama_prov:
            unmatched.append(nama)

        total_before += count_vertices(geom)
        sgeom = simplify_geom(geom, TOLERANCE) if geom else None
        total_after += count_vertices(sgeom)

        out_features.append({
            "type": "Feature",
            "properties": {
                "kode": props.get("shapeID") or "",
                "kabupaten": nama,
                "provinsi": nama_prov or "TIDAK DIKETAHUI",
            },
            "geometry": sgeom,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "sumber": "geoBoundaries gbOpen IDN ADM2 (CC BY 3.0 IGO)",
            "toleransi_derajat": TOLERANCE,
            "jumlah_unit": len(out_features),
        },
        "features": out_features,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"Unit            : {len(out_features)}")
    print(f"Verteks         : {total_before:,} -> {total_after:,} "
          f"({100 * total_after / total_before:.1f}%)")
    print(f"Ukuran keluaran : {size_mb:.2f} MB -> {OUT}")
    print(f"Tanpa provinsi  : {len(unmatched)}")
    if unmatched:
        for n in unmatched[:20]:
            print("   -", n)
        if len(unmatched) > 20:
            print(f"   ... dan {len(unmatched) - 20} lainnya")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

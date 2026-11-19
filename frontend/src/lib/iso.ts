import { geoMercator, geoPath } from 'd3-geo'
import polylabel from 'polylabel'
import type { FeatureCollection, Geometry, MultiPolygon, Polygon } from 'geojson'

export const ISO_ROTATE = -25
export const ISO_SQUASH = 0.55
export const ISO_BASE = 1000
export const WALL_LAYERS = 3
export const WALL_STEP = 8

export const ROTATE_OVERRIDES: Record<string, number> = {
  'Jawa Timur': -12,
  'Jawa Tengah': -14,
  'Sumatera Utara': -16,
}

export type IsoMatrix = [number, number, number, number, number, number]

export type Layout = {
  matrix: IsoMatrix
  provincePath: string
  borders: Array<{ kode: string; name: string; d: string }>
  borderMesh: string
  shadow: { cx: number; cy: number; rx: number; ry: number }
  kmPerPx: number
  rotate: number
  project: (lon: number, lat: number) => [number, number] | null
}

export function applyMatrix(matrix: IsoMatrix, x: number, y: number): [number, number] {
  const [a, b, c, d, e, f] = matrix
  return [a * x + c * y + e, b * x + d * y + f]
}

export function ringArea(ring: number[][]): number {
  let sum = 0
  for (let i = 0; i < ring.length - 1; i += 1) {
    sum += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
  }
  return Math.abs(sum) / 2
}

// Buang pulau/komponen poligon yang sangat kecil agar lempeng tetap bersih.
export function dropTinyParts(geometry: Polygon | MultiPolygon, minArea = 0.01): Polygon | MultiPolygon {
  if (geometry.type === 'Polygon') return geometry
  const kept = geometry.coordinates.filter((polygon) => ringArea(polygon[0]) >= minArea)
  if (kept.length === 0) return geometry
  return kept.length === 1 ? { type: 'Polygon', coordinates: kept[0] } : { type: 'MultiPolygon', coordinates: kept }
}

// Sederhanakan koordinat dengan grid kecil; preservasi bentuk dan berat path.
export function simplifyGeometry(geometry: Polygon | MultiPolygon, step = 0.005): Polygon | MultiPolygon {
  const round = (value: number) => Math.round(value / step) * step
  const walk = (coords: unknown): unknown => {
    if (!Array.isArray(coords)) return coords
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      return [round(coords[0]), round(coords[1])]
    }
    const out: unknown[] = []
    let prev = ''
    for (const child of coords) {
      const value = walk(child)
      const key = JSON.stringify(value)
      if (key !== prev) out.push(value)
      prev = key
    }
    return out
  }
  return { ...geometry, coordinates: walk((geometry as { coordinates: unknown }).coordinates) } as Polygon | MultiPolygon
}

function closeRing(ring: number[][]): number[][] | null {
  if (!Array.isArray(ring)) return null
  const points = ring.filter((point) => Array.isArray(point) && typeof point[0] === 'number' && typeof point[1] === 'number')
  if (points.length < 4) return null
  const first = points[0]
  const last = points[points.length - 1]
  if (first[0] !== last[0] || first[1] !== last[1]) points.push(first)
  if (points.length < 4) return null
  const lons = points.map((point) => point[0])
  const lats = points.map((point) => point[1])
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  // Buang ring yang membungkus dunia / keluar Indonesia; ring seperti ini
  // membuat hit-area raksasa dan merusak framing.
  if (maxLon - minLon > 60 || maxLat - minLat > 30) return null
  if (minLon < 90 || maxLon > 145 || minLat < -15 || maxLat > 10) return null
  return points
}

function signedRingArea(ring: number[][]): number {
  let sum = 0
  for (let i = 0; i < ring.length - 1; i += 1) {
    sum += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
  }
  return sum / 2
}

function orientPolygon(rings: number[][][]): number[][][] {
  if (rings.length === 0) return rings
  const outer = signedRingArea(rings[0]) > 0 ? [...rings[0]].reverse() : rings[0]
  const holes = rings.slice(1).map((ring) => (signedRingArea(ring) < 0 ? [...ring].reverse() : ring))
  return [outer, ...holes]
}

export function sanitizeGeometry(geometry: Geometry): Geometry | null {
  if (geometry.type === 'Polygon') {
    const rings = geometry.coordinates.map(closeRing).filter((ring): ring is number[][] => Boolean(ring))
    return rings.length ? { type: 'Polygon', coordinates: orientPolygon(rings) } : null
  }
  if (geometry.type === 'MultiPolygon') {
    const polygons = geometry.coordinates
      .map((polygon) => polygon.map(closeRing).filter((ring): ring is number[][] => Boolean(ring)))
      .filter((polygon) => polygon.length > 0)
      .map(orientPolygon)
    return polygons.length ? { type: 'MultiPolygon', coordinates: polygons } : null
  }
  return geometry
}

export function poleOf(geometry: Polygon | MultiPolygon): { lon: number; lat: number; distance: number } | null {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  let best: number[][] | null = null
  let bestArea = -1
  for (const polygon of polygons) {
    const ring = polygon[0]
    if (!ring || ring.length < 4) continue
    const area = ringArea(ring)
    if (area > bestArea) {
      bestArea = area
      best = ring
    }
  }
  if (!best) return null
  const point = polylabel([best as Array<[number, number]>], 0.01)
  return { lon: point[0], lat: point[1], distance: point.distance }
}

export function buildLayout(
  provinceGeometry: Geometry,
  collection: FeatureCollection<Polygon | MultiPolygon, { kode: string; kabupaten: string }>,
  width: number,
  height: number,
  provinceName: string,
): Layout | null {
  if (width <= 0 || height <= 0 || collection.features.length === 0) return null

  const projection = geoMercator().scale(1000).translate([0, 0]).clipExtent([[0, -1000], [3000, 1000]])
  const path = geoPath(projection)
  const safeProvince = sanitizeGeometry(provinceGeometry)
  const safeFeatures = collection.features
    .map((feature) => {
      const geometry = sanitizeGeometry(feature.geometry)
      return geometry ? { ...feature, geometry } : null
    })
    .filter((feature): feature is typeof collection.features[number] => Boolean(feature))
  if (!safeProvince || safeFeatures.length === 0) return null
  const framingPolygons: Array<{ area: number; geometry: Polygon }> = []
  for (const feature of safeFeatures) {
    const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates
    for (const polygon of polygons) {
      const area = ringArea(polygon[0])
      if (area > 0) framingPolygons.push({ area, geometry: { type: 'Polygon', coordinates: polygon } })
    }
  }
  const maxArea = Math.max(0, ...framingPolygons.map((item) => item.area))
  const framingGeometries = framingPolygons
    .filter((item) => item.area >= maxArea * 0.15)
    .map((item) => item.geometry)
  const provincePath = path(safeProvince) ?? ''
  const borders = safeFeatures.map((feature) => ({
    kode: feature.properties.kode,
    name: feature.properties.kabupaten,
    d: path(feature.geometry) ?? '',
  }))
  const borderMesh = borders.map((border) => border.d).join('')

  const rotate = ROTATE_OVERRIDES[provinceName] ?? ISO_ROTATE
  const radians = (rotate * Math.PI) / 180
  const cos = Math.cos(radians)
  const sin = Math.sin(radians)

  let minPx = Number.POSITIVE_INFINITY
  let minPy = Number.POSITIVE_INFINITY
  let maxPx = Number.NEGATIVE_INFINITY
  let maxPy = Number.NEGATIVE_INFINITY
  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY

  const visit = (coords: unknown) => {
    if (!Array.isArray(coords)) return
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      const projected = projection([coords[0], coords[1]])
      if (!projected) return
      if (projected[0] < minPx) minPx = projected[0]
      if (projected[0] > maxPx) maxPx = projected[0]
      if (projected[1] < minPy) minPy = projected[1]
      if (projected[1] > maxPy) maxPy = projected[1]
      return
    }
    for (const child of coords) visit(child)
  }

  for (const geometry of framingGeometries) visit((geometry as { coordinates: unknown }).coordinates)
  if (!Number.isFinite(minPx)) return null

  const centerPx = (minPx + maxPx) / 2
  const centerPy = (minPy + maxPy) / 2
  const transform = (projected: [number, number]) => {
    const dx = projected[0] - centerPx
    const dy = projected[1] - centerPy
    return [dx * cos - dy * sin, (dx * sin + dy * cos) * ISO_SQUASH] as [number, number]
  }

  const visitTransform = (coords: unknown) => {
    if (!Array.isArray(coords)) return
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      const projected = projection([coords[0], coords[1]])
      if (!projected) return
      const [x, y] = transform(projected)
      if (x < minX) minX = x
      if (x > maxX) maxX = x
      if (y < minY) minY = y
      if (y > maxY) maxY = y
      return
    }
    for (const child of coords) visitTransform(child)
  }
  for (const geometry of framingGeometries) visitTransform((geometry as { coordinates: unknown }).coordinates)

    // Dinding digambar sebagai offset piksel setelah transform, jadi ruang yang
  // dialokasikan juga harus dalam piksel (bukan diskalakan dua kali).
  const wall = WALL_LAYERS * WALL_STEP
  const contentWidth = width * 0.82
  const contentHeight = height * 0.84 - wall
  const scale = Math.min(contentWidth / (maxX - minX), contentHeight / (maxY - minY))
  const tx = width / 2 - ((minX + maxX) / 2) * scale
  const ty = height / 2 - ((minY + maxY) / 2) * scale - wall / 2 + 6

  const matrix: IsoMatrix = [
    scale * cos,
    scale * sin * ISO_SQUASH,
    -scale * sin,
    scale * cos * ISO_SQUASH,
    tx - scale * (cos * centerPx - sin * centerPy),
    ty - scale * ((sin * centerPx + cos * centerPy) * ISO_SQUASH),
  ]

  const shadowCx = width / 2
  const shadowCy = ty + maxY * scale + wall / 2
  const shadowRx = ((maxX - minX) * scale) / 2.15
  const shadowRy = Math.max(12, (maxY - minY) * scale * 0.18)
  const kmPerPx = 6371 / (projection.scale() * scale)

  return {
    matrix,
    provincePath,
    borders,
    borderMesh,
    shadow: { cx: shadowCx, cy: shadowCy, rx: shadowRx, ry: shadowRy },
    kmPerPx,
    rotate,
    project: (lon: number, lat: number) => {
      const projected = projection([lon, lat])
      if (!projected) return null
      return applyMatrix(matrix, projected[0], projected[1])
    },
  }
}

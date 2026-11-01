import { useEffect, useMemo, useRef, useState } from 'react'
import type { ProvinceFeature } from './lib/map-data'
import { RISK_LEVELS } from './lib/risk'
import type { RiskLevel } from './types/geojson'

// Pratinjau peta sebagai SVG statis: proyeksi equirectangular sederhana dari
// GeoJSON provinsi. Tanpa MapLibre; tanpa menahan gulir halaman.
const WIDTH = 1000
const PADDING = 0.04
const LEVELS: RiskLevel[] = [1, 2, 3, 4]

type Ring = number[][]
type Bounds = { lonMin: number; lonMax: number; latMin: number; latMax: number }
type Box = { x1: number; y1: number; x2: number; y2: number }

export type MapPreviewFeature = { name: string; level: RiskLevel; drivers: string[] }

// Cincin luar saja: cukup untuk siluet provinsi dan jauh lebih ringan.
function outerRings(feature: ProvinceFeature): Ring[] {
  const geometry = feature.geometry as unknown as { type: string; coordinates: unknown }
  if (geometry.type === 'Polygon') {
    const rings = geometry.coordinates as Ring[]
    return Array.isArray(rings) && Array.isArray(rings[0]) ? [rings[0]] : []
  }
  if (geometry.type === 'MultiPolygon') {
    const polygons = geometry.coordinates as Ring[][]
    if (!Array.isArray(polygons)) return []
    return polygons.map((polygon) => polygon[0]).filter((ring): ring is Ring => Array.isArray(ring))
  }
  return []
}

// Bounding box seluruh provinsi, dilebihkan 4% agar tidak menyentuh tepi.
function collectBounds(features: ProvinceFeature[]): Bounds | null {
  let minLon = Number.POSITIVE_INFINITY
  let maxLon = Number.NEGATIVE_INFINITY
  let minLat = Number.POSITIVE_INFINITY
  let maxLat = Number.NEGATIVE_INFINITY
  for (const feature of features) {
    for (const ring of outerRings(feature)) {
      for (const point of ring) {
        if (!Array.isArray(point)) continue
        const lon = point[0]
        const lat = point[1]
        if (typeof lon !== 'number' || typeof lat !== 'number') continue
        if (lon < minLon) minLon = lon
        if (lon > maxLon) maxLon = lon
        if (lat < minLat) minLat = lat
        if (lat > maxLat) maxLat = lat
      }
    }
  }
  if (!Number.isFinite(minLon) || !Number.isFinite(minLat)) return null
  const lonPad = (maxLon - minLon) * PADDING
  const latPad = (maxLat - minLat) * PADDING
  return { lonMin: minLon - lonPad, lonMax: maxLon + lonPad, latMin: minLat - latPad, latMax: maxLat + latPad }
}

function fillFor(feature: ProvinceFeature): string {
  const level = feature.properties.level as RiskLevel | undefined
  if (!feature.properties.has_data || !level) return 'var(--paper-map-nodata)'
  return `var(${RISK_LEVELS[level].colorToken})`
}

// Titik laut terdekat: cari arah offset yang tidak masuk kotak provinsi mana pun.
function findSeaAnchor(center: { x: number; y: number }, boxes: Box[], height: number) {
  const distance = Math.min(WIDTH, height) * 0.13
  const directions: Array<[number, number]> = [[1, -0.55], [1, 0], [0.6, -1], [-1, -0.5], [-1, 0], [1, 0.7], [-0.7, 1], [0, 1]]
  const marginX = WIDTH * 0.13
  const marginY = height * 0.18
  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
  let fallback = { x: center.x, y: center.y }
  for (const [dx, dy] of directions) {
    const candidate = {
      x: clamp(center.x + dx * distance, marginX, WIDTH - marginX),
      y: clamp(center.y + dy * distance, marginY, height - marginY),
    }
    if (dx === 1 && dy === -0.55) fallback = candidate
    const clearance = Math.min(WIDTH, height) * 0.05
    const inside = boxes.some((box) => candidate.x >= box.x1 - clearance && candidate.x <= box.x2 + clearance && candidate.y >= box.y1 - clearance && candidate.y <= box.y2 + clearance)
    if (!inside) return candidate
  }
  return fallback
}

export function MapPreview({ provinces, featured }: { provinces: ProvinceFeature[] | null; featured: MapPreviewFeature | null }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const drawing = useMemo(() => {
    if (!provinces || provinces.length === 0) return null
    const bounds = collectBounds(provinces)
    if (!bounds) return null
    const height = Math.round(WIDTH * ((bounds.latMax - bounds.latMin) / (bounds.lonMax - bounds.lonMin)))
    const lonSpan = bounds.lonMax - bounds.lonMin
    const latSpan = bounds.latMax - bounds.latMin
    const project = (lon: number, lat: number) => ({
      x: ((lon - bounds.lonMin) / lonSpan) * WIDTH,
      y: ((bounds.latMax - lat) / latSpan) * height,
    })

    const shapes: Array<{ id: string; path: string; fill: string; name: string; box: Box }> = []
    for (const feature of provinces) {
      const rings = outerRings(feature).map((ring) => {
        const points: Array<{ x: number; y: number }> = []
        for (const point of ring) {
          if (!Array.isArray(point)) continue
          const lon = point[0]
          const lat = point[1]
          if (typeof lon !== 'number' || typeof lat !== 'number') continue
          points.push(project(lon, lat))
        }
        return points
      })
      const path = rings
        .map((points) => (points.length === 0 ? '' : `${points.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join('')}Z`))
        .filter(Boolean)
        .join('')
      const allPoints = rings.flat()
      if (path === '' || allPoints.length === 0) continue
      const box = allPoints.reduce<Box>(
        (acc, point) => ({
          x1: Math.min(acc.x1, point.x),
          y1: Math.min(acc.y1, point.y),
          x2: Math.max(acc.x2, point.x),
          y2: Math.max(acc.y2, point.y),
        }),
        { x1: Number.POSITIVE_INFINITY, y1: Number.POSITIVE_INFINITY, x2: Number.NEGATIVE_INFINITY, y2: Number.NEGATIVE_INFINITY },
      )
      shapes.push({
        id: String(feature.properties.shape_id ?? feature.properties.province),
        path,
        fill: fillFor(feature),
        name: feature.properties.province,
        box,
      })
    }

    const target = featured ? shapes.find((shape) => shape.name === featured.name) : undefined
    let pin: { centerX: number; centerY: number; anchorX: number; anchorY: number } | null = null
    if (target) {
      const centerX = (target.box.x1 + target.box.x2) / 2
      const centerY = (target.box.y1 + target.box.y2) / 2
      const anchor = findSeaAnchor({ x: centerX, y: centerY }, shapes.map((shape) => shape.box), height)
      pin = { centerX, centerY, anchorX: anchor.x, anchorY: anchor.y }
    }

    return { height, shapes, pin }
  }, [provinces, featured])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    const onDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !wrapRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  if (!drawing) return null

  const drivers = (featured?.drivers ?? []).slice(0, 2)

  return (
    <div className="lp-map" ref={wrapRef} style={{ aspectRatio: `${WIDTH} / ${drawing.height}` }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${drawing.height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Peta risiko Indonesia: provinsi diwarnai menurut level risiko untuk periode yang dipilih"
      >
        {drawing.shapes.map((shape) => (
          <path key={shape.id} d={shape.path} fill={shape.fill} stroke="var(--paper-map-line)" strokeWidth="1" strokeLinejoin="round" />
        ))}
        {drawing.pin && (
          <>
            <line x1={drawing.pin.centerX} y1={drawing.pin.centerY} x2={drawing.pin.anchorX} y2={drawing.pin.anchorY} stroke="var(--paper-line-strong)" strokeWidth="1" />
            <circle cx={drawing.pin.centerX} cy={drawing.pin.centerY} r="2.5" fill="var(--paper-text)" />
          </>
        )}
      </svg>

      {drawing.pin && featured && (
        <div
          className="lp-pin-wrap"
          style={{ left: `${(drawing.pin.anchorX / WIDTH) * 100}%`, top: `${(drawing.pin.anchorY / drawing.height) * 100}%` }}
        >
          <button
            type="button"
            className="lp-pin"
            aria-expanded={open}
            aria-label={`${featured.name}, ${RISK_LEVELS[featured.level].label}. Tampilkan faktor pendorong`}
            onPointerEnter={() => setOpen(true)}
            onPointerLeave={() => setOpen(false)}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            onClick={() => setOpen((current) => !current)}
          >
            <span>{featured.name}</span>
            <span className="lp-pin-level" style={{ background: `var(${RISK_LEVELS[featured.level].colorToken})` }}>
              <span className="level-bars" aria-hidden="true">
                {LEVELS.map((bar) => <i key={bar} className={bar <= featured.level ? 'filled' : ''} />)}
              </span>
              {RISK_LEVELS[featured.level].label}
            </span>
          </button>

          {open && (
            <div className="lp-pin-pop" role="status">
              <ul>
                {drivers.map((driver) => <li key={driver}>{driver}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import { memo, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { select as d3Select } from 'd3-selection'
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from 'd3-zoom'
import type { FeatureCollection, Geometry, MultiPolygon, Polygon } from 'geojson'
import { HORIZONS, type HorizonKey } from './lib/horizons'
import { loadKabupatenGeojson } from './lib/map-data'
import { RISK_LEVELS, riskColor } from './lib/risk'
import {
  ISO_SQUASH,
  WALL_LAYERS,
  WALL_STEP,
  buildLayout,
  dropTinyParts,
  poleOf,
  simplifyGeometry,
} from './lib/iso'
import type { KabupatenProperties, ProvinceProperties, RiskLevel } from './types/geojson'

type DioramaProperties = KabupatenProperties & {
  kabupaten: string
  provinsi: string
  display_level?: RiskLevel
}
type DioramaCollection = FeatureCollection<Polygon | MultiPolygon, DioramaProperties>
type DioramaFeature = DioramaCollection['features'][number]
type Disc = {
  kode: string
  name: string
  level: RiskLevel
  hotspot: number
  coverage: number
  x: number
  y: number
  r: number
  rank: number
}

type Props = {
  province: { properties: ProvinceProperties; geometry: Geometry }
  horizon: HorizonKey
  generatedAt?: string
  closing?: boolean
  onClose: () => void
  onHorizonChange: (horizon: HorizonKey) => void
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function coverageOf(row: DioramaFeature | null): number {
  return clamp(row?.properties.cakupan_pct ?? 0, 0, 100)
}

function useCountUp(target: number, duration = 500): number {
  const [value, setValue] = useState(prefersReducedMotion() ? target : 0)
  useEffect(() => {
    if (prefersReducedMotion()) {
      queueMicrotask(() => setValue(target))
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - progress) ** 3
      setValue(target * eased)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])
  return value
}

const RiskDisc = memo(function RiskDisc({ disc, selected, hovered, index, zoomed, onHover, onLeave, onSelect }: {
  disc: Disc
  selected: boolean
  hovered: boolean
  index: number
  zoomed: boolean
  onHover: (kode: string) => void
  onLeave: () => void
  onSelect: (kode: string) => void
}) {
  const lift = selected ? 6 : hovered ? 4 : 0
  const color = riskColor(disc.level)
  const radius = disc.rank >= 10 && zoomed ? 8 : disc.r
  const thickness = 5
  const strokeWidth = 1.5
  const ringWidth = 2.5
  const ringGap = 7
  return (
    <g className="iso-disc-anim" style={{ animationDelay: `${Math.min(index, 9) * 30}ms` }}>
      <g className="iso-disc-scale">
      <g
        className={`iso-disc${selected ? ' is-selected' : ''}${hovered ? ' is-hovered' : ''}`}
        data-kode={disc.kode}
        style={{ transform: `translateY(${-lift}px)` }}
        tabIndex={0}
        role="button"
        aria-label={`${disc.name}, ${RISK_LEVELS[disc.level].label}, ${disc.hotspot} hotspot 72 jam`}
        onPointerEnter={() => onHover(disc.kode)}
        onPointerLeave={onLeave}
        onFocus={() => onHover(disc.kode)}
        onBlur={onLeave}
        onMouseUp={() => onSelect(disc.kode)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onSelect(disc.kode)
          }
        }}
      >
        <ellipse cx={disc.x} cy={disc.y + thickness} rx={radius} ry={radius * ISO_SQUASH} fill="rgba(20,20,20,.16)" />
        <ellipse cx={disc.x} cy={disc.y + thickness / 2} rx={radius} ry={radius * ISO_SQUASH} fill="rgba(20,20,20,.2)" />
        <ellipse className="iso-disc-top" cx={disc.x} cy={disc.y} rx={radius} ry={radius * ISO_SQUASH} fill={color} stroke="#ffffff" strokeWidth={strokeWidth} />
        {selected && (
          <ellipse className="iso-ring" cx={disc.x} cy={disc.y} rx={radius + ringGap} ry={(radius + ringGap) * ISO_SQUASH} fill="none" stroke="var(--accent)" strokeWidth={ringWidth} />
        )}
      </g>
      </g>
    </g>
  )
})

const HitPath = memo(function HitPath({ kode, d, onHover }: {
  kode: string
  d: string
  onHover: (kode: string | null) => void
}) {
  return (
    <path
      d={d}
      fill="rgba(0,0,0,0)"
      pointerEvents="all"
      className="iso-hit"
      data-kode={kode}
      onPointerEnter={() => onHover(kode)}
      onPointerLeave={() => onHover(null)}
    />
  )
})

const BorderMesh = memo(function BorderMesh({ d }: { d: string }) {
  return (
    <>
      <path d={d} fill="none" stroke="var(--iso-border-under)" strokeWidth={2.2} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <path d={d} fill="none" stroke="#ffffff" strokeWidth={1.5} strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </>
  )
})

export function ProvinceDiorama({ province, horizon, generatedAt, closing = false, onClose, onHorizonChange }: Props) {
  const mapCardRef = useRef<HTMLDivElement | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const zoomGroupRef = useRef<SVGGElement | null>(null)
  const legendRef = useRef<HTMLDivElement | null>(null)
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const zoomStateRef = useRef<ZoomTransform>(zoomIdentity)
  const pendingSelectRef = useRef<{ kode: string | null; x: number; y: number; dragged: boolean } | null>(null)
  const rowsRef = useRef<HTMLDivElement | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [kabupaten, setKabupaten] = useState<DioramaCollection | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [selectedKode, setSelectedKode] = useState<string | null>(null)
  const [hoverKode, setHoverKode] = useState<string | null>(null)
  const [tab, setTab] = useState<'risiko' | 'hotspot'>('risiko')
  const [zoomState, setZoomState] = useState<ZoomTransform>(zoomIdentity)
  useEffect(() => { zoomStateRef.current = zoomState }, [zoomState])
  const [zoomed, setZoomed] = useState(false)
  const [legendOpen, setLegendOpen] = useState(false)

  useEffect(() => {
    const node = mapCardRef.current
    if (!node) return
    const observer = new ResizeObserver(() => setSize({ width: node.clientWidth, height: node.clientHeight }))
    observer.observe(node)
    setSize({ width: node.clientWidth, height: node.clientHeight })
    return () => observer.disconnect()
  }, [])


  const zoomBy = useCallback((factor: number) => {
    const svg = svgRef.current
    const behavior = zoomBehaviorRef.current
    if (!svg || !behavior) return
    d3Select(svg).call(behavior.scaleBy, factor)
  }, [])

  const panBy = useCallback((dx: number, dy: number) => {
    const svg = svgRef.current
    const behavior = zoomBehaviorRef.current
    if (!svg || !behavior) return
    d3Select(svg).call(behavior.translateBy, dx, dy)
  }, [])

  const resetZoom = useCallback(() => {
    const svg = svgRef.current
    const behavior = zoomBehaviorRef.current
    if (!svg || !behavior) return
    const selection = d3Select(svg)
    if (prefersReducedMotion()) {
      selection.call(behavior.transform, zoomIdentity)
      return
    }
    const from = zoomStateRef.current
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / 300)
      const eased = 1 - (1 - progress) ** 3
      const k = from.k + (1 - from.k) * eased
      const x = from.x * (1 - eased)
      const y = from.y * (1 - eased)
      selection.call(behavior.transform, zoomIdentity.translate(x, y).scale(k))
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [])

  useEffect(() => {
    let cancelled = false
    void loadKabupatenGeojson(province.properties.province)
      .then((data) => {
        if (cancelled) return
        setKabupaten(data as DioramaCollection)
      })
      .catch(() => {
        if (!cancelled) setLoadError(true)
      })
    return () => { cancelled = true }
  }, [province.properties.province])

  const baseLevel = province.properties.level_d1 ?? province.properties.level ?? 1
  const horizonLevel = (province.properties as Record<string, unknown>)[`level_${horizon}`] as number | undefined
  const levelDelta = (horizonLevel ?? baseLevel) - baseLevel

  const displayCollection = useMemo<DioramaCollection | null>(() => {
    if (!kabupaten) return null
    return {
      ...kabupaten,
      features: kabupaten.features.map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          display_level: feature.properties.level
            ? clamp(feature.properties.level + levelDelta, 1, 4) as RiskLevel
            : undefined,
        },
        geometry: simplifyGeometry(dropTinyParts(feature.geometry, 0.01), 0.015),
      })),
    }
  }, [kabupaten, levelDelta])

  const affectedRows = useMemo(() => {
    if (!displayCollection) return []
    return displayCollection.features
      .filter((feature) => feature.properties.has_data && feature.properties.display_level)
      .sort((a, b) => {
        const levelDiff = (b.properties.display_level ?? 0) - (a.properties.display_level ?? 0)
        if (levelDiff !== 0) return levelDiff
        return (b.properties.hotspot_72h ?? 0) - (a.properties.hotspot_72h ?? 0)
      })
  }, [displayCollection])

  const effectiveSelectedKode = selectedKode && affectedRows.some((row) => row.properties.kode === selectedKode) ? selectedKode : null
  const selectedRow = useMemo(
    () => affectedRows.find((row) => row.properties.kode === effectiveSelectedKode) ?? null,
    [affectedRows, effectiveSelectedKode],
  )
  const maxLevel = useMemo(
    () => affectedRows.reduce((max, row) => Math.max(max, row.properties.display_level ?? 0), 0) as RiskLevel,
    [affectedRows],
  )
  const summaryHotspot = affectedRows.reduce((sum, row) => sum + (row.properties.hotspot_72h ?? 0), 0)
  const animatedCount = useCountUp(affectedRows.length)
  const animatedHotspot = useCountUp(summaryHotspot)
  const selectedCoverage = useCountUp(coverageOf(selectedRow))
  const selectedHotspot = useCountUp(selectedRow?.properties.hotspot_72h ?? 0)

  const layout = useMemo(() => {
    if (!displayCollection) return null
    return buildLayout(province.geometry, displayCollection, size.width, size.height, province.properties.province)
  }, [displayCollection, province.geometry, province.properties.province, size.width, size.height])

  useEffect(() => {
    const svg = svgRef.current
    const group = zoomGroupRef.current
    if (!svg || !group || size.width <= 0 || size.height <= 0) return
    let frame = 0
    let pending: ZoomTransform | null = null
    const apply = () => {
      frame = 0
      const transform = pending
      pending = null
      if (!transform) return
      group.setAttribute('transform', `translate(${transform.x} ${transform.y}) scale(${transform.k})`)
      group.style.setProperty('--inv-scale', String(1 / transform.k))
      zoomStateRef.current = transform
    }
    const schedule = (transform: ZoomTransform) => {
      pending = transform
      if (frame === 0) frame = requestAnimationFrame(apply)
    }
    const flush = () => {
      if (frame !== 0) {
        cancelAnimationFrame(frame)
        frame = 0
      }
      apply()
    }
    const behavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 4])
      .extent([[0, 0], [size.width, size.height]])
      .translateExtent([
        [-size.width * 0.25, -size.height * 0.25],
        [size.width * 1.25, size.height * 1.25],
      ])
      .filter((event) => {
        if (event.type === 'wheel') return !event.ctrlKey
        return !event.button
      })
      .on('start', () => {
        svg.classList.add('is-gesturing')
        group.classList.add('is-gesturing')
        mapCardRef.current?.classList.add('is-gesturing')
      })
      .on('end', () => {
        flush()
        svg.classList.remove('is-gesturing')
        group.classList.remove('is-gesturing')
        mapCardRef.current?.classList.remove('is-gesturing')
        const transform = zoomStateRef.current
        setZoomState(transform)
        setZoomed(transform.k > 2)
      })
      .on('zoom', (event) => schedule(event.transform))
    zoomBehaviorRef.current = behavior
    const selection = d3Select(svg)
    selection.call(behavior)
    selection.call(behavior.transform, zoomStateRef.current)
    group.setAttribute('transform', `translate(${zoomStateRef.current.x} ${zoomStateRef.current.y}) scale(${zoomStateRef.current.k})`)
    group.style.setProperty('--inv-scale', String(1 / zoomStateRef.current.k))
    return () => {
      if (frame) cancelAnimationFrame(frame)
      selection.on('.zoom', null)
      zoomBehaviorRef.current = null
    }
  }, [size.width, size.height, layout])

  const discs = useMemo<Disc[]>(() => {
    if (!layout) return []
    const ranked = [...affectedRows].sort((a, b) => (b.properties.hotspot_72h ?? 0) - (a.properties.hotspot_72h ?? 0))
    const maxHotspot = Math.max(1, ...ranked.map((row) => row.properties.hotspot_72h ?? 0))
    const items: Disc[] = []
    for (const [index, row] of ranked.entries()) {
      const pole = poleOf(row.geometry)
      const point = pole ? layout.project(pole.lon, pole.lat) : null
      if (!pole || !point) continue
      const edge = layout.project(pole.lon + pole.distance, pole.lat)
      const maxRadius = edge ? Math.abs(edge[0] - point[0]) : 34
      const baseRadius = index < 10 ? 10 + 24 * ((row.properties.hotspot_72h ?? 0) / maxHotspot) : 4.5
      items.push({
        kode: row.properties.kode,
        name: row.properties.kabupaten,
        level: (row.properties.display_level ?? 1) as RiskLevel,
        hotspot: row.properties.hotspot_72h ?? 0,
        coverage: coverageOf(row),
        x: point[0],
        y: point[1],
        r: Math.max(4, Math.min(34, baseRadius, Math.max(6, maxRadius * 0.85))),
        rank: index,
      })
    }
    for (let iteration = 0; iteration < 4; iteration += 1) {
      for (let i = 0; i < Math.min(10, items.length); i += 1) {
        for (let j = i + 1; j < Math.min(10, items.length); j += 1) {
          const distance = Math.hypot(items[i].x - items[j].x, items[i].y - items[j].y)
          if (distance < items[i].r + items[j].r + 4) {
            items[i] = { ...items[i], r: Math.max(6, items[i].r * 0.85) }
            items[j] = { ...items[j], r: Math.max(6, items[j].r * 0.85) }
          }
        }
      }
    }
    return items
  }, [affectedRows, layout])

  const selectedDisc = discs.find((disc) => disc.kode === effectiveSelectedKode) ?? null
  const selectedScreen = useMemo(() => selectedDisc
    ? {
        x: zoomState.x + selectedDisc.x * zoomState.k,
        y: zoomState.y + selectedDisc.y * zoomState.k,
        r: selectedDisc.r,
      }
    : null, [selectedDisc, zoomState])

  const callout = useMemo(() => {
    if (!selectedDisc || !selectedScreen || size.width <= 0) return null
    const { x: sx, y: sy, r } = selectedScreen
    if (sx < -r || sy < -r || sx > size.width + r || sy > size.height + r) return null
    const width = Math.min(size.width < 500 ? 180 : 220, size.width - 16)
    const height = 92
    const gap = 18
    const others = discs
      .filter((disc) => disc.kode !== selectedDisc.kode)
      .map((disc) => ({
        x: zoomState.x + disc.x * zoomState.k,
        y: zoomState.y + disc.y * zoomState.k,
        r: disc.r,
      }))
    const candidates = [
      { placement: 'above' as const, left: sx - width / 2, top: sy - r * ISO_SQUASH - gap - height },
      { placement: 'below' as const, left: sx - width / 2, top: sy + r * ISO_SQUASH + gap },
      { placement: 'right' as const, left: sx + r + gap, top: sy - height / 2 },
      { placement: 'left' as const, left: sx - r - gap - width, top: sy - height / 2 },
    ]
    let best = candidates[0]
    let bestScore = Number.POSITIVE_INFINITY
    for (const candidate of candidates) {
      const rect = {
        x1: candidate.left - 4,
        y1: candidate.top - 4,
        x2: candidate.left + width + 4,
        y2: candidate.top + height + 4,
      }
      let score = 0
      if (rect.x1 < 8 || rect.y1 < 8 || rect.x2 > size.width - 8 || rect.y2 > size.height - 8) score += 20
      for (const other of others) {
        if (other.x > rect.x1 - other.r && other.x < rect.x2 + other.r && other.y > rect.y1 - other.r && other.y < rect.y2 + other.r) {
          score += 1
        }
      }
      if (score < bestScore) {
        bestScore = score
        best = candidate
      }
    }
    return {
      left: clamp(best.left, 8, Math.max(8, size.width - width - 8)),
      top: clamp(best.top, 8, Math.max(8, size.height - height - 8)),
      width,
      placement: best.placement,
    }
  }, [selectedDisc, selectedScreen, discs, zoomState, size.width, size.height])

  const labels = useMemo(() => {
    if (zoomState.k <= 2) return []
    const placed: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
    const items: Array<{ kode: string; name: string; x: number; y: number }> = []
    for (const disc of discs) {
      if (disc.kode === effectiveSelectedKode) continue
      const sx = zoomState.x + disc.x * zoomState.k
      const sy = zoomState.y + disc.y * zoomState.k
      if (sx < 0 || sy < 0 || sx > size.width || sy > size.height) continue
      const text = disc.name
      const width = text.length * 5.4 + 4
      let x = sx + disc.r + 6
      if (x + width > size.width - 6) x = sx - disc.r - 6 - width
      if (x < 6) continue
      const y = sy - 5
      const rect = { x1: x - 2, y1: y - 8, x2: x + width + 2, y2: y + 4 }
      if (placed.some((item) => !(rect.x2 < item.x1 || rect.x1 > item.x2 || rect.y2 < item.y1 || rect.y1 > item.y2))) continue
      placed.push(rect)
      items.push({ kode: disc.kode, name: text, x, y })
    }
    return items
  }, [discs, zoomState, size.width, size.height, effectiveSelectedKode])

  const scaleBar = useMemo(() => {
    if (!layout || !Number.isFinite(layout.kmPerPx) || layout.kmPerPx <= 0) return null
    const kmPerPx = layout.kmPerPx / zoomState.k
    let km = 25
    for (const candidate of [25, 50, 100, 200, 500, 1000]) {
      if (candidate / kmPerPx <= 110) km = candidate
    }
    return { km, width: clamp(km / kmPerPx, 18, 110) }
  }, [layout, zoomState.k])

  const select = useCallback((kode: string) => setSelectedKode(kode), [])
  const clearSelection = useCallback(() => setSelectedKode(null), [])
  const hover = useCallback((kode: string | null) => setHoverKode(kode), [])
  const clearHover = useCallback(() => setHoverKode(null), [])

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onDown = (event: MouseEvent) => {
      const target = event.target as Element | null
      const disc = target?.closest?.('.iso-disc')
      const hit = target?.closest?.('.iso-hit')
      const kode = disc?.getAttribute('data-kode') ?? hit?.getAttribute('data-kode') ?? null
      pendingSelectRef.current = { kode, x: event.clientX, y: event.clientY, dragged: false }
    }
    svg.addEventListener('mousedown', onDown, true)
    return () => svg.removeEventListener('mousedown', onDown, true)
  }, [layout])

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const pending = pendingSelectRef.current
      if (pending && Math.hypot(event.clientX - pending.x, event.clientY - pending.y) > 4) {
        pending.dragged = true
      }
    }
    const onUp = () => {
      const pending = pendingSelectRef.current
      pendingSelectRef.current = null
      if (!pending || pending.dragged) return
      setSelectedKode(pending.kode)
    }
    window.addEventListener('mousemove', onMove, true)
    window.addEventListener('mouseup', onUp, true)
    return () => {
      window.removeEventListener('mousemove', onMove, true)
      window.removeEventListener('mouseup', onUp, true)
    }
  }, [])

  const handleMapKeyDown = useCallback((event: ReactKeyboardEvent<HTMLDivElement>) => {
    const step = 48
    if (event.key === 'Escape') {
      setSelectedKode(null)
      return
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      panBy(step, 0)
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      panBy(-step, 0)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      panBy(0, step)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      panBy(0, -step)
    } else if (event.key === '+' || event.key === '=') {
      event.preventDefault()
      zoomBy(1.35)
    } else if (event.key === '-' || event.key === '_') {
      event.preventDefault()
      zoomBy(1 / 1.35)
    } else if (event.key === '0') {
      event.preventDefault()
      resetZoom()
    }
  }, [panBy, resetZoom, zoomBy])

  useEffect(() => {
    if (!legendOpen) return
    const onDown = (event: PointerEvent) => {
      if (!legendRef.current?.contains(event.target as Node)) setLegendOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLegendOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [legendOpen])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelectedKode(null)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const container = rowsRef.current
    if (!effectiveSelectedKode || !container) return
    if (container.scrollHeight <= container.clientHeight + 4) return
    const node = container.querySelector<HTMLElement>(`[data-kode="${effectiveSelectedKode}"]`)
    if (!node) return
    const view = container.getBoundingClientRect()
    const item = node.getBoundingClientRect()
    if (item.top >= view.top && item.bottom <= view.bottom) return
    const top = container.scrollTop + (item.top - view.top) - view.height / 2 + item.height / 2
    container.scrollTo({ top: Math.max(0, top), behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
  }, [effectiveSelectedKode])

  const tabs = selectedRow?.properties.hotspot_72h === undefined ? ['risiko'] as const : ['risiko', 'hotspot'] as const
  const activeTab = tab === 'hotspot' && selectedRow?.properties.hotspot_72h !== undefined ? 'hotspot' : 'risiko'
  const horizonIndex = Math.max(0, HORIZONS.findIndex((item) => item.key === horizon))
  const tabIndex = activeTab === 'hotspot' ? 1 : 0

  return (
    <section className={`diorama${closing ? ' is-closing' : ''}`} aria-label={`Diorama risiko provinsi ${province.properties.province}`}>
      <header className="diorama-head">
        <button type="button" className="diorama-back" onClick={onClose}>← Peta</button>
        <div className="diorama-headline">
          <h1>{province.properties.province}</h1>
          <span className="diorama-sample">Data contoh</span>
          <div className="diorama-chips">
            <span className="diorama-chip diorama-chip-level" style={{ ['--chip' as string]: `var(${RISK_LEVELS[(maxLevel || 1) as RiskLevel].colorToken})` }}>
              <i aria-hidden="true" />{RISK_LEVELS[(maxLevel || 1) as RiskLevel].label}
            </span>
            <span className="diorama-chip"><b>{Math.round(animatedCount)}</b> kabupaten terdampak</span>
            <span className="diorama-chip"><b>{Math.round(animatedHotspot).toLocaleString('id-ID')}</b> hotspot 72 jam</span>
          </div>
        </div>
        <fieldset className="horizon-control diorama-horizon">
          <legend className="sr-only">PERIODE</legend>
          <div className="horizon-options" style={{ ['--pill' as string]: horizonIndex }}>
            <span className="seg-pill" aria-hidden="true" />
            {HORIZONS.map((item) => (
              <button className={`horizon-button${horizon === item.key ? ' is-selected' : ''}`} key={item.key} type="button" aria-pressed={horizon === item.key} onClick={() => onHorizonChange(item.key)}>
                {item.label}
                <small>{new Date(Date.parse(generatedAt ?? '2026-10-30T00:00:00Z') + (HORIZONS.find((entry) => entry.key === item.key)?.offsetDays ?? 0) * 86400000).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', timeZone: 'Asia/Jakarta' }).toUpperCase()}</small>
              </button>
            ))}
          </div>
        </fieldset>
      </header>

      <div className="diorama-body">
        <div className="diorama-main">
          <div
            className="diorama-map-wrap"
            ref={mapCardRef}
            tabIndex={0}
            onKeyDown={handleMapKeyDown}
          >
            {layout && size.width > 0 && (
              <svg ref={svgRef} className="iso-svg" viewBox={`0 0 ${size.width} ${size.height}`} role="application" aria-label={`Diorama isometrik kabupaten di ${province.properties.province}`}>
                <defs>
                  <radialGradient id="iso-shadow">
                    <stop offset="0" stopColor="rgba(20,20,20,.09)" />
                    <stop offset="1" stopColor="rgba(20,20,20,0)" />
                  </radialGradient>
                </defs>
                <rect width={size.width} height={size.height} fill="transparent"  />
                <g className="iso-zoom" ref={zoomGroupRef}>
                <ellipse className="iso-ground-shadow" cx={layout.shadow.cx} cy={layout.shadow.cy} rx={layout.shadow.rx} ry={layout.shadow.ry} fill="url(#iso-shadow)" />
                <g className="iso-slab">
                  <g className="iso-walls" aria-hidden="true">
                    {Array.from({ length: WALL_LAYERS }, (_, index) => (
                      <g key={index} transform={`translate(0 ${(WALL_LAYERS - index) * WALL_STEP})`}>
                        <g transform={`matrix(${layout.matrix.join(' ')})`}>
                          <path d={layout.provincePath} fill="var(--iso-wall)" />
                        </g>
                      </g>
                    ))}
                  </g>
                  <g transform={`matrix(${layout.matrix.join(' ')})`}>
                    <path d={layout.provincePath} fill="var(--iso-surface)" />
                    {layout.borders.map((border) => {
                      const hovered = hoverKode === border.kode
                      const selected = effectiveSelectedKode === border.kode
                      if (!hovered && !selected) return null
                      return <path key={`overlay-${border.kode}`} d={border.d} fill="rgba(20,20,20,.07)" pointerEvents="none" />
                    })}
                    {layout.borders.map((border) => (
                      <HitPath key={`hit-${border.kode}`} kode={border.kode} d={border.d} onHover={hover} />
                    ))}
                    <g pointerEvents="none">
                      <BorderMesh d={layout.borderMesh} />
                    </g>
                  </g>
                </g>
                {discs.filter((disc) => disc.rank < 10 || zoomed).map((disc, index) => (
                  <RiskDisc
                    key={disc.kode}
                    disc={disc}
                    index={index}
                    zoomed={zoomed}
                    selected={effectiveSelectedKode === disc.kode}
                    hovered={hoverKode === disc.kode}
                    onHover={hover}
                    onLeave={clearHover}
                    onSelect={select}
                   
                  />
                ))}
                </g>
                {labels.map((label) => (
                  <text key={label.kode} className="iso-label" x={label.x} y={label.y}>{label.name}</text>
                ))}
              </svg>
            )}

            <div className="iso-legend-wrap" ref={legendRef}>
              <button type="button" className="iso-legend-trigger" aria-expanded={legendOpen} onClick={() => setLegendOpen((open) => !open)}>
                <span className="iso-legend-dots" aria-hidden="true">
                  {[1, 2, 3, 4].map((level) => <i key={level} style={{ background: riskColor(level as RiskLevel) }} />)}
                </span>
                Legenda
              </button>
              {legendOpen && (
                <div className="iso-legend-panel" role="dialog" aria-label="Legenda piringan risiko">
                  <div className="iso-legend-levels">
                    {[1, 2, 3, 4].map((level) => (
                      <span key={level}><i style={{ background: riskColor(level as RiskLevel) }} aria-hidden="true" />{RISK_LEVELS[level as RiskLevel].label}</span>
                    ))}
                  </div>
                  <span className="iso-legend-size">Ukuran piringan = hotspot 72 jam</span>
                </div>
              )}
            </div>

            <p className="iso-disclaimer">Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.</p>
            {scaleBar && (
              <div className="iso-scale">
                <span className="iso-scale-bar" style={{ width: scaleBar.width }} aria-hidden="true" />
                <span>{scaleBar.km} km</span>
              </div>
            )}
            <div className="iso-zoom-controls" aria-label="Kontrol zoom peta">
              <button type="button" onClick={() => zoomBy(1.4)} aria-label="Perbesar peta">+</button>
              <button type="button" onClick={() => zoomBy(1 / 1.4)} aria-label="Perkecil peta">−</button>
              <button type="button" onClick={resetZoom} disabled={Math.abs(zoomState.k - 1) < 0.001 && Math.abs(zoomState.x) < 0.5 && Math.abs(zoomState.y) < 0.5} aria-label="Reset tampilan peta">↺</button>
            </div>

            {!displayCollection && !loadError && <div className="diorama-state" role="status">MEMUAT KABUPATEN...</div>}
            {loadError && <div className="diorama-state" role="alert">DATA KABUPATEN GAGAL DIMUAT.</div>}
            {!loadError && displayCollection && affectedRows.length === 0 && (
              <div className="iso-empty" role="status">Tidak ada kabupaten terdampak pada horizon ini</div>
            )}

            {selectedDisc && callout && (
              <div className={`iso-callout is-${callout.placement}`} style={{ left: callout.left, top: callout.top, width: callout.width }} role="status">
                <strong>{selectedDisc.name}</strong>
                <div className="iso-callout-value">{selectedCoverage.toFixed(1)}%<span>cakupan area berisiko</span></div>
                <span>{selectedDisc.hotspot} hotspot 72 jam</span>
              </div>
            )}
          </div>

          <section className="diorama-detail" aria-label={selectedRow ? `Detail ${selectedRow.properties.kabupaten}` : 'Detail kabupaten'}>
            <div className="diorama-detail-head">
              <div>
                <p className="eyebrow">KABUPATEN TERPILIH</p>
                <h2>{selectedRow ? selectedRow.properties.kabupaten : 'Belum ada pilihan'}</h2>
              </div>
              <div className="diorama-detail-actions">
                {selectedRow && <button type="button" className="diorama-clear" onClick={clearSelection}>Lepas pilihan</button>}
                {selectedRow && (
                  <div className="diorama-tabs" role="tablist" aria-label="Detail kabupaten" style={{ ['--pill' as string]: tabIndex, ['--pill-count' as string]: tabs.length }}>
                    <span className="seg-pill" aria-hidden="true" />
                    {tabs.map((item) => (
                      <button key={item} type="button" role="tab" aria-selected={activeTab === item} className={activeTab === item ? 'is-selected' : ''} onClick={() => setTab(item)}>
                        {item === 'risiko' ? 'Risiko' : 'Hotspot 72 jam'}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {!selectedRow ? (
              <p className="diorama-empty">Klik piringan atau area kabupaten untuk melihat detail. Tekan Esc atau klik area kosong untuk melepas pilihan.</p>
            ) : activeTab === 'risiko' ? (
              <>
                <div className="diorama-metrics">
                  <div><span className="eyebrow">CAKUPAN AREA BERISIKO</span><strong>{selectedCoverage.toFixed(1)}%</strong></div>
                  <div><span className="eyebrow">LEVEL</span><strong>{RISK_LEVELS[(selectedRow.properties.display_level ?? 1) as RiskLevel].label}</strong></div>
                  <div><span className="eyebrow">HOTSPOT 72 JAM</span><strong>{Math.round(selectedHotspot)}</strong></div>
                  <div><span className="eyebrow">SEL PEMANTAUAN</span><strong>{selectedRow.properties.n_sel ?? 0}</strong></div>
                  <div><span className="eyebrow">SEL PENUH</span><strong>{selectedRow.properties.n_sel_penuh ?? 0}</strong></div>
                  <div><span className="eyebrow">LUAS KABUPATEN</span><strong>{(selectedRow.properties.luas_kabupaten_ha ?? 0).toLocaleString('id-ID')} ha</strong></div>
                </div>
                <div className="diorama-detail-foot">
                  <span>Perkiraan luas terdampak</span>
                  <strong>{(selectedRow.properties.luas_terdampak_ha_min ?? 0).toLocaleString('id-ID')}–{(selectedRow.properties.luas_terdampak_ha_max ?? 0).toLocaleString('id-ID')} ha</strong>
                </div>
              </>
            ) : (
              <div className="diorama-metrics">
                <div><span className="eyebrow">HOTSPOT 72 JAM</span><strong>{Math.round(selectedHotspot)}</strong></div>
                <div><span className="eyebrow">SUMBER</span><strong>Deteksi satelit</strong></div>
                <div><span className="eyebrow">CATATAN</span><strong>Bukan konfirmasi kebakaran</strong></div>
              </div>
            )}
          </section>
        </div>

        <aside className="diorama-list" aria-label="Daftar kabupaten terdampak">
          <div className="diorama-list-head">
            <p className="eyebrow">KABUPATEN TERDAMPAK</p>
            <span>{affectedRows.length}</span>
          </div>
          <div className="diorama-rows" ref={rowsRef}>
            {affectedRows.length === 0 ? (
              <p className="diorama-empty">Tidak ada kabupaten terdampak pada horizon ini.</p>
            ) : (
              <ol className="diorama-rowlist">
                {affectedRows.map((row, index) => {
                  const level = (row.properties.display_level ?? 1) as RiskLevel
                  const coverage = coverageOf(row)
                  return (
                    <li key={row.properties.kode}>
                      <button
                        type="button"
                        data-kode={row.properties.kode}
                        style={{ ['--i' as string]: index }}
                        className={`diorama-row${effectiveSelectedKode === row.properties.kode ? ' is-selected' : ''}${hoverKode === row.properties.kode ? ' is-hovered' : ''}`}
                        onClick={() => select(row.properties.kode)}
                        onMouseEnter={() => hover(row.properties.kode)}
                        onMouseLeave={() => hover(null)}
                        onFocus={() => hover(row.properties.kode)}
                        onBlur={() => hover(null)}
                      >
                        <span className="diorama-row-dot" style={{ background: `var(${RISK_LEVELS[level].colorToken})` }} aria-hidden="true" />
                        <span className="diorama-row-name">{row.properties.kabupaten}</span>
                        <span className="diorama-row-bar" aria-hidden="true"><i style={{ width: `${coverage}%`, background: `var(${RISK_LEVELS[level].colorToken})` }} /></span>
                        <span className="diorama-row-value">{coverage.toFixed(1)}%</span>
                      </button>
                    </li>
                  )
                })}
              </ol>
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}

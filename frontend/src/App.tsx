import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { GeoJSONSource, Map as MapLibreMap, MapGeoJSONFeature, MapMouseEvent } from 'maplibre-gl'
import type { Geometry, Point } from 'geojson'
import { HORIZONS, type HorizonKey } from './lib/horizons'
import { loadMapBaseData, type ProvinceFeature, type ProvinceFeatureCollection } from './lib/map-data'
import { normalizeName, provinceSlug } from './lib/slug'
import type {
  DataMeta,
  HotspotFeatureCollection,
  KabupatenRiskRecord,
  ProvinceProperties,
  RiskLevel,
} from './types/geojson'
import { RISK_LEVELS, riskColor } from './lib/risk'
import { RiskLegend } from './Legend'
import { ProvinceDiorama } from './ProvinceDiorama'
import { MethodPage } from './MethodPage'
import { WilayahPage } from './WilayahPage'
import { RiwayatPage } from './RiwayatPage'
import { LandingPage } from './LandingPage'
import './App.css'

const PROVINCE_SOURCE = 'province-boundaries'
const PROVINCE_FILL = 'province-risk-fill'
const PROVINCE_EXTRUDE = 'province-risk-extrude'
const PROVINCE_LINE = 'province-boundary-line'
const PROVINCE_HOVER = 'province-hover-line'
const LAND_SHADOW = 'land-shadow'
const INDONESIA_LAND = 'indonesia-land'
const HOTSPOT_SOURCE = 'hotspot-observation-source'
const HOTSPOT_CIRCLE = 'hotspot-observation-circles'
const HOTSPOT_CLUSTER = 'hotspot-cluster-circles'
const HOTSPOT_CLUSTER_COUNT = 'hotspot-cluster-count'
const NATIONAL_BOUNDS: [[number, number], [number, number]] = [[94.5, -11.5], [141.5, 6.5]]
maplibregl.setWorkerUrl(new URL('maplibre-gl/dist/maplibre-gl-worker.mjs', import.meta.url).toString())
const levelNames = ['RENDAH', 'SEDANG', 'TINGGI', 'SANGAT TINGGI'] as const

type MapState = 'loading' | 'ready' | 'error'
type DataState = 'loading' | 'ready' | 'error'
type ProvinceHoverProperties = Pick<
  ProvinceProperties,
  'province' | 'shape_id' | 'level' | 'score' | 'has_data' | 'hotspot_72h' | 'kabupaten_terdampak'
>
type ProvinceHover = { properties: ProvinceHoverProperties; point: [number, number] }
type SelectedProvince = { properties: ProvinceProperties; geometry: Geometry }
type HotspotPulse = { id: string; x: number; y: number }

type MapLayers = {
  hotspots: HotspotFeatureCollection
  provinces: ProvinceFeatureCollection
  kabupatenIndex: KabupatenRiskRecord[]
}

function tokenValue(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim()
}

// Tile-free basemap: only a themed background. Indonesian land comes from
// the province GeoJSON layer added at runtime.
function basemapStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {},
    layers: [
      { id: 'theme-sea', type: 'background', paint: { 'background-color': '#00000000' } },
    ],
  }
}

// Solid land fill for Indonesian islands; color filled by repaintThemed().
function indonesiaLandStyle(): maplibregl.LayerSpecification {
  return {
    id: INDONESIA_LAND,
    type: 'fill',
    source: PROVINCE_SOURCE,
    paint: { 'fill-color': '#00000000' },
  }
}

function paintProvinceLayers(map: MapLibreMap) {
  const neutral = tokenValue('--map-neutral')
  const provinceFill = ['case', ['==', ['get', 'has_data'], true], ['match', ['get', 'level'], 1, riskColor(1), 2, riskColor(2), 3, riskColor(3), 4, riskColor(4), neutral], neutral] as never
  const extrudeColor = ['match', ['get', 'level'], 1, riskColor(1), 2, riskColor(2), 3, riskColor(3), 4, riskColor(4), neutral] as never
  const extrudeHeight = ['case',
    ['boolean', ['feature-state', 'hover'], false],
    ['match', ['get', 'level'], 1, 8000, 2, 14000, 3, 22000, 4, 30000, 0],
    ['match', ['get', 'level'], 1, 4000, 2, 10000, 3, 18000, 4, 26000, 0],
  ] as never
  map.setPaintProperty('theme-sea', 'background-color', tokenValue('--map-sea'))
  if (map.getLayer(INDONESIA_LAND)) map.setPaintProperty(INDONESIA_LAND, 'fill-color', tokenValue('--map-land'))
  if (map.getLayer(PROVINCE_FILL)) map.setPaintProperty(PROVINCE_FILL, 'fill-color', provinceFill)
  if (map.getLayer(PROVINCE_EXTRUDE)) {
    map.setPaintProperty(PROVINCE_EXTRUDE, 'fill-extrusion-color', extrudeColor)
    map.setPaintProperty(PROVINCE_EXTRUDE, 'fill-extrusion-height', extrudeHeight)
  }
  if (map.getLayer(PROVINCE_LINE)) map.setPaintProperty(PROVINCE_LINE, 'line-color', '#ffffff')
  if (map.getLayer(PROVINCE_HOVER)) {
    map.setPaintProperty(PROVINCE_HOVER, 'line-color', tokenValue('--text'))
    map.setPaintProperty(PROVINCE_HOVER, 'line-width', ['case', ['boolean', ['feature-state', 'selected'], false], 3.5, ['boolean', ['feature-state', 'hover'], false], 2.5, 0] as never)
  }
  if (map.getLayer(LAND_SHADOW)) map.setPaintProperty(LAND_SHADOW, 'line-color', 'rgba(20, 20, 20, 0.05)')
}

function riskLevelName(level: number) {
  return levelNames[Math.max(0, Math.min(levelNames.length - 1, level - 1))]
}

class DioramaErrorBoundary extends Component<{ children: ReactNode; onReset: () => void }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (this.state.failed) {
      return (
        <div className="diorama-error" role="alert">
          <p>Diorama gagal ditampilkan. Silakan kembali ke peta.</p>
          <button type="button" className="diorama-back" onClick={this.props.onReset}>← Peta</button>
        </div>
      )
    }
    return this.props.children
  }
}

function MapView({ layers, dataState, selectedProvince, externalHoverId, onMapReady, onSelectProvince, onHoverProvince }: {
  layers: MapLayers | null
  dataState: DataState
  selectedProvince: ProvinceHoverProperties | null
  externalHoverId: string | null
  onMapReady: (map: MapLibreMap | null) => void
  onSelectProvince: (province: SelectedProvince) => void
  onHoverProvince: (hover: ProvinceHover | null) => void
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const hoveredIdRef = useRef<string | null>(null)
  const selectedIdRef = useRef<string | null>(null)
  const [mapState, setMapState] = useState<MapState>('loading')
  const [attempt, setAttempt] = useState(0)
  const [hotspotPulses, setHotspotPulses] = useState<HotspotPulse[]>([])

  const applyHover = useCallback((map: MapLibreMap, id: string | null) => {
    if (!map.getSource(PROVINCE_SOURCE)) return
    if (hoveredIdRef.current && hoveredIdRef.current !== id) {
      map.setFeatureState({ source: PROVINCE_SOURCE, id: hoveredIdRef.current }, { hover: false })
    }
    hoveredIdRef.current = id
    if (id) map.setFeatureState({ source: PROVINCE_SOURCE, id }, { hover: true })
    if (map.getLayer(PROVINCE_EXTRUDE)) {
      map.setPaintProperty(PROVINCE_EXTRUDE, 'fill-extrusion-opacity', id ? ['case', ['boolean', ['feature-state', 'hover'], false], 0.95, 0.45] : 0.85)
    }
  }, [])

  useEffect(() => {
    const check = window.setTimeout(() => setMapState('loading'), 0)
    return () => window.clearTimeout(check)
  }, [attempt])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let initializedMap: MapLibreMap | null = null
    let readyTimer: number | null = null
    let resizeObserver: ResizeObserver | null = null

    try {
      const map = new maplibregl.Map({
        container,
        style: basemapStyle(),
        bounds: NATIONAL_BOUNDS,
        fitBoundsOptions: { padding: { top: 40, bottom: 40, left: 40, right: 40 }, pitch: 40, bearing: 0 },
        minZoom: 2,
        maxZoom: 12,
        pitch: 40,
        bearing: 0,
        minPitch: 40,
        maxPitch: 40,
        attributionControl: false,
        maxBounds: [[60, -60], [180, 60]],
        dragRotate: false,
      })
      map.touchZoomRotate.disableRotation()
      map.keyboard.disableRotation()
      initializedMap = map
      mapRef.current = map
      onMapReady(map)
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
      // Event `load` bisa tidak pernah terpicu bila kontainer belum punya ukuran.
      // Polling ini memastikan status siap segera setelah style benar-benar termuat.
      readyTimer = window.setInterval(() => {
        if (cancelled) return
        if (map.loaded() || map.isStyleLoaded()) {
          window.clearInterval(readyTimer!)
          readyTimer = null
          setMapState('ready')
        }
      }, 200)
      map.once('load', () => {
        if (readyTimer !== null) {
          window.clearInterval(readyTimer)
          readyTimer = null
        }
        // Fit ulang setelah layout topbar selesai, terutama di mobile.
        window.setTimeout(() => {
          if (!cancelled) map.fitBounds(NATIONAL_BOUNDS, { padding: { top: 40, bottom: 40, left: 40, right: 40 }, pitch: 40, bearing: 0, duration: 0 })
        }, 60)
        if (!cancelled) setMapState('ready')
      })
      map.on('webglcontextlost', () => {
        if (!cancelled) setMapState('error')
      })
      map.on('error', (event) => {
        const errorMessage = event.error?.message ?? ''
        if (!cancelled && (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError') || errorMessage.includes('404'))) setMapState('error')
      })
      resizeObserver = new ResizeObserver(() => map.resize())
      resizeObserver.observe(container)
    } catch {
      queueMicrotask(() => {
        if (!cancelled) setMapState('error')
      })
    }

    return () => {
      cancelled = true
      if (readyTimer !== null) window.clearInterval(readyTimer)
      resizeObserver?.disconnect()
      hoveredIdRef.current = null
      selectedIdRef.current = null
      if (mapRef.current === initializedMap) mapRef.current = null
      onMapReady(null)
      initializedMap?.remove()
    }
  }, [attempt, onMapReady])

  const installLayersRef = useRef<(map: MapLibreMap, data: MapLayers) => void>(() => {})
  useEffect(() => {
    installLayersRef.current = (map, data) => {
      if (!map.isStyleLoaded()) {
        map.once('idle', () => installLayersRef.current(map, data))
        return
      }
      if (!map.getSource(PROVINCE_SOURCE)) map.addSource(PROVINCE_SOURCE, { type: 'geojson', data: data.provinces, promoteId: 'shape_id' })
      else (map.getSource(PROVINCE_SOURCE) as GeoJSONSource).setData(data.provinces)
      if (!map.getSource(HOTSPOT_SOURCE)) map.addSource(HOTSPOT_SOURCE, { type: 'geojson', data: data.hotspots, cluster: true, clusterRadius: 44, clusterMaxZoom: 7 })
      else (map.getSource(HOTSPOT_SOURCE) as GeoJSONSource).setData(data.hotspots)

      if (!map.getLayer(INDONESIA_LAND)) map.addLayer(indonesiaLandStyle())
      if (!map.getLayer(LAND_SHADOW)) map.addLayer({ id: LAND_SHADOW, type: 'line', source: PROVINCE_SOURCE, paint: { 'line-color': 'rgba(20, 20, 20, 0.05)', 'line-width': 8, 'line-blur': 8, 'line-translate': [0, 6] } })
      if (!map.getLayer(PROVINCE_FILL)) map.addLayer({ id: PROVINCE_FILL, type: 'fill', source: PROVINCE_SOURCE, paint: { 'fill-color': '#00000000', 'fill-opacity': ['case', ['==', ['get', 'has_data'], true], 0.9, 1] } })
      if (!map.getLayer(PROVINCE_EXTRUDE)) map.addLayer({ id: PROVINCE_EXTRUDE, type: 'fill-extrusion', source: PROVINCE_SOURCE, filter: ['==', ['get', 'has_data'], true], paint: { 'fill-extrusion-color': '#00000000', 'fill-extrusion-height': 0, 'fill-extrusion-height-transition': { duration: 180, delay: 0 }, 'fill-extrusion-opacity': 0.85, 'fill-extrusion-opacity-transition': { duration: 180, delay: 0 }, 'fill-extrusion-vertical-gradient': true } })
      if (!map.getLayer(PROVINCE_LINE)) map.addLayer({ id: PROVINCE_LINE, type: 'line', source: PROVINCE_SOURCE, layout: { 'line-join': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 1.2 } })
      if (!map.getLayer(PROVINCE_HOVER)) map.addLayer({ id: PROVINCE_HOVER, type: 'line', source: PROVINCE_SOURCE, layout: { 'line-join': 'round' }, paint: { 'line-color': tokenValue('--text'), 'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3.5, ['boolean', ['feature-state', 'hover'], false], 2.5, 0] as never, 'line-width-transition': { duration: 180, delay: 0 } } })
      if (!map.getLayer(HOTSPOT_CLUSTER)) map.addLayer({ id: HOTSPOT_CLUSTER, type: 'circle', source: HOTSPOT_SOURCE, filter: ['has', 'point_count'], paint: { 'circle-color': tokenValue('--accent'), 'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 1, 10, 10, 14, 50, 18, 200, 22], 'circle-stroke-color': tokenValue('--surface'), 'circle-stroke-width': 2 } })
      if (!map.getLayer(HOTSPOT_CLUSTER_COUNT)) map.addLayer({ id: HOTSPOT_CLUSTER_COUNT, type: 'symbol', source: HOTSPOT_SOURCE, filter: ['has', 'point_count'], layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': ['Open Sans Semibold'], 'text-size': 11, 'text-allow-overlap': true, 'text-ignore-placement': true }, paint: { 'text-color': tokenValue('--on-accent') } })
      if (!map.getLayer(HOTSPOT_CIRCLE)) map.addLayer({ id: HOTSPOT_CIRCLE, type: 'circle', source: HOTSPOT_SOURCE, filter: ['!', ['has', 'point_count']], paint: { 'circle-radius': ['interpolate', ['linear'], ['get', 'frp'], 0, 3, 100, 7], 'circle-color': tokenValue('--map-hotspot-fill'), 'circle-stroke-color': tokenValue('--map-hotspot-stroke'), 'circle-stroke-width': 1.25 } })

      for (const id of [PROVINCE_FILL, PROVINCE_EXTRUDE, PROVINCE_LINE, PROVINCE_HOVER, HOTSPOT_CLUSTER, HOTSPOT_CLUSTER_COUNT, HOTSPOT_CIRCLE]) {
        map.setLayoutProperty(id, 'visibility', 'visible')
      }
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready') return
    paintProvinceLayers(map)
  }, [mapState])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !layers || mapState !== 'ready') return
    installLayersRef.current(map, layers)
    paintProvinceLayers(map)
    const provinceSource = map.getSource(PROVINCE_SOURCE) as GeoJSONSource | undefined
    const hotspotSource = map.getSource(HOTSPOT_SOURCE) as GeoJSONSource | undefined
    if (provinceSource) provinceSource.setData(layers.provinces)
    if (hotspotSource) hotspotSource.setData(layers.hotspots)
  }, [layers, mapState])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready' || !layers) {
      queueMicrotask(() => setHotspotPulses([]))
      return
    }
    let frame = 0
    const update = () => {
      frame = 0
      if (!map.getLayer(HOTSPOT_CIRCLE)) {
        setHotspotPulses([])
        return
      }
      const pulses = map.queryRenderedFeatures({ layers: [HOTSPOT_CIRCLE] })
        .filter((feature) => feature.geometry.type === 'Point')
        .map((feature, index) => {
          const geometry = feature.geometry as Point
          const point = map.project(geometry.coordinates as [number, number])
          return { id: `${feature.properties?.time_local ?? 'hotspot'}-${index}`, x: point.x, y: point.y }
        })
      setHotspotPulses(pulses)
    }
    const schedule = () => {
      if (frame === 0) frame = requestAnimationFrame(update)
    }
    schedule()
    map.on('move', schedule)
    map.on('zoom', schedule)
    map.on('idle', schedule)
    return () => {
      if (frame) cancelAnimationFrame(frame)
      map.off('move', schedule)
      map.off('zoom', schedule)
      map.off('idle', schedule)
    }
  }, [layers, mapState])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready') return

    const setHover = (id: string | null) => {
      if (hoveredIdRef.current === id) return
      applyHover(map, id)
    }

    const provinceAt = (event: MapMouseEvent) => {
      const isProvince = (feature: MapGeoJSONFeature) => feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon'
      const direct = map.queryRenderedFeatures(event.point, { layers: [PROVINCE_FILL] }).find(isProvince)
      if (direct) return direct
      // Area klik diperbesar untuk provinsi kecil seperti Bali dan DI Yogyakarta.
      const pad = 8
      const box: [maplibregl.PointLike, maplibregl.PointLike] = [
        [event.point.x - pad, event.point.y - pad],
        [event.point.x + pad, event.point.y + pad],
      ]
      return map.queryRenderedFeatures(box, { layers: [PROVINCE_FILL] }).find(isProvince)
    }

    const handleMove = (event: MapMouseEvent) => {
      const feature = provinceAt(event)
      const hotspotHit = map.queryRenderedFeatures(event.point, { layers: [HOTSPOT_CLUSTER, HOTSPOT_CIRCLE] }).length > 0
      if (!feature) {
        map.getCanvas().style.cursor = hotspotHit ? 'pointer' : ''
        setHover(null)
        onHoverProvince(null)
        return
      }
      const properties = feature.properties as ProvinceHoverProperties | null
      if (!properties || typeof properties.province !== 'string') return
      map.getCanvas().style.cursor = 'pointer'
      setHover(properties.shape_id ?? null)
      onHoverProvince({ properties, point: [event.point.x, event.point.y] })
    }

    const handleClick = (event: MapMouseEvent) => {
      const feature = provinceAt(event)
      if (!feature) return
      const properties = feature.properties as ProvinceProperties | null
      if (!properties || typeof properties.province !== 'string') return
      onSelectProvince({ properties, geometry: feature.geometry })
    }

    const handleLeave = () => {
      map.getCanvas().style.cursor = ''
      setHover(null)
      onHoverProvince(null)
    }

    const canvas = map.getCanvas()
    map.on('mousemove', handleMove)
    map.on('click', handleClick)
    canvas.addEventListener('mouseleave', handleLeave)
    return () => {
      map.off('mousemove', handleMove)
      map.off('click', handleClick)
      canvas.removeEventListener('mouseleave', handleLeave)
      canvas.style.cursor = ''
      setHover(null)
    }
  }, [mapState, onHoverProvince, onSelectProvince, applyHover])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready') return
    applyHover(map, externalHoverId)
  }, [externalHoverId, mapState, applyHover])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready' || !map.getSource(PROVINCE_SOURCE)) return
    const nextId = selectedProvince?.shape_id ?? null
    if (selectedIdRef.current && selectedIdRef.current !== nextId) {
      map.setFeatureState({ source: PROVINCE_SOURCE, id: selectedIdRef.current }, { selected: false })
    }
    selectedIdRef.current = nextId
    if (nextId) map.setFeatureState({ source: PROVINCE_SOURCE, id: nextId }, { selected: true })
  }, [selectedProvince, mapState])

  return (
    <div className="map-root">
      <div ref={containerRef} className="map-canvas" role="application" aria-label="Peta risiko provinsi. Gunakan tombol tab untuk memilih periode. Klik provinsi untuk memilih." />
      <div className="hotspot-pulse-layer" aria-hidden="true">
        {hotspotPulses.map((pulse) => <span key={pulse.id} className="hotspot-pulse" style={{ left: pulse.x, top: pulse.y }} />)}
      </div>
      {mapState !== 'ready' && (
        <div className="map-state" role="status" aria-live="polite">
          {mapState === 'loading' ? <span className="mono-label">MEMUAT PETA...</span> : (
            <div className="map-error"><span className="mono-label">PETA GAGAL DIMUAT. COBA LAGI.</span><button className="retry-button" type="button" onClick={() => setAttempt((value) => value + 1)}>COBA LAGI</button></div>
          )}
        </div>
      )}
      {mapState === 'ready' && dataState === 'error' && (
        <div className="map-state" role="alert"><div className="map-error"><span className="mono-label">DATA PETA GAGAL DIMUAT.</span><button className="retry-button" type="button" onClick={() => setAttempt((value) => value + 1)}>COBA LAGI</button></div></div>
      )}
      {mapState === 'ready' && dataState === 'loading' && <div className="map-data-loading" role="status">MEMUAT DATA PETA...</div>}
    </div>
  )
}

function App() {
  const currentPath = window.location.pathname
  const isMethodPage = currentPath === '/metode'
  const isWilayahPage = currentPath === '/wilayah'
  const isRiwayatPage = currentPath === '/riwayat'
  const isLandingPage = currentPath === '/'
  const isMapPage = currentPath === '/peta'
  const [horizon, setHorizon] = useState<HorizonKey>('d1')
  const [hoverProvince, setHoverProvince] = useState<ProvinceHover | null>(null)
  const [top5HoverId, setTop5HoverId] = useState<string | null>(null)
  const [selectedProvince, setSelectedProvince] = useState<SelectedProvince | null>(null)
  const [dioramaClosing, setDioramaClosing] = useState(false)
  const closeTimerRef = useRef<number | null>(null)
  const [layers, setLayers] = useState<MapLayers | null>(null)
  const [meta, setMeta] = useState<DataMeta | null>(null)
  const [dataState, setDataState] = useState<DataState>('loading')
  const [staleHours, setStaleHours] = useState<number | null>(null)
  const mapInstanceRef = useRef<MapLibreMap | null>(null)
  const [legendOpen, setLegendOpen] = useState(false)
  const legendRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => () => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current)
  }, [])

  const handleSelectProvince = useCallback((province: SelectedProvince) => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    setDioramaClosing(false)
    setSelectedProvince(province)
    setHoverProvince(null)
    window.history.pushState({ province: provinceSlug(province.properties.province) }, '', `/peta#${provinceSlug(province.properties.province)}`)
  }, [])
  const resetNationalView = useCallback(() => {
    const map = mapInstanceRef.current
    if (!map || !map.loaded()) return
    map.fitBounds(NATIONAL_BOUNDS, { padding: { top: 40, bottom: 40, left: 40, right: 40 }, pitch: 40, bearing: 0, duration: 600 })
  }, [])
  const handleCloseDiorama = useCallback(() => {
    setHoverProvince(null)
    setDioramaClosing(true)
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      setDioramaClosing(false)
      if (window.history.state?.province) {
        window.history.back()
        return
      }
      setSelectedProvince(null)
      resetNationalView()
      window.history.replaceState({}, '', '/peta')
    }, 320)
  }, [resetNationalView])
  const handleHoverProvince = useCallback((hover: ProvinceHover | null) => setHoverProvince(hover), [])
  const handleMapReady = useCallback((map: MapLibreMap | null) => { mapInstanceRef.current = map }, [])
  const topProvinces = useMemo(() => {
    if (!layers) return []
    return layers.provinces.features
      .filter((feature) => feature.properties.has_data && feature.properties.level)
      .sort((a, b) => (b.properties.level ?? 0) - (a.properties.level ?? 0) || (b.properties.hotspot_72h ?? 0) - (a.properties.hotspot_72h ?? 0))
      .slice(0, 5)
  }, [layers])
  const handleTop5Hover = useCallback((feature: ProvinceFeature | null) => {
    setTop5HoverId(feature?.properties.shape_id ?? null)
    setHoverProvince(null)
  }, [])
  const handleTop5Select = useCallback((feature: ProvinceFeature) => {
    handleSelectProvince({ properties: feature.properties, geometry: feature.geometry })
  }, [handleSelectProvince])

  useEffect(() => {
    document.title = isMethodPage ? 'Metode dan data | HOTSPOT.ID' : isLandingPage ? 'HOTSPOT.ID | Risiko munculnya hotspot' : 'HOTSPOT.ID | Peta risiko munculnya hotspot'
  }, [isMethodPage, isLandingPage])

  useEffect(() => {
    let cancelled = false
    window.setTimeout(() => setDataState('loading'), 0)
    void loadMapBaseData(horizon).then((data) => {
      if (cancelled) return
      setLayers({ hotspots: data.hotspots, provinces: data.provinces, kabupatenIndex: data.kabupatenIndex })
      setMeta(data.meta)
      setDataState('ready')
    }).catch(() => {
      if (cancelled) return
      setLayers(null)
      setMeta(null)
      setDataState('error')
    })
    return () => { cancelled = true }
  }, [horizon])

  useEffect(() => {
    if (!isMapPage || !layers) return
    const hash = decodeURIComponent(window.location.hash.replace(/^#/, ''))
    if (!hash) return
    const province = layers.provinces.features.find((feature) => provinceSlug(feature.properties.province) === hash)
    if (province) {
      queueMicrotask(() => setSelectedProvince({ properties: province.properties, geometry: province.geometry }))
    } else {
      queueMicrotask(() => setSelectedProvince(null))
      window.history.replaceState({}, '', '/peta')
    }
  }, [isMapPage, layers])

  useEffect(() => {
    if (!isMapPage) return
    const syncFromHash = () => {
      const hash = decodeURIComponent(window.location.hash.replace(/^#/, ''))
      if (!hash) {
        setDioramaClosing(false)
        setSelectedProvince(null)
        setHoverProvince(null)
        resetNationalView()
        return
      }
      if (!layers) return
      const province = layers.provinces.features.find((feature) => provinceSlug(feature.properties.province) === hash)
      if (province) {
        setDioramaClosing(false)
        setSelectedProvince({ properties: province.properties, geometry: province.geometry })
      } else {
        setDioramaClosing(false)
        setSelectedProvince(null)
        setHoverProvince(null)
        resetNationalView()
        window.history.replaceState({}, '', '/peta')
      }
    }
    window.addEventListener('popstate', syncFromHash)
    window.addEventListener('hashchange', syncFromHash)
    return () => {
      window.removeEventListener('popstate', syncFromHash)
      window.removeEventListener('hashchange', syncFromHash)
    }
  }, [isMapPage, layers, resetNationalView])

  // Deep-link from WilayahPage: /peta?provinsi=Nama atau /peta?kabupaten=Nama.
  // Level 1 hanya memilih provinsi; kabupaten dipakai untuk mencari provinsinya.
  useEffect(() => {
    if (!isMapPage || !layers || !mapInstanceRef.current) return
    const params = new URLSearchParams(window.location.search)
    const targetKabupaten = params.get('kabupaten')
    const targetProvinsi = params.get('provinsi')
    if (!targetKabupaten && !targetProvinsi) return

    const bounds = new maplibregl.LngLatBounds()
    const extend = (coords: unknown) => {
      if (!Array.isArray(coords)) return
      if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        bounds.extend(coords as [number, number])
        return
      }
      for (const child of coords) extend(child)
    }

    if (targetKabupaten) {
      const kabupaten = layers.kabupatenIndex.find(
        (row) => row.kabupaten.toLocaleLowerCase('id') === targetKabupaten.toLocaleLowerCase('id'),
      )
      if (!kabupaten) return
      const province = layers.provinces.features.find(
        (feature) => normalizeName(feature.properties.province) === normalizeName(kabupaten.provinsi),
      )
      if (!province) return
      extend(province.geometry.coordinates)
      if (bounds.isEmpty()) return
      mapInstanceRef.current.fitBounds(bounds, { padding: 80, maxZoom: 8.5, duration: 800 })
      queueMicrotask(() => setSelectedProvince({ properties: province.properties, geometry: province.geometry }))
      window.history.replaceState({}, '', `/peta#${provinceSlug(province.properties.province)}`)
      return
    }

    const province = layers.provinces.features.find(
      (feature) => normalizeName(feature.properties.province) === normalizeName(targetProvinsi!),
    )
    if (!province) return
    extend(province.geometry.coordinates)
    if (bounds.isEmpty()) return
    mapInstanceRef.current.fitBounds(bounds, { padding: 80, maxZoom: 7.5, duration: 800 })
    queueMicrotask(() => setSelectedProvince({ properties: province.properties, geometry: province.geometry }))
    window.history.replaceState({}, '', `/peta#${provinceSlug(province.properties.province)}`)
  }, [isMapPage, layers])

  useEffect(() => {
    if (!legendOpen) return
    const handlePointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !legendRef.current?.contains(event.target)) setLegendOpen(false)
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLegendOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [legendOpen])

  useEffect(() => {
    if (!meta) return
    const updateStaleness = () => setStaleHours(Math.max(0, Math.floor((Date.now() - Date.parse(meta.generated_at)) / 3600000)))
    updateStaleness()
    const timer = window.setInterval(updateStaleness, 60000)
    return () => window.clearInterval(timer)
  }, [meta])

  if (isMethodPage) return <MethodPage />
  if (isWilayahPage) return <WilayahPage />
  if (isRiwayatPage) return <RiwayatPage />
  if (isLandingPage) return <LandingPage />
  if (!isMapPage) return null

  const tooltipStyle = hoverProvince ? {
    left: Math.max(8, Math.min(hoverProvince.point[0] + 12, window.innerWidth - 248)),
    top: Math.max(8, Math.min(hoverProvince.point[1] + 12, window.innerHeight - 176)),
  } : undefined

  return (
    <main className="dashboard">
      <header className="topbar">
        <a className="wordmark" href="/peta" aria-label="HOTSPOT.ID, peta"><span className="wordmark-mark" aria-hidden="true" /><span>HOTSPOT.ID</span></a>
        <nav className="main-nav" aria-label="Navigasi utama">
          <a className="nav-tab" href="/">Beranda</a><a className="nav-tab nav-active" href="/peta" aria-current="page">Peta</a><a className="nav-tab" href="/wilayah">Wilayah</a><a className="nav-tab" href="/riwayat">Riwayat</a><a className="nav-tab" href="/metode">Metode</a>
        </nav>
        <div className="topbar-right">
          {meta?.is_sample && <span className="sample-tag header-sample">Data contoh</span>}
          <div className={`data-status${meta && staleHours !== null && !meta.is_sample && staleHours > meta.stale_after_hours ? ' is-stale' : ''}`} title={meta && staleHours !== null && staleHours > meta.stale_after_hours && !meta.is_sample ? `Pembaruan terakhir ${staleHours} jam lalu` : undefined}><span className="status-dot" aria-hidden="true" />{meta && staleHours !== null ? (meta.is_sample ? `DIPERBARUI ${new Date(meta.generated_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' })} WIB` : (staleHours > meta.stale_after_hours ? `DATA BASI · ${staleHours} JAM` : `DIPERBARUI ${new Date(meta.generated_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' })} WIB`)) : 'MEMUAT STATUS DATA'}</div>
        </div>
      </header>

      <section className="workspace" id="peta" aria-label="Peta risiko Indonesia">
        <div className={`map-stage${selectedProvince ? ' has-diorama' : ''}`}>
          <MapView
            layers={layers}
            dataState={dataState}
            selectedProvince={selectedProvince?.properties ?? null}
            externalHoverId={top5HoverId}
            onMapReady={handleMapReady}
            onSelectProvince={handleSelectProvince}
            onHoverProvince={handleHoverProvince}
          />
          {!selectedProvince && topProvinces.length > 0 && (
            <aside className="top5-panel" aria-label="Top 5 provinsi berdasarkan risiko">
              <div className="top5-head"><span className="eyebrow">TOP 5 PROVINSI</span><span className="top5-metric">HOTSPOT 72 JAM</span></div>
              <ol className="top5-list">
                {topProvinces.map((feature, index) => {
                  const level = (feature.properties.level ?? 1) as RiskLevel
                  const isHovered = hoverProvince?.properties.province === feature.properties.province || top5HoverId === feature.properties.shape_id
                  return (
                    <li key={feature.properties.shape_id}>
                      <button
                        type="button"
                        className={`top5-row${isHovered ? ' is-hovered' : ''}`}
                        onMouseEnter={() => handleTop5Hover(feature)}
                        onMouseLeave={() => handleTop5Hover(null)}
                        onFocus={() => handleTop5Hover(feature)}
                        onBlur={() => handleTop5Hover(null)}
                        onClick={() => handleTop5Select(feature)}
                      >
                        <span className="top5-rank">{index + 1}</span>
                        <span className="top5-name">{feature.properties.province}</span>
                        <span className="top5-dot" style={{ background: `var(${RISK_LEVELS[level].colorToken})` }} aria-hidden="true" />
                        <span className="top5-hotspot">{feature.properties.hotspot_72h ?? 0}</span>
                      </button>
                    </li>
                  )
                })}
              </ol>
            </aside>
          )}
          {!selectedProvince && <div className="map-lower-left">
            <p className="map-limitation">Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.</p>
            <div className="legend-popover-wrap" ref={legendRef}>
              <button className="legend-trigger" type="button" aria-expanded={legendOpen} aria-haspopup="true" onClick={() => setLegendOpen((open) => !open)}>LEGENDA</button>
              {legendOpen && <aside className="legend-popover" aria-label="Legenda risiko">
                <RiskLegend showHotspot />
              </aside>}
            </div>
          </div>}
          {!selectedProvince && hoverProvince && <div className="map-tooltip province-tooltip" style={tooltipStyle} role="status"><div className="tooltip-head"><strong>{hoverProvince.properties.province}</strong>{!hoverProvince.properties.has_data ? <span className="tooltip-empty">TANPA DATA</span> : <span className={`level-chip risk-level-${hoverProvince.properties.level} tooltip-badge`}><span className="level-bars" aria-hidden="true">{[1, 2, 3, 4].map((bar) => <i key={bar} className={bar <= (hoverProvince.properties.level ?? 1) ? 'filled' : ''} />)}</span>{riskLevelName(hoverProvince.properties.level ?? 1)}</span>}</div>{hoverProvince.properties.has_data && <><span>HOTSPOT 72 JAM {hoverProvince.properties.hotspot_72h ?? 0}</span><span>KABUPATEN TERDAMPAK {hoverProvince.properties.kabupaten_terdampak ?? 0}</span></>}</div>}
          {!selectedProvince && <div className="map-control-stack">
            <fieldset className="horizon-control"><legend className="sr-only">PERIODE</legend><div className="horizon-options">{HORIZONS.map((item) => <button className={`horizon-button${horizon === item.key ? ' is-selected' : ''}`} key={item.key} type="button" aria-pressed={horizon === item.key} onClick={() => setHorizon(item.key)}>{item.label}<small>{new Date(Date.parse(meta?.generated_at ?? '2026-10-30T00:00:00Z') + HORIZONS.findIndex((entry) => entry.key === item.key) * 86400000).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', timeZone: 'Asia/Jakarta' }).toUpperCase()}</small></button>)}</div></fieldset>
          </div>}
          {selectedProvince && <DioramaErrorBoundary onReset={handleCloseDiorama}><ProvinceDiorama key={selectedProvince.properties.province} province={selectedProvince} horizon={horizon} generatedAt={meta?.generated_at} closing={dioramaClosing} onClose={handleCloseDiorama} onHorizonChange={setHorizon} /></DioramaErrorBoundary>}
        </div>
      </section>

      <span className="sr-only" aria-live="polite">Peta {HORIZONS.find((item) => item.key === horizon)?.label} dipilih{selectedProvince ? `, ${selectedProvince.properties.province} dipilih` : ''}.</span>
    </main>
  )
}

export default App

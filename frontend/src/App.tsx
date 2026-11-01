import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { GeoJSONSource, Map as MapLibreMap, MapMouseEvent, MapGeoJSONFeature } from 'maplibre-gl'
import { HORIZONS, type HorizonKey } from './lib/horizons'
import { aggregateRisks, loadMapData, type ProvinceFeatureCollection, type RiskMapCollection } from './lib/map-data'
import { RISK_LEVELS, riskColor } from './lib/risk'
import { RiskLegend } from './Legend'
import type { DataMeta, HotspotFeatureCollection, RiskProperties } from './types/geojson'
import { MethodPage } from './MethodPage'
import { WilayahPage } from './WilayahPage'
import { RiwayatPage } from './RiwayatPage'
import { LandingPage } from './LandingPage'
import './App.css'

const RISK_SOURCE = 'hotspot-risk-source'
const HOTSPOT_SOURCE = 'hotspot-observation-source'
const RISK_FILL = 'hotspot-risk-fill'
const RISK_LINE = 'hotspot-risk-outline'
const PROVINCE_SOURCE = 'province-boundaries'
const PROVINCE_FILL = 'province-risk-fill'
const PROVINCE_LINE = 'province-boundary-line'
const INDONESIA_LAND = 'indonesia-land'
const HOTSPOT_CIRCLE = 'hotspot-observation-circles'
const SELECTED_CELL_LAYER = 'selected-risk-cell-outline'
maplibregl.setWorkerUrl(new URL('maplibre-gl/dist/maplibre-gl-worker.mjs', import.meta.url).toString())
const levelNames = ['RENDAH', 'SEDANG', 'TINGGI', 'SANGAT TINGGI'] as const
const weeklyBars = [0.22, 0.48, 0.34, 0.68, 0.52, 0.82, 0.61]
type MapState = 'loading' | 'ready' | 'error'
type DataState = 'loading' | 'ready' | 'error'
type SelectedCell = RiskProperties & { coordinates: [number, number] }
type HoverCell = { properties: RiskProperties; point: [number, number] }
type ProvinceHoverProperties = { province: string; level?: number; score?: number; has_data?: boolean; high_count?: number; very_high_count?: number; cell_count?: number; risk_area_ha?: number }
type ProvinceHover = { properties: ProvinceHoverProperties; point: [number, number] }
type SelectedProvince = ProvinceHoverProperties & { coordinates: [number, number] }

type MapLayers = {
  risk: RiskMapCollection
  hotspots: HotspotFeatureCollection
  provinces: ProvinceFeatureCollection
}


function tokenValue(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim()
}

// Tile-free basemap: only a themed background. Indonesian land comes from
// the province GeoJSON layer added at runtime.
function basemapStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
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

function featureProperties(feature: MapGeoJSONFeature): RiskProperties | null {
  const properties = feature.properties
  if (!properties || typeof properties.cell_id !== 'number' || typeof properties.level !== 'number' || typeof properties.score !== 'number') return null
  return properties as RiskProperties
}

function centerOfFeature(feature: MapGeoJSONFeature): [number, number] {
  const coordinates = feature.geometry.type === 'Polygon'
    ? feature.geometry.coordinates[0]
    : feature.geometry.type === 'MultiPolygon'
      ? feature.geometry.coordinates[0][0]
      : []
  const points = coordinates.slice(0, -1)
  if (points.length === 0) return [0, 0]
  const center = points.reduce<[number, number]>((sum, point) => [sum[0] + point[0], sum[1] + point[1]], [0, 0])
  return [center[0] / points.length, center[1] / points.length]
}

function riskLevelName(level: number) {
  return levelNames[Math.max(0, Math.min(levelNames.length - 1, level - 1))]
}

function MapView({ layers, showRisk, showHotspots, selectedCell, onMapReady, onSelectCell, onSelectProvince, onHoverCell, onHoverProvince, onSummary }: {
  layers: MapLayers | null
  showRisk: boolean
  showHotspots: boolean
  selectedCell: SelectedCell | null
  onMapReady: (map: MapLibreMap | null) => void
  onSelectCell: (cell: SelectedCell) => void
  onSelectProvince: (province: SelectedProvince) => void
  onHoverCell: (cell: HoverCell | null) => void
  onHoverProvince: (hover: ProvinceHover | null) => void
  onSummary: (summary: { high: number; veryHigh: number }) => void
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [mapState, setMapState] = useState<MapState>('loading')
  const [attempt, setAttempt] = useState(0)
  const [dataState, setDataState] = useState<DataState>('loading')
  const onSummaryRef = useRef(onSummary)
  useEffect(() => { onSummaryRef.current = onSummary }, [onSummary])

  useEffect(() => {
    const check = window.setTimeout(() => setMapState('loading'), 0)
    return () => window.clearTimeout(check)
  }, [attempt])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let initializedMap: MapLibreMap | null = null

    try {
      const map = new maplibregl.Map({
        container,
        style: basemapStyle(),
        bounds: [[94.5, -11.5], [141.5, 6.5]],
        minZoom: 3,
        maxZoom: 12,
        attributionControl: false,
        maxBounds: [[90, -14], [143, 9]],
        dragRotate: false,
      })
      map.touchZoomRotate.disableRotation()
      initializedMap = map
      mapRef.current = map
      onMapReady(map)
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
      map.once('load', () => {
        if (!cancelled) setMapState('ready')
      })
      map.on('error', (event) => {
        const errorMessage = event.error?.message ?? ''
        if (!cancelled && (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError') || errorMessage.includes('404'))) setMapState('error')
      })
    } catch {
      queueMicrotask(() => {
        if (!cancelled) setMapState('error')
      })
    }

    return () => {
      cancelled = true
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
      if (!map.getSource(RISK_SOURCE)) map.addSource(RISK_SOURCE, { type: 'geojson', data: data.risk, promoteId: 'cell_id' })
      if (!map.getSource(PROVINCE_SOURCE)) map.addSource(PROVINCE_SOURCE, { type: 'geojson', data: data.provinces })
      else (map.getSource(PROVINCE_SOURCE) as GeoJSONSource).setData(data.provinces)
      // Solid Indonesian islands, placed above the background and under all overlays.
      if (!map.getLayer(INDONESIA_LAND)) map.addLayer(indonesiaLandStyle(), PROVINCE_FILL)
      if (!map.getSource('hotspot-aggregate-source')) map.addSource('hotspot-aggregate-source', { type: 'geojson', data: aggregateRisks(data.risk.features) })
      if (!map.getSource(HOTSPOT_SOURCE)) map.addSource(HOTSPOT_SOURCE, { type: 'geojson', data: data.hotspots, cluster: true, clusterRadius: 44, clusterMaxZoom: 7 })
      if (!map.getLayer(PROVINCE_FILL)) map.addLayer({ id: PROVINCE_FILL, type: 'fill', source: PROVINCE_SOURCE, maxzoom: 5.5, paint: { 'fill-color': '#00000000', 'fill-opacity': ['case', ['==', ['get', 'has_data'], true], ['match', ['get', 'level'], 1, 0.45, 2, 0.6, 3, 0.8, 4, 0.95, 0.45], 1] } })

      if (!map.getLayer(PROVINCE_LINE)) map.addLayer({ id: PROVINCE_LINE, type: 'line', source: PROVINCE_SOURCE, maxzoom: 5.5, paint: { 'line-color': '#00000000', 'line-width': 1 } })
      if (!map.getLayer(RISK_FILL)) map.addLayer({ id: RISK_FILL, type: 'fill', source: RISK_SOURCE, minzoom: 5.5, paint: { 'fill-color': ['match', ['get', 'level'], 1, riskColor(1), 2, riskColor(2), 3, riskColor(3), 4, riskColor(4), 'transparent'], 'fill-opacity': ['match', ['get', 'level'], 1, RISK_LEVELS[1].opacity, 2, RISK_LEVELS[2].opacity, 3, RISK_LEVELS[3].opacity, 4, RISK_LEVELS[4].opacity, 0] } })
      if (!map.getLayer(RISK_LINE)) map.addLayer({ id: RISK_LINE, type: 'line', source: RISK_SOURCE, minzoom: 5.5, paint: { 'line-color': ['match', ['get', 'level'], 1, riskColor(1, true), 2, riskColor(2, true), 3, riskColor(3, true), 4, riskColor(4, true), tokenValue('--line-strong')], 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 0.3, 6, 0.7, 8, 1] } })

      if (!map.getLayer(SELECTED_CELL_LAYER)) map.addLayer({ id: SELECTED_CELL_LAYER, type: 'line', source: RISK_SOURCE, minzoom: 5.5, filter: ['==', ['get', 'cell_id'], -1], paint: { 'line-color': tokenValue('--line-strong'), 'line-width': 2.5 } })
      if (!map.getLayer('hotspot-cluster-circles')) map.addLayer({ id: 'hotspot-cluster-circles', type: 'circle', source: HOTSPOT_SOURCE, filter: ['has', 'point_count'], paint: { 'circle-color': tokenValue('--accent'), 'circle-radius': ['step', ['get', 'point_count'], 8, 10, 10, 50, 12], 'circle-stroke-color': tokenValue('--surface'), 'circle-stroke-width': 2 } })
      if (!map.getLayer(HOTSPOT_CIRCLE)) map.addLayer({ id: HOTSPOT_CIRCLE, type: 'circle', source: HOTSPOT_SOURCE, filter: ['!', ['has', 'point_count']], paint: { 'circle-radius': ['step', ['get', 'frp'], 3, 20, 4, 70, 6], 'circle-color': tokenValue('--map-hotspot-fill'), 'circle-stroke-color': tokenValue('--map-hotspot-stroke'), 'circle-stroke-width': 1.25 } })
       for (const id of [PROVINCE_FILL, PROVINCE_LINE, 'province-no-data-label']) map.setLayoutProperty(id, 'visibility', map.getZoom() < 5.5 && showRisk ? 'visible' : 'none')
        for (const id of ['hotspot-risk-aggregate-fill', 'hotspot-risk-aggregate-line']) map.setLayoutProperty(id, 'visibility', 'none')
      for (const id of [RISK_LINE, SELECTED_CELL_LAYER]) map.setLayoutProperty(id, 'visibility', map.getZoom() >= 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(RISK_FILL)) map.setLayoutProperty(RISK_FILL, 'visibility', map.getZoom() >= 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(PROVINCE_FILL)) map.setPaintProperty(PROVINCE_FILL, 'fill-opacity-transition', { duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 160, delay: 0 })
      for (const id of ['hotspot-cluster-circles', 'hotspot-cluster-count', HOTSPOT_CIRCLE]) map.setLayoutProperty(id, 'visibility', showHotspots ? 'visible' : 'none')
    }
  }, [showRisk, showHotspots])

  useEffect(() => {
    // Pasang ulang lapisan dan cat ulang warnanya dari token terang terkini.
    const map = mapRef.current
    if (!map || mapState !== 'ready') return
    if (layers) installLayersRef.current(map, layers)
    const provinceFill = ['case', ['==', ['get', 'has_data'], true], ['match', ['get', 'level'], 1, riskColor(1), 2, riskColor(2), 3, riskColor(3), 4, riskColor(4), tokenValue('--map-no-data')], tokenValue('--map-land')] as never
    map.setPaintProperty('theme-sea', 'background-color', tokenValue('--map-bg'))
    if (map.getLayer(INDONESIA_LAND)) map.setPaintProperty(INDONESIA_LAND, 'fill-color', tokenValue('--map-land'))
    if (map.getLayer(PROVINCE_FILL)) map.setPaintProperty(PROVINCE_FILL, 'fill-color', provinceFill)
    if (map.getLayer(PROVINCE_LINE)) map.setPaintProperty(PROVINCE_LINE, 'line-color', tokenValue('--map-line'))
  }, [mapState, layers])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !layers || mapState !== 'ready') return
    installLayersRef.current(map, layers)
    const riskSource = map.getSource(RISK_SOURCE) as GeoJSONSource | undefined
    const aggregateSource = map.getSource('hotspot-aggregate-source') as GeoJSONSource | undefined
    const hotspotSource = map.getSource(HOTSPOT_SOURCE) as GeoJSONSource | undefined
    if (riskSource) riskSource.setData(layers.risk)
    if (aggregateSource) aggregateSource.setData(aggregateRisks(layers.risk.features))
    if (hotspotSource) hotspotSource.setData(layers.hotspots)
    if (map.getLayer(SELECTED_CELL_LAYER)) map.setFilter(SELECTED_CELL_LAYER, ['==', ['get', 'cell_id'], selectedCell?.cell_id ?? -1])
    onSummaryRef.current({
      high: layers.risk.features.filter((feature) => feature.properties.level === 3).length,
      veryHigh: layers.risk.features.filter((feature) => feature.properties.level === 4).length,
    })
    setDataState('ready')
  }, [layers, mapState, selectedCell])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !layers || mapState !== 'ready') return
    installLayersRef.current(map, layers)
  }, [layers, mapState, showRisk, showHotspots])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready' || !dataState) return

    const getRiskFeature = (event: MapMouseEvent) => {
      if (map.getZoom() < 5.5) {
        const provinces = map.queryRenderedFeatures(event.point, { layers: [PROVINCE_FILL] })
        return provinces.find((feature) => feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon')
      }
      const features = map.queryRenderedFeatures(event.point, { layers: [RISK_FILL] })
      return features.find((feature) => feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon')
    }

    const handleMove = (event: MapMouseEvent) => {
      const feature = getRiskFeature(event)
      if (!feature) {
        map.getCanvas().style.cursor = ''
        onHoverProvince(null)
        onHoverCell(null)
        return
      }
      if (map.getZoom() < 5.5) {
        const properties = feature.properties
        if (!properties || typeof properties.province !== 'string') return
        map.getCanvas().style.cursor = 'pointer'
        onHoverProvince({ properties: properties as ProvinceHoverProperties, point: [event.point.x, event.point.y] })
        onHoverCell(null)
        return
      }
      const properties = featureProperties(feature)
      if (!properties) return
      map.getCanvas().style.cursor = 'pointer'
      onHoverProvince(null)
      onHoverCell({ properties, point: [event.point.x, event.point.y] })
    }

    const handleClick = (event: MapMouseEvent) => {
      const feature = getRiskFeature(event)
      if (!feature) return
      if (map.getZoom() < 5.5) {
        const provinceProperties = feature.properties
        if (!provinceProperties || typeof provinceProperties.province !== 'string') return
        onSelectProvince({ ...(provinceProperties as ProvinceHoverProperties), coordinates: centerOfFeature(feature) })
        return
      }
      const properties = featureProperties(feature)
      if (!properties) return
      onSelectCell({ ...properties, coordinates: centerOfFeature(feature) })
    }
    const handleLeave = () => {
      map.getCanvas().style.cursor = ''
      onHoverProvince(null)
      onHoverCell(null)
    }

    const canvas = map.getCanvas()
    map.on('mousemove', handleMove)
    canvas.addEventListener('mouseleave', handleLeave)
    map.on('click', handleClick)
    const handleZoom = () => {
      if (map.getLayer(PROVINCE_FILL)) map.setLayoutProperty(PROVINCE_FILL, 'visibility', map.getZoom() < 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(PROVINCE_LINE)) map.setLayoutProperty(PROVINCE_LINE, 'visibility', map.getZoom() < 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(RISK_FILL)) map.setLayoutProperty(RISK_FILL, 'visibility', map.getZoom() >= 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(HOTSPOT_CIRCLE)) map.setLayoutProperty(HOTSPOT_CIRCLE, 'visibility', showHotspots && map.getZoom() > 5.5 ? 'visible' : 'none')
    }
    map.on('zoom', handleZoom)
    const handleIdle = () => {
      if (map.getLayer(PROVINCE_FILL)) map.setLayoutProperty(PROVINCE_FILL, 'visibility', map.getZoom() < 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(PROVINCE_LINE)) map.setLayoutProperty(PROVINCE_LINE, 'visibility', map.getZoom() < 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(RISK_FILL)) map.setLayoutProperty(RISK_FILL, 'visibility', map.getZoom() >= 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(RISK_LINE)) map.setLayoutProperty(RISK_LINE, 'visibility', map.getZoom() >= 5.5 && showRisk ? 'visible' : 'none')
      if (map.getLayer(HOTSPOT_CIRCLE)) map.setLayoutProperty(HOTSPOT_CIRCLE, 'visibility', showHotspots && map.getZoom() > 5.5 ? 'visible' : 'none')
      if (map.getLayer('hotspot-cluster-circles')) map.setLayoutProperty('hotspot-cluster-circles', 'visibility', showHotspots ? 'visible' : 'none')
      if (map.getLayer('hotspot-cluster-circles')) map.setLayoutProperty('hotspot-cluster-circles', 'visibility', showHotspots ? 'visible' : 'none')
    }
    map.on('idle', handleIdle)
    return () => {
      map.off('mousemove', handleMove)
      canvas.removeEventListener('mouseleave', handleLeave)
      map.off('click', handleClick)
      map.off('zoom', handleZoom)
      map.off('idle', handleIdle)
      canvas.style.cursor = ''
    }
  }, [dataState, mapState, onHoverCell, onHoverProvince, onSelectCell, onSelectProvince, showHotspots, showRisk])

  useEffect(() => {
    const map = mapRef.current
    if (!map || mapState !== 'ready') return
    if (map.getLayer(SELECTED_CELL_LAYER)) {
      map.setFilter(SELECTED_CELL_LAYER, ['==', ['get', 'cell_id'], selectedCell?.cell_id ?? -1])
    }
    if (selectedCell) map.easeTo({ center: selectedCell.coordinates, duration: 350 })
  }, [selectedCell, mapState])

  return (
    <div className="map-root">
      <div ref={containerRef} className="map-canvas" role="application" aria-label="Peta risiko. Gunakan tombol tab untuk memilih kontrol periode dan lapisan. Klik sel risiko untuk membuka rinciannya." />
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

function DetailCard({ cell, onClose }: { cell: SelectedCell; onClose: () => void }) {
  const bars = Array.from({ length: 20 }, (_, index) => index < Math.round(cell.score * 20))
  const impactLow = 40 + (cell.cell_id % 80)
  const impactHigh = impactLow + 180 + (cell.level * 60)
  const levelClass = `risk-level-${cell.level}`

  return (
    <aside className="cell-detail bracket-panel" aria-label={`Detail sel ${cell.cell_id}`}>
      <header className="detail-header">
        <div><span className="eyebrow">DETAIL SEL · DATA CONTOH</span><h2>{cell.province}</h2></div>
        <button type="button" className="icon-button close-detail" aria-label="Tutup detail sel" onClick={onClose}>×</button>
      </header>
      <div className="detail-cell-id">SEL {cell.cell_id} <span>·</span> {cell.island.toUpperCase()}</div>
      <div className={`level-chip ${levelClass}`}><span className="level-bars" aria-hidden="true">{[1, 2, 3, 4].map((bar) => <i key={bar} className={bar <= cell.level ? 'filled' : ''} />)}</span>{riskLevelName(cell.level)}</div>
      <section className="detail-section" aria-label="Skor risiko contoh">
        <div className="section-heading"><span className="eyebrow">SKOR RISIKO</span><strong>{Math.round(cell.score * 100)}%</strong></div>
        <div className="segmented-meter" aria-label={`Skor contoh ${Math.round(cell.score * 100)} persen`}>{bars.map((filled, index) => <i key={index} className={filled ? levelClass : ''} />)}</div>
      </section>
      <section className="detail-section">
        <div className="section-heading"><span className="eyebrow">FAKTOR PENDORONG</span><span className="sample-inline">DATA CONTOH</span></div>
        <ul className="driver-list">{cell.drivers.slice(0, 3).map((driver) => <li key={driver}>{driver}</li>)}</ul>
      </section>
      <section className="detail-section weekly-section">
        <div className="section-heading"><span className="eyebrow">HOTSPOT 7 HARI</span><span className="sample-inline">DATA CONTOH</span></div>
        <div className="weekly-chart" role="img" aria-label="Grafik batang simulasi hotspot tujuh hari">
          {weeklyBars.map((height, index) => <span key={index} style={{ height: `${Math.round(height * 100)}%` }}><i /></span>)}
        </div>
        <div className="chart-days"><span>7 HARI LALU</span><span>TERBARU</span></div>
      </section>
      <div className="detail-metric"><span className="eyebrow">PERKIRAAN LAHAN GAMBUT</span><strong>{cell.peat_pct}%</strong></div>
      <section className="impact-card">
        <div className="section-heading"><span className="eyebrow">PERKIRAAN AREA TERDAMPAK</span><span className="uncertainty-mark" aria-label="Rentang tidak pasti">±</span></div>
        <span className="sample-inline">DATA CONTOH · BUKAN ANGKA NYATA</span>
        <strong className="impact-range">{impactLow}–{impactHigh} <small>ha</small></strong>
        <div className="impact-range-track" aria-hidden="true"><i /><b /></div>
        <p>Rentang contoh untuk menunjukkan ketidakpastian. Bukan hasil pengukuran.</p>
      </section>
    </aside>
  )
}

function ProvinceOverviewCard({ province, isSample, onClose }: { province: SelectedProvince; isSample: boolean; onClose: () => void }) {
  const level = (province.level ?? 0) as 0 | 1 | 2 | 3 | 4
  const hasData = province.has_data !== false && level >= 1
  const levelClass = hasData ? `level-${level}` : ''
  const cellCount = province.cell_count ?? 0
  const highCount = province.high_count ?? 0
  const veryHighCount = province.very_high_count ?? 0
  const riskAreaHa = province.risk_area_ha ?? 0
  const sharePct = cellCount > 0 ? Math.round(((highCount + veryHighCount) / cellCount) * 100) : 0

  return (
    <aside className="cell-detail bracket-panel" aria-label={`Ikhtisar provinsi ${province.province}`}>
      <header className="detail-header">
        <div><span className="eyebrow">IKHTISAR WILAYAH{isSample ? ' · DATA CONTOH' : ''}</span><h2>{province.province}</h2></div>
        <button type="button" className="icon-button close-detail" aria-label="Tutup ikhtisar wilayah" onClick={onClose}>×</button>
      </header>
      {!hasData ? (
        <p className="province-empty">Belum ada data risiko untuk wilayah ini pada periode yang dipilih.</p>
      ) : (
        <>
          <div className={`level-chip ${levelClass}`}><span className="level-bars" aria-hidden="true">{[1, 2, 3, 4].map((bar) => <i key={bar} className={bar <= level ? 'filled' : ''} />)}</span>{riskLevelName(level)}</div>
          <section className="detail-section" aria-label="Kondisi wilayah">
            <div className="section-heading"><span className="eyebrow">KONDISI WILAYAH</span><strong>{Math.round((province.score ?? 0) * 100)}%</strong></div>
            <p className="province-summary">
              {veryHighCount + highCount > 0
                ? `Terdeteksi ${veryHighCount + highCount} titik berisiko tinggi hingga sangat tinggi dari ${cellCount} sel terpantau. Waspadai potensi karhutla pada titik tersebut.`
                : `Tidak ada titik berisiko tinggi dari ${cellCount} sel terpantau. Kondisi relatif terkendali.`}
            </p>
          </section>
          <div className="detail-metric"><span className="eyebrow">TITIK RISIKO TINGGI</span><strong>{highCount} <small>sel</small></strong></div>
          <div className="detail-metric"><span className="eyebrow">TITIK SANGAT TINGGI</span><strong>{veryHighCount} <small>sel</small></strong></div>
          <div className="detail-metric"><span className="eyebrow">CAKUPAN AREA DIPANTAU</span><strong>{sharePct}% <small>berisiko</small></strong></div>
          <section className="impact-card">
            <div className="section-heading"><span className="eyebrow">PERKIRAAN LUAS AREA BERISIKO KARHUTLA</span></div>
            {isSample && <span className="sample-inline">DATA CONTOH · BUKAN ANGKA NYATA</span>}
            <strong className="impact-range">{riskAreaHa.toLocaleString('id-ID')} <small>ha</small></strong>
            <div className="impact-range-track" aria-hidden="true"><i /><b /></div>
            <p>Akumulasi luas sel pemantauan di wilayah ini. Indikasi area yang berpotensi mengalami kebakaran hutan dan lahan.</p>
          </section>
        </>
      )}
    </aside>
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
  // nonaktifkan sementara: state toggle lapisan (LAPISAN selalu aktif)
  const showRisk = true
  const showHotspots = true
  const [hoverProvince, setHoverProvince] = useState<ProvinceHover | null>(null)
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null)
  const [selectedProvince, setSelectedProvince] = useState<SelectedProvince | null>(null)
  const [hoverCell, setHoverCell] = useState<HoverCell | null>(null)
  const [layers, setLayers] = useState<MapLayers | null>(null)
  const [meta, setMeta] = useState<DataMeta | null>(null)
  const [, setDataState] = useState<DataState>('loading')
  const [staleHours, setStaleHours] = useState<number | null>(null)
  const [, setMapSummary] = useState({ high: 0, veryHigh: 0 })
  const mapInstanceRef = useRef<MapLibreMap | null>(null)
  // nonaktifkan sementara: state dock/layers/topRegions
  const [legendOpen, setLegendOpen] = useState(false)
  const legendRef = useRef<HTMLDivElement | null>(null)

  const handleSelectCell = useCallback((cell: SelectedCell) => {
    setSelectedCell(cell)
    setSelectedProvince(null)
    setHoverCell(null)
  }, [])
  const handleSelectProvince = useCallback((province: SelectedProvince) => {
    setSelectedProvince(province)
    setSelectedCell(null)
    setHoverCell(null)
    setHoverProvince(null)
  }, [])
  const handleHoverCell = useCallback((cell: HoverCell | null) => setHoverCell(cell), [])
  const handleHoverProvince = useCallback((hover: ProvinceHover | null) => setHoverProvince(hover), [])
  const handleMapReady = useCallback((map: MapLibreMap | null) => { mapInstanceRef.current = map }, [])

  useEffect(() => {
    document.title = isMethodPage ? 'Metode dan data | HOTSPOT.ID' : isLandingPage ? 'HOTSPOT.ID | Risiko munculnya hotspot' : 'HOTSPOT.ID | Peta risiko munculnya hotspot'
  }, [isMethodPage, isLandingPage])

  useEffect(() => {
    let cancelled = false
    window.setTimeout(() => setDataState('loading'), 0)
    void loadMapData(horizon).then((data) => {
      if (cancelled) return
      setLayers({ risk: data.risk, hotspots: data.hotspots, provinces: data.provinces })
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

  // Deep-link from WilayahPage: /peta?provinsi=Nama — zoom ke wilayah itu dan buka overview.
  useEffect(() => {
    if (!isMapPage || !layers || !mapInstanceRef.current) return
    const params = new URLSearchParams(window.location.search)
    const target = params.get('provinsi')
    if (!target) return
    const province = layers.provinces.features.find(
      (feature) => feature.properties.province.toLocaleLowerCase('id') === target.toLocaleLowerCase('id')
    )
    if (!province) return
    const bounds = new maplibregl.LngLatBounds()
    const extend = (coords: unknown) => {
      if (!Array.isArray(coords)) return
      if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        bounds.extend(coords as [number, number])
        return
      }
      for (const child of coords) extend(child)
    }
    extend(province.geometry.coordinates)
    if (bounds.isEmpty()) return
    mapInstanceRef.current.fitBounds(bounds, { padding: 80, maxZoom: 7.5, duration: 800 })
    const sw = bounds.getSouthWest()
    const ne = bounds.getNorthEast()
    const selected: SelectedProvince = { ...province.properties, coordinates: [(sw.lng + ne.lng) / 2, (sw.lat + ne.lat) / 2] }
    queueMicrotask(() => {
      setSelectedProvince(selected)
      setSelectedCell(null)
    })
    window.history.replaceState({}, '', '/peta')
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

  // nonaktifkan sementara: selectFromList dan topRegions dipakai di dock bawah/wilayah teratas yang disembunyikan
  if (isMethodPage) return <MethodPage />
  if (isWilayahPage) return <WilayahPage />
  if (isRiwayatPage) return <RiwayatPage />
  if (isLandingPage) return <LandingPage />
  if (isMethodPage) return <MethodPage />
  if (!isMapPage) return null

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
          <div className={`map-stage${selectedCell || selectedProvince ? ' has-selection' : ''}`}>
          {/* nonaktifkan sementara: panel wilayah teratas desktop/mobile */}
          <MapView
            layers={layers}
            showRisk={showRisk}
            showHotspots={showHotspots}
            selectedCell={selectedCell}
            onMapReady={handleMapReady}
            onSelectCell={handleSelectCell}
            onSelectProvince={handleSelectProvince}
            onHoverCell={handleHoverCell}
            onHoverProvince={handleHoverProvince}
            onSummary={setMapSummary}
          />
          {/* nonaktifkan sementara: strip ringkasan map */}
          <div className="map-lower-left">
            <p className="map-limitation">Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.</p>
            <div className="legend-popover-wrap" ref={legendRef}>
              <button className="legend-trigger" type="button" aria-expanded={legendOpen} aria-haspopup="true" onClick={() => setLegendOpen((open) => !open)}>LEGENDA</button>
              {legendOpen && <aside className="legend-popover" aria-label="Legenda risiko">
                <RiskLegend showHotspot />
              </aside>}
            </div>
          </div>
          {hoverProvince && <div className="map-tooltip province-tooltip" style={{ left: hoverProvince.point[0], top: hoverProvince.point[1] }} role="status"><strong>{hoverProvince.properties.province}</strong>{!hoverProvince.properties.has_data ? <span>TANPA DATA</span> : <><span className={`tooltip-level risk-text-${hoverProvince.properties.level}`}>{riskLevelName(hoverProvince.properties.level ?? 1)} <span className="level-bars" aria-hidden="true">{[1, 2, 3, 4].map((bar) => <i key={bar} className={bar <= (hoverProvince.properties.level ?? 1) ? 'filled' : ''} />)}</span></span><span>SEL TINGGI {hoverProvince.properties.high_count ?? 0}</span><span>SEL SANGAT TINGGI {hoverProvince.properties.very_high_count ?? 0}</span></>}</div>}
          {hoverCell && !hoverProvince && !selectedCell && <div className="map-tooltip" style={{ left: hoverCell.point[0], top: hoverCell.point[1] }} role="status"><span className={`tooltip-level risk-text-${hoverCell.properties.level}`}>{riskLevelName(hoverCell.properties.level)}</span><strong>{hoverCell.properties.province}</strong><span>SKOR CONTOH {Math.round(hoverCell.properties.score * 100)}%</span></div>}
          {selectedCell && <DetailCard cell={selectedCell} onClose={() => setSelectedCell(null)} />}
          {!selectedCell && selectedProvince && <ProvinceOverviewCard province={selectedProvince} isSample={meta?.is_sample ?? false} onClose={() => setSelectedProvince(null)} />}
          {/* nonaktifkan sementara: menu lapisan */}
          <div className="map-control-stack">
            <fieldset className="horizon-control"><legend className="sr-only">PERIODE</legend><div className="horizon-options">{HORIZONS.filter((item) => item.key !== 'd3').map((item) => <button className={`horizon-button${horizon === item.key ? ' is-selected' : ''}`} key={item.key} type="button" aria-pressed={horizon === item.key} onClick={() => { setHorizon(item.key); setSelectedCell(null); setSelectedProvince(null) }}>{item.label}<small>{new Date(Date.parse(meta?.generated_at ?? '2026-10-30T00:00:00Z') + HORIZONS.findIndex((entry) => entry.key === item.key) * 86400000).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', timeZone: 'Asia/Jakarta' }).toUpperCase()}</small></button>)}</div></fieldset>
          </div>
          {/* nonaktifkan sementara: tombol dan popover LAPISAN */}
        </div>
      </section>

      {/* nonaktifkan sementara: dock bawah daftar wilayah */}
      <span className="sr-only" aria-live="polite">Peta {HORIZONS.find((item) => item.key === horizon)?.label} dipilih{selectedCell ? `, sel ${selectedCell.cell_id} dipilih` : ''}.</span>
    </main>
  )
}

export default App

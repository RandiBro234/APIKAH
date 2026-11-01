import type { FeatureCollection, Point, Polygon } from 'geojson'

export type RiskLevel = 1 | 2 | 3 | 4

export type RiskProperties = {
  cell_id: number
  level: RiskLevel
  score: number
  province: string
  island: string
  drivers: string[]
  peat_pct: number
}

export type HotspotProperties = {
  time_local: string
  confidence: 'l' | 'n' | 'h'
  frp: number
}

export type RiskFeatureCollection = FeatureCollection<Polygon, RiskProperties>
export type HotspotFeatureCollection = FeatureCollection<Point, HotspotProperties>

export type ProvinceProperties = {
  province: string
  source_name?: string
  shape_iso: string
  shape_id: string
  level?: RiskLevel
  score?: number
  high_count?: number
  very_high_count?: number
  has_data?: boolean
  cell_count?: number
  island?: string
  risk_area_ha?: number
}

export type DataMeta = {
  generated_at: string
  data_hotspot_latest_at: string
  model_version: string
  data_version: string
  stale_after_hours: number
  is_sample: boolean
}

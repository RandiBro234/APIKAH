import type { FeatureCollection, MultiPolygon, Point, Polygon } from 'geojson'

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

// --- Kabupaten/kota (ADM2). Lihat docs/KONTRAK-DATA-KABUPATEN.md ---

export type KabupatenProperties = {
  kode: string
  kabupaten: string
  provinsi: string
  has_data?: boolean
  level?: RiskLevel
  score?: number
  n_sel?: number
  n_sel_penuh?: number
  cakupan_pct?: number
  luas_kabupaten_ha?: number
  luas_terdampak_ha_min?: number
  luas_terdampak_ha_max?: number
  hotspot_72h?: number
  unmatched?: boolean
}

export type KabupatenFeatureCollection = FeatureCollection<Polygon | MultiPolygon, KabupatenProperties>

export type KabupatenRiskRecord = KabupatenProperties

export type KabupatenRiskFile = {
  periode: string
  horizon: string
  sumber: string
  is_mock: boolean
  kabupaten: KabupatenRiskRecord[]
}

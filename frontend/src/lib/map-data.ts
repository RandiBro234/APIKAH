import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { provinceSlug } from './slug'
import type {
  DataMeta,
  HotspotFeatureCollection,
  KabupatenFeatureCollection,
  KabupatenRiskFile,
  KabupatenRiskRecord,
  ProvinceProperties,
  RiskFeatureCollection,
  RiskProperties,
} from '../types/geojson'

export type RiskMapFeature = FeatureCollection<Polygon | MultiPolygon, RiskProperties>['features'][number]
export type RiskMapCollection = FeatureCollection<Polygon | MultiPolygon, RiskProperties>
export type ProvinceFeature = FeatureCollection<MultiPolygon | Polygon, ProvinceProperties>['features'][number]
export type ProvinceFeatureCollection = FeatureCollection<MultiPolygon | Polygon, ProvinceProperties>

type RiskFile = RiskFeatureCollection & {
  aggregate?: RiskFeatureCollection
  horizon?: string
  prediction_date?: string
  model_version?: string
}

// Approximate geodesic area of a polygon ring in hectares (planar approximation
// on the sphere is overkill for small grid cells).
function ringAreaHectares(ring: number[][]): number {
  let sum = 0
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i]
    const [x2, y2] = ring[i + 1]
    sum += x1 * y2 - x2 * y1
  }
  const areaDeg = Math.abs(sum) / 2
  const midLat = ring.reduce((acc, point) => acc + point[1], 0) / ring.length
  const kmPerDegLat = 110.574
  const kmPerDegLng = 111.32 * Math.cos((midLat * Math.PI) / 180)
  return areaDeg * kmPerDegLat * kmPerDegLng * 100 // km^2 -> ha
}

function featureAreaHectares(feature: RiskMapFeature): number {
  const geometry = feature.geometry
  const rings = geometry.type === 'Polygon' ? [geometry.coordinates[0]] : geometry.coordinates.map((polygon) => polygon[0])
  return rings.reduce((total, ring) => total + ringAreaHectares(ring as number[][]), 0)
}

async function readJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) throw new Error(`Gagal memuat ${url}`)
  return response.json() as Promise<T>
}

function modelHorizon(horizon: string): string {
  return { d0: 'actual', d1: 'h1', d2: 'h2', d7: 'h7' }[horizon] ?? horizon
}

async function readRisk(horizon: string): Promise<RiskFile> {
  const modelKey = modelHorizon(horizon)
  try {
    return await readJson<RiskFile>(`/data/risk_${modelKey}.geojson`)
  } catch {
    const sampleHorizon = horizon === 'd7' ? 'd3' : horizon
    return readJson<RiskFile>(`/data/risk_${sampleHorizon}.sample.geojson`)
  }
}

async function readMeta(): Promise<DataMeta> {
  const meta = await readJson<Partial<DataMeta>>('/data/meta.json')
  return {
    generated_at: meta.generated_at ?? new Date(0).toISOString(),
    data_hotspot_latest_at: meta.data_hotspot_latest_at ?? new Date(0).toISOString(),
    model_version: meta.model_version ?? 'belum tersedia',
    data_version: meta.data_version ?? 'belum tersedia',
    stale_after_hours: meta.stale_after_hours ?? 24,
    is_sample: meta.is_sample ?? meta.model_version?.toLowerCase() === 'contoh',
  }
}

function enrichProvinces(
  provinces: ProvinceFeatureCollection,
  sampleRisk: RiskFile,
  horizon: string,
  fallbackToKabupaten: boolean,
): ProvinceFeatureCollection {
  return {
    ...provinces,
    features: provinces.features.map((province) => {
      const provinceRisk = sampleRisk.features.filter((cell) => cell.properties.province.toLocaleLowerCase('id') === province.properties.province.toLocaleLowerCase('id'))
      const horizonLevel = (province.properties as Record<string, unknown>)[`level_${horizon}`] as 1 | 2 | 3 | 4 | undefined
      const aggregatedLevel = horizonLevel ?? (fallbackToKabupaten ? province.properties.level : undefined)
      return {
        ...province,
        properties: {
          ...province.properties,
          has_data: aggregatedLevel !== undefined || (fallbackToKabupaten && province.properties.has_data === true),
          level: aggregatedLevel,
          score: province.properties.score ?? provinceRisk.reduce((score, cell) => Math.max(score, cell.properties.score), 0),
          high_count: provinceRisk.filter((cell) => cell.properties.level === 3).length,
          very_high_count: provinceRisk.filter((cell) => cell.properties.level === 4).length,
          cell_count: provinceRisk.length,
          island: provinceRisk[0]?.properties.island,
          risk_area_ha: Math.round(provinceRisk.reduce((total, cell) => total + featureAreaHectares(cell), 0)),
          hotspot_72h: province.properties.hotspot_72h ?? 0,
          kabupaten_terdampak: province.properties.kabupaten_terdampak ?? 0,
        },
      }
    }),
  }
}

export async function loadMapBaseData(horizon: string): Promise<{
  risk: RiskMapCollection
  hotspots: HotspotFeatureCollection
  provinces: ProvinceFeatureCollection
  kabupatenIndex: KabupatenRiskRecord[]
  meta: DataMeta
}> {
  const [sampleRisk, hotspots, provinces, meta, kabupatenRisk] = await Promise.all([
    readRisk(horizon),
    readJson<HotspotFeatureCollection>('/data/hotspots_72h.geojson').catch(() => readJson<HotspotFeatureCollection>('/data/hotspots_72h.sample.geojson')),
    readJson<ProvinceFeatureCollection>('/data/provinsi.geojson'),
    readMeta(),
    readJson<KabupatenRiskFile>('/data/kabupaten_risk.json'),
  ])

  return {
    risk: sampleRisk as RiskMapCollection,
    hotspots,
    provinces: enrichProvinces(provinces, sampleRisk, horizon, false),
    kabupatenIndex: kabupatenRisk.kabupaten,
    meta,
  }
}

export async function loadKabupatenGeojson(provinceName: string): Promise<KabupatenFeatureCollection> {
  return readJson<KabupatenFeatureCollection>(`/data/kabupaten/${provinceSlug(provinceName)}.geojson`)
}

export async function loadMapData(horizon: string): Promise<{
  risk: RiskMapCollection
  hotspots: HotspotFeatureCollection
  provinces: ProvinceFeatureCollection
  kabupaten: KabupatenFeatureCollection
  kabupatenMeta: { isMock: boolean; periode: string; horizon: string }
  meta: DataMeta
}> {
  const [sampleRisk, hotspots, provinces, meta, kabupatenGeom, kabupatenRisk] = await Promise.all([
    readRisk(horizon),
    readJson<HotspotFeatureCollection>('/data/hotspots_72h.geojson').catch(() => readJson<HotspotFeatureCollection>('/data/hotspots_72h.sample.geojson')),
    readJson<ProvinceFeatureCollection>('/data/provinsi.geojson'),
    readMeta(),
    readJson<KabupatenFeatureCollection>('/data/kabupaten.geojson'),
    readJson<KabupatenRiskFile>('/data/kabupaten_risk.json'),
  ])

  const enrichedProvinces = enrichProvinces(provinces, sampleRisk, horizon, true)

  // Gabungkan geometri ADM2 dengan angka risiko kabupaten. Angka risiko boleh
  // berupa data contoh (is_mock=true); UI wajib menandainya. Kode di berkas
  // risiko adalah ID sintetis, jadi join memakai nama kabupaten + provinsi.
  const riskByKey = new Map<string, KabupatenRiskRecord>()
  for (const row of kabupatenRisk.kabupaten) riskByKey.set(`${row.kabupaten}|${row.provinsi}`, row)

  const enrichedKabupaten: KabupatenFeatureCollection = {
    ...kabupatenGeom,
    features: kabupatenGeom.features.map((feature) => {
      const record = riskByKey.get(`${feature.properties.kabupaten}|${feature.properties.provinsi}`)
      if (!record) {
        return {
          ...feature,
          properties: { ...feature.properties, has_data: false, unmatched: true },
        }
      }
      return {
        ...feature,
        properties: {
          ...feature.properties,
          has_data: record.has_data,
          level: record.level,
          score: record.score,
          n_sel: record.n_sel,
          n_sel_penuh: record.n_sel_penuh,
          cakupan_pct: record.cakupan_pct,
          luas_kabupaten_ha: record.luas_kabupaten_ha,
          luas_terdampak_ha_min: record.luas_terdampak_ha_min,
          luas_terdampak_ha_max: record.luas_terdampak_ha_max,
          hotspot_72h: record.hotspot_72h,
          unmatched: record.unmatched,
        },
      }
    }),
  }

  return {
    risk: sampleRisk as RiskMapCollection,
    hotspots,
    provinces: enrichedProvinces,
    kabupaten: enrichedKabupaten,
    kabupatenMeta: { isMock: kabupatenRisk.is_mock, periode: kabupatenRisk.periode, horizon: kabupatenRisk.horizon },
    meta,
  }
}

export function aggregateRisks(features: RiskMapFeature[]): RiskMapCollection {
  const blocks = new Map<string, RiskMapFeature>()

  for (const feature of features) {
    const ring = feature.geometry.type === 'Polygon' ? feature.geometry.coordinates[0] : feature.geometry.coordinates[0][0]
    const points = ring.slice(0, -1)
    if (points.length === 0) continue

    const longitude = points.reduce((sum, point) => sum + point[0], 0) / points.length
    const latitude = points.reduce((sum, point) => sum + point[1], 0) / points.length
    const blockKey = `${feature.properties.island}-${Math.floor(longitude)}-${Math.floor(latitude)}`
    const previous = blocks.get(blockKey)
    if (!previous || feature.properties.level > previous.properties.level) {
      blocks.set(blockKey, feature)
    }
  }

  return {
    type: 'FeatureCollection',
    features: [...blocks.values()].map((feature) => {
      const ring = feature.geometry.coordinates[0]
      const longitudes = ring.map((point) => point[0])
      const latitudes = ring.map((point) => point[1])
      const west = Math.floor(Math.min(...longitudes))
      const east = west + 1
      const south = Math.floor(Math.min(...latitudes))
      const north = south + 1
      return {
        ...feature,
        geometry: {
          type: 'Polygon',
          coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
      }
    }),
  }
}

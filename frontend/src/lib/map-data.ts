import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'
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

type SampleRiskFile = RiskFeatureCollection & {
  aggregate?: RiskFeatureCollection
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

export async function loadMapData(horizon: string): Promise<{
  risk: RiskMapCollection
  hotspots: HotspotFeatureCollection
  provinces: ProvinceFeatureCollection
  kabupaten: KabupatenFeatureCollection
  kabupatenMeta: { isMock: boolean; periode: string; horizon: string }
  meta: DataMeta
}> {
  const [sampleRisk, hotspots, provinces, meta, kabupatenGeom, kabupatenRisk] = await Promise.all([
    readJson<SampleRiskFile>(`/data/risk_${horizon}.sample.geojson`),
    readJson<HotspotFeatureCollection>('/data/hotspots_72h.sample.geojson'),
    readJson<ProvinceFeatureCollection>('/data/provinsi.geojson'),
    readJson<DataMeta>('/data/meta.sample.json'),
    readJson<KabupatenFeatureCollection>('/data/kabupaten.geojson'),
    readJson<KabupatenRiskFile>('/data/kabupaten_risk.json'),
  ])

  const enrichedProvinces: ProvinceFeatureCollection = {
    ...provinces,
    features: provinces.features.map((province) => {
      const provinceRisk = sampleRisk.features.filter((cell) => cell.properties.province.toLocaleLowerCase('id') === province.properties.province.toLocaleLowerCase('id'))
      const maximumLevel = provinceRisk.reduce((level, cell) => Math.max(level, cell.properties.level), 0)
      return {
        ...province,
        properties: {
          ...province.properties,
          has_data: provinceRisk.length > 0,
          level: maximumLevel > 0 ? maximumLevel as 1 | 2 | 3 | 4 : undefined,
          score: provinceRisk.reduce((score, cell) => Math.max(score, cell.properties.score), 0),
          high_count: provinceRisk.filter((cell) => cell.properties.level === 3).length,
          very_high_count: provinceRisk.filter((cell) => cell.properties.level === 4).length,
          cell_count: provinceRisk.length,
          island: provinceRisk[0]?.properties.island,
          risk_area_ha: Math.round(provinceRisk.reduce((total, cell) => total + featureAreaHectares(cell), 0)),
        },
      }
    }),
  }

  // Gabungkan geometri ADM2 dengan angka risiko kabupaten. Angka risiko boleh
  // berupa data contoh (is_mock=true); UI wajib menandainya.
  const riskByKode = new Map<string, KabupatenRiskRecord>()
  for (const row of kabupatenRisk.kabupaten) riskByKode.set(row.kode, row)

  const enrichedKabupaten: KabupatenFeatureCollection = {
    ...kabupatenGeom,
    features: kabupatenGeom.features.map((feature) => {
      const record = riskByKode.get(feature.properties.kode)
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

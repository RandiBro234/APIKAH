import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

const outputDirectory = join(process.cwd(), 'public', 'data')
const generatedAt = new Date('2026-10-30T06:00:00+07:00').toISOString()
const regions = [
  { province: 'Riau', island: 'Sumatra', longitude: 101.45, latitude: 0.51, level: 4, peat: 88 },
  { province: 'Riau', island: 'Sumatra', longitude: 102.2, latitude: 0.76, level: 3, peat: 74 },
  { province: 'Riau', island: 'Sumatra', longitude: 101.7, latitude: 1.26, level: 4, peat: 92 },
  { province: 'Riau', island: 'Sumatra', longitude: 102.45, latitude: 0.26, level: 2, peat: 63 },
  { province: 'Riau', island: 'Sumatra', longitude: 100.95, latitude: 1.01, level: 3, peat: 81 },
  { province: 'Sumatera Selatan', island: 'Sumatra', longitude: 104.76, latitude: -2.99, level: 4, peat: 86 },
  { province: 'Sumatera Selatan', island: 'Sumatra', longitude: 105.25, latitude: -2.49, level: 3, peat: 72 },
  { province: 'Sumatera Selatan', island: 'Sumatra', longitude: 103.95, latitude: -3.24, level: 2, peat: 57 },
  { province: 'Jambi', island: 'Sumatra', longitude: 103.61, latitude: -1.59, level: 3, peat: 79 },
  { province: 'Jambi', island: 'Sumatra', longitude: 104.11, latitude: -1.34, level: 2, peat: 65 },
  { province: 'Kalimantan Barat', island: 'Kalimantan', longitude: 109.34, latitude: -0.02, level: 3, peat: 77 },
  { province: 'Kalimantan Barat', island: 'Kalimantan', longitude: 110.09, latitude: -0.52, level: 4, peat: 91 },
  { province: 'Kalimantan Barat', island: 'Kalimantan', longitude: 109.84, latitude: 0.48, level: 2, peat: 61 },
  { province: 'Kalimantan Tengah', island: 'Kalimantan', longitude: 113.92, latitude: -2.21, level: 4, peat: 89 },
  { province: 'Kalimantan Tengah', island: 'Kalimantan', longitude: 114.42, latitude: -2.71, level: 3, peat: 82 },
  { province: 'Kalimantan Tengah', island: 'Kalimantan', longitude: 113.17, latitude: -2.46, level: 2, peat: 59 },
  { province: 'Kalimantan Timur', island: 'Kalimantan', longitude: 117.15, latitude: 0.52, level: 2, peat: 44 },
  { province: 'Papua Selatan', island: 'Papua', longitude: 140.4, latitude: -8.49, level: 1, peat: 28 },
  { province: 'Aceh', island: 'Sumatra', longitude: 97.15, latitude: 4.15, level: 1, peat: 19 },
  { province: 'Kalimantan Utara', island: 'Kalimantan', longitude: 116.1, latitude: 3.35, level: 1, peat: 22 },
]
const drivers = [
  'Beberapa hari terakhir tercatat sedikit hujan.',
  'Lahan gambut di sekitar sel dapat mengering saat kemarau.',
  'Riwayat deteksi hotspot setempat turut diperhitungkan.',
]
const levelScores = { 1: 0.06, 2: 0.18, 3: 0.37, 4: 0.62 }
const horizonOffsets = [0, 0, 0, 0]

function cellId(latitude, longitude) {
  const latIndex = Math.floor((latitude + 12) / 0.25)
  const lonIndex = Math.floor((longitude - 94) / 0.25)
  return latIndex * 1000 + lonIndex
}

function polygonFor(region, offset) {
  const longitude = region.longitude + offset * 0.25
  const latitude = region.latitude + offset * 0.25
  const halfCell = 0.125
  return [[
    [longitude - halfCell, latitude - halfCell],
    [longitude + halfCell, latitude - halfCell],
    [longitude + halfCell, latitude + halfCell],
    [longitude - halfCell, latitude + halfCell],
    [longitude - halfCell, latitude - halfCell],
  ]]
}

function levelFromScore(score) {
  if (score < 0.1) return 1
  if (score < 0.25) return 2
  if (score < 0.5) return 3
  return 4
}

function riskCollection(horizonIndex) {
  const riskFeatures = regions.map((region, index) => {
    const score = levelScores[Math.max(1, Math.min(4, region.level + (horizonIndex === 0 ? 0 : ((index + horizonIndex) % 3 === 0 ? -1 : 0))))]
    const level = levelFromScore(score)
    const longitude = region.longitude + horizonOffsets[horizonIndex]
    const latitude = region.latitude

    return {
      type: 'Feature',
      id: cellId(latitude, longitude),
      properties: {
        cell_id: cellId(latitude, longitude),
        level,
        score,
        province: region.province,
        island: region.island,
        drivers: drivers.slice(0, 3),
        peat_pct: region.peat,
      },
      geometry: {
        type: 'Polygon',
        coordinates: polygonFor({ ...region, longitude, latitude }, 0),
      },
    }
  })

  const blocks = new Map()
  for (const feature of riskFeatures) {
    const coordinates = feature.geometry.coordinates[0]
    const centerLongitude = coordinates.reduce((sum, point) => sum + point[0], 0) / coordinates.length
    const centerLatitude = coordinates.reduce((sum, point) => sum + point[1], 0) / coordinates.length
    const blockKey = `${feature.properties.island}-${Math.floor(centerLongitude)}-${Math.floor(centerLatitude)}`
    const current = blocks.get(blockKey)
    if (!current || feature.properties.level > current.properties.level) {
      blocks.set(blockKey, {
        ...feature,
        properties: { ...feature.properties, cell_id: Number(`${horizonIndex + 1}${blocks.size + 1}`) },
      })
    }
  }

  return {
    type: 'FeatureCollection',
    features: riskFeatures,
    aggregate: { type: 'FeatureCollection', features: [...blocks.values()] },
  }
}

const meta = {
  generated_at: generatedAt,
  data_hotspot_latest_at: generatedAt,
  model_version: 'contoh',
  data_version: 'contoh-statis-v2',
  stale_after_hours: 24,
  is_sample: true,
}
const hotspots = {
  type: 'FeatureCollection',
  features: regions.filter((region) => region.island !== 'Papua' && region.level >= 2).slice(0, 14).map((region, index) => ({
    type: 'Feature',
    id: index + 1,
    properties: {
      time_local: new Date(Date.parse(generatedAt) - index * 2 * 60 * 60 * 1000).toISOString(),
      confidence: ['h', 'n', 'l'][index % 3],
      frp: [8, 22, 46, 74, 115, 185][index % 6],
    },
    geometry: {
      type: 'Point',
      coordinates: [region.longitude + ((index % 3) - 1) * 0.06, region.latitude + ((index % 2) ? 0.05 : -0.05)],
    },
  })),
}

await mkdir(outputDirectory, { recursive: true })
await writeFile(join(outputDirectory, 'meta.sample.json'), `${JSON.stringify(meta, null, 2)}\n`)
await writeFile(join(outputDirectory, 'hotspots_72h.sample.geojson'), `${JSON.stringify(hotspots, null, 2)}\n`)

for (const [index, horizon] of ['d0', 'd1', 'd2', 'd3'].entries()) {
  await writeFile(join(outputDirectory, `risk_${horizon}.sample.geojson`), `${JSON.stringify(riskCollection(index), null, 2)}\n`)
}

process.stdout.write(`Data contoh dibuat di ${outputDirectory}\n`)

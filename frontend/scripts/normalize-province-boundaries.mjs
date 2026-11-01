import { readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

const filePath = join(process.cwd(), 'public', 'data', 'provinsi.geojson')
const provinceNames = {
  'Bangka-Belitung Islands': 'Kepulauan Bangka Belitung',
  'Central Java': 'Jawa Tengah',
  'Central Kalimantan': 'Kalimantan Tengah',
  'Central Sulawesi': 'Sulawesi Tengah',
  'East Java': 'Jawa Timur',
  'East Kalimantan': 'Kalimantan Timur',
  'East Nusa Tenggara': 'Nusa Tenggara Timur',
  'Jakarta Special Capital Region': 'DKI Jakarta',
  'North Kalimantan': 'Kalimantan Utara',
  'North Maluku': 'Maluku Utara',
  'North Sulawesi': 'Sulawesi Utara',
  'North Sumatra': 'Sumatera Utara',
  'Riau Islands': 'Kepulauan Riau',
  'South Kalimantan': 'Kalimantan Selatan',
  'South Sulawesi': 'Sulawesi Selatan',
  'South Sumatra': 'Sumatera Selatan',
  'Southeast Sulawesi': 'Sulawesi Tenggara',
  'Special Region of Yogyakarta': 'DI Yogyakarta',
  'West Java': 'Jawa Barat',
  'West Kalimantan': 'Kalimantan Barat',
  'West Nusa Tenggara': 'Nusa Tenggara Barat',
  'West Papua': 'Papua Barat',
  'West Sulawesi': 'Sulawesi Barat',
  'West Sumatra': 'Sumatera Barat',
}

const data = JSON.parse(await readFile(filePath, 'utf8'))
for (const feature of data.features) {
  const originalName = feature.properties.province
  feature.properties.source_name = originalName
  feature.properties.province = provinceNames[originalName] ?? originalName
}
await writeFile(filePath, `${JSON.stringify(data)}\n`)
process.stdout.write(`Nama ${data.features.length} provinsi dinormalkan.\n`)

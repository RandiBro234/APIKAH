# Kontrak Data: Kabupaten/Kota (ADM2)

**Status:** draf untuk disepakati bersama pemilik pipeline data.
**Konteks:** mockup memakai data contoh, tetapi bentuk datanya harus sama dengan yang nanti
dihasilkan pipeline nyata. Dokumen ini adalah spesifikasi itu.

## 1. Sumber batas wilayah

| Butir | Nilai |
| --- | --- |
| Dataset | geoBoundaries gbOpen, `IDN`, `ADM2` |
| Nama resmi | *regency, city* |
| Tahun representasi | 2020 |
| Jumlah unit | **519** |
| Lisensi | CC BY 3.0 IGO (atribusi) — boleh dipakai di repo publik |
| Asal data | BPS, World Food Programme, OCHA ROAP |

**Catatan jumlah.** 519 adalah hitungan dataset ini untuk tahun 2020. Jumlah kabupaten/kota
berubah karena pemekaran, dan skema provinsi di `data/hotspot_indonesia` masih **34 provinsi**
(pra-pemekaran Papua 2022). Karena itu:

- Jangan pernah menuliskan jumlah 519 (atau 514) sebagai konstanta di kode.
- Kabupaten di provinsi hasil pemekaran bisa **tidak cocok** saat join; catat sebagai
  `unmatched` dan tampilkan, jangan dibuang diam-diam.
- Simpan `provinsi` hasil join dari poligon, bukan dari kolom hotspot.

**Catatan performa.** Rata-rata 7.366 verteks per unit, maksimum 216.482. Untuk mockup dan
peta web, gunakan berkas **`_simplified`** dari geoBoundaries. Target: total < 5 MB agar
halaman tetap responsif dengan 519 poligon.

## 2. Berkas yang dibutuhkan mockup

Dua artefak, keduanya disimpan di `data/geo/`:

1. `adm2_idn_simplified.geojson` — poligon kabupaten/kota, properti minimal:
   `kabupaten`, `provinsi`, `luas_km2`.
2. `adm2_risk.json` — keluaran agregasi per kabupaten (skema di bagian 3).

## 3. Skema `adm2_risk.json`

```json
{
  "periode": "2026-11-04",
  "horizon": "h1",
  "sumber": "model-per-provinsi",
  "is_mock": true,
  "kabupaten": [
    {
      "kode": "IDN-ADM2-0001",
      "kabupaten": "Contoh Kabupaten",
      "provinsi": "Riau",
      "has_data": true,
      "level": 3,
      "score": 0.42,
      "n_sel": 8,
      "n_sel_penuh": 6,
      "cakupan_pct": 71.4,
      "luas_kabupaten_ha": 812000,
      "luas_terdampak_ha_min": 187500,
      "luas_terdampak_ha_max": 312500,
      "hotspot_72h": 14,
      "unmatched": false
    }
  ]
}
```

### Arti tiap medan

| Medan | Tipe | Wajib | Arti |
| --- | --- | --- | --- |
| `kode` | string | ya | ID unik dari dataset batas |
| `kabupaten` | string | ya | nama kabupaten/kota |
| `provinsi` | string | ya | provinsi hasil join poligon |
| `has_data` | bool | ya | `false` bila tidak ada sel berprediksi di wilayah ini |
| `level` | 1–4 | bila `has_data` | level risiko agregat |
| `score` | 0–1 | bila `has_data` | skor agregat **setelah normalisasi lintas provinsi** |
| `n_sel` | int | ya | jumlah sel yang menyentuh kabupaten ini (termasuk sebagian) |
| `n_sel_penuh` | int | ya | jumlah sel yang **seluruhnya** di dalam kabupaten |
| `cakupan_pct` | float | ya | persen luas kabupaten yang tercakup sel berisiko |
| `luas_kabupaten_ha` | int | ya | luas wilayah kabupaten |
| `luas_terdampak_ha_min` | int | bila `has_data` | batas bawah rentang luas terdampak |
| `luas_terdampak_ha_max` | int | bila `has_data` | batas atas rentang luas terdampak |
| `hotspot_72h` | int | ya | jumlah deteksi VIIRS nyata 72 jam terakhir |
| `unmatched` | bool | ya | `true` bila poligon gagal dicocokkan ke skema provinsi |

### Aturan yang wajib dipatuhi

1. **`luas_terdampak_ha_max ≤ luas_kabupaten_ha`.** Ini invariant keras, bukan saran.
   Satu sel 0,25° = 625 km² = 62.500 ha; tanpa fraksi cakupan, satu kabupaten bisa
   "mendapat" luas terdampak yang melampaui luas wilayahnya sendiri.
2. **`n_sel_penuh ≤ n_sel`.**
3. **`cakupan_pct` dihitung dari luas, bukan dari jumlah sel.** Kabupaten dengan 3 sel
   sebagian kecil bisa punya cakupan lebih kecil daripada kabupaten dengan 1 sel penuh.
4. **`score` sudah dinormalisasi.** Model dilatih per provinsi, sehingga skor mentah antar
   provinsi tidak sebanding. Normalisasi dilakukan **sebelum** kabupaten diranking.
5. **Tanpa `has_data` atau tanpa `score`**, jangan kirim `level` — biar UI membedakan
   "tidak berisiko" dari "tidak punya data".

## 4. Pembagian tanggung jawab

| Pihak | Menyediakan |
| --- | --- |
| Pipeline data | `adm2_idn_simplified.geojson`, `adm2_risk.json` dengan angka nyata |
| Mockup | Skema ini sebagai spesifikasi + fixture contoh yang **lolos semua aturan di atas** |

## 5. Cara mengunduh batas wilayah

Sandbox pengembangan tidak punya akses jaringan, jadi unduhan dilakukan manual:

- Versi ringan (disarankan):
  `https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IDN/ADM2/geoBoundaries-IDN-ADM2_simplified.geojson`
- Versi penuh (berat, hanya untuk pengolahan):
  `.../geoBoundaries-IDN-ADM2.geojson`

Simpan sebagai `data/geo/adm2_idn_simplified.geojson`.

> Snapshot audit label 2026-10-25. Path/status dapat berubah; gunakan dokumentasi pipeline terkini sebelum menjalankan.

# APIKAH — data label hotspot, ganti sensor, ENSO, dan cakupan fitur

Diperiksa: 2026-10-25

## Sumber

| Path | Isi |
|---|---|
| `APIKAH/data/hotspot_indonesia_2012_2026-09.parquet` | **3.941.038 baris**, 11 kolom. Agregat utama |
| `APIKAH/data/hotspot_indonesia_2012_2026-09.csv` | data sama dalam CSV (80,4 MB) — **redundan** |
| `APIKAH/data/hotspot_indonesia/` | 177 file per bulan (versi Indonesia) |
| `APIKAH/data/hotspot_raw/` | 178 file per bulan (superset; tanpa kolom `provinsi`, `produk`) |

Kolom agregat: `latitude, longitude, acq_date, acq_time, confidence, frp, bright_ti4,
daynight, satellite, provinsi, produk`

Catatan: `hotspot_raw` superset `hotspot_indonesia` (4.670.591 vs 3.941.039 baris).
Parquet agregat = gabungan `hotspot_indonesia/` (selisih 1 baris). Jadi ~243 MB dari 345 MB
di `data/` adalah duplikat/derivatif.

## Sebaran hotspot per tahun

Median 192.281. Tahun ekstrem (≥2× median) ditandai **tebal**.

| Tahun | Hotspot | vs median | |
|---|---|---|---|
| 2012 | 317.705 | 1,65× | tinggi |
| 2013 | 256.871 | 1,34× | |
| **2014** | **551.669** | **2,87×** | **ekstrem** |
| **2015** | **874.521** | **4,55×** | **ekstrem (terparah)** |
| 2016 | 116.629 | 0,61× | |
| 2017 | 90.433 | 0,47× | sangat rendah |
| 2018 | 192.281 | 1,00× | median |
| **2019** | **436.391** | **2,27×** | **ekstrem** |
| 2020 | 92.814 | 0,48× | sangat rendah |
| 2021 | 70.654 | 0,37× | sangat rendah |
| 2022 | 63.365 | 0,33× | sangat rendah |
| 2023 | 249.838 | 1,30× | |
| 2024 | 115.609 | 0,60× | |
| 2025 | 94.026 | 0,49× | sangat rendah |
| **2026** | **418.232** | **2,18×** | **ekstrem, hanya 9 bulan** |

**4 musim ekstrem** dalam 15 tahun. Rentang sinyal 63.365 → 874.521 = **14×**.
Bandingkan setahun penuh vs Jan–Sep saja (adil untuk 2026):
2015 = 499.782 · **2026 = 418.232 (terparah kedua)** · 2014 = 379.747 · 2019 = 304.996

## Ganti sensor di tengah rekaman — masalah utama

| Produk | Rentang | Baris |
|---|---|---|
| `VIIRS_SNPP_SP` | 2012-01 → **2018-03** | 2.219.766 |
| `VIIRS_NOAA20_SP` | **2018-04** → 2026-06 | 1.337.955 |
| `VIIRS_NOAA20_NRT` | 2026-07 → 2026-10 | 383.317 (di agregat s/d Sep) |

- Pergantian SNPP → NOAA-20 terjadi tepat di batas bulan (Mar/Apr 2018)
- **Nol bulan tumpang-tindih** → perbedaan **tingkat** antar sensor **tidak bisa diestimasi**
- 2026: **91,7% NRT** (Jul–Sep), 8,3% SP (Jan–Jun). NRT = produk sementara; versi **SP**
  akan menyusul → unduh ulang sebagai SP saat tersedia
- **SNPP hilang 2018-04 → 2026-10 (~8,5 tahun)**, padahal SNPP beroperasi sampai
  **2 November 2026**. Tanpa data ini, kalibrasi silang dua sensor tidak mungkin

### Yang bisa dan tidak bisa dikatakan tentang perbedaan sensor

- **Bentuk musiman hampir identik**: korelasi SNPP vs NOAA-20 = **0,9697**; rata-rata
  selisih ~1,5 poin persen/bulan (terbesar Juni: 8,29% vs 4,03%). Artinya kalau ada
  perbedaan, itu **pengali sederhana** — jenis yang paling mudah dikoreksi
- **Pola spasial berbeda** (korelasi 0,7295; terbesar Riau: 15,92% → 4,05%) **TETAPI
  tercampur komposisi tahun** — era SNPP memuat 2015 yang terpusat di Sumatera. Jadi
  perbedaan ini **bukan bukti artefak sensor** ke arah mana pun
- **Tingkat/level**: tidak terukur (0 bulan tumpang-tindih)

## ENSO 2026 — El Niño kuat dan masih menguat

| Bulan 2026 | Niño 3.4 | Hotspot |
|---|---|---|
| Mar | +0,22 | 8.209 |
| Apr | +0,74 | 5.041 |
| Mei | +1,09 | 4.150 |
| Jun | +1,58 | 8.474 |
| Jul | +1,73 | 27.096 |
| Agu | +1,89 | 146.440 |
| Sep | **+2,09** | 209.781 |
| Okt–Des | belum terbit | — |

- Naik monoton, **belum berbalik** → musim kemungkinan berlanjut; puncak historis 2015 ada di
  **Oktober** → 2026 berpotensi melampaui 2015
- Anomali faktor Agu/Jul 2026 = **5,40×** (tahun lain 0,97–3,46×) — **nyata**, sejalan
  dengan lonjakan indeks. Bukan artefak NRT: faktor Jun→Jul (batas SP→NRT) = 3,20×,
  justru di bawah rata-rata (~3,67×)
- **DMI (IOD) baru terbit sampai Mei 2026** (+0,15) — terlambat beberapa bulan, sesuai
  peringatan di `PIPELINE_DEV.md`
- Sumber: `https://psl.noaa.gov/data/correlation/nina34.anom.data` dan
  `https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data`

## Audit cakupan waktu: fitur vs label — TIDAK ADA CELAH

Rentang label = 2012-01 → 2026-09 (15 tahun).

| Sumber | Rentang tersedia | Menutupi label |
|---|---|---|
| ERA5-Land | 1950 → 2026 (77 tahun) | ✅ 15/15 |
| CEMS Fire | 1940 → 2026 (87 tahun) | ✅ 15/15 |
| Niño 3.4 | 1948 → 2026 | ✅ |
| DMI | 1870 → 2026 | ✅ |
| MCD64A1 | → 2026-08 | ✅ (opsional, lag ~1 bulan) |
| Hansen `lossyear` | 2001 → 2025 | ✅ |

**Fitur dinamis justru lebih panjang dari label.** Yang membatasi adalah label, bukan fitur.

### Snapshot sumber statis + masalah anakronisme

| Sumber | Snapshot | Serius? |
|---|---|---|
| WorldCover | **2021** (`v200/2021`) | ringan — tutupan lahan berubah lambat |
| WorldPop | **2020** | ringan |
| OSM (Geofabrik) | **"latest" = 2026** | **paling serius** — jalan baru membuka akses hutan |
| Hansen | GFC-**2025**-v1.13 | perlu lag 1 tahun untuk `lossyear` |
| DEM 90 m | statis | tidak masalah |
| Peta gambut | statis | tidak masalah |
| geoBoundaries | sekarang | tidak masalah |

Memakai snapshot 2021/2026 untuk memprediksi 2012 = **kebocoran kovariat** (memakai informasi
masa depan), bukan kebocoran label. Mitigasi: nyatakan eksplisit di metodologi, dan uji
sensitivitas dengan/tanpa fitur statis.

## Rekomendasi modeling (hasil analisis sesi ini)

1. **JANGAN potong ke 2018+.** Alasannya:
   - 2018–2026 hanya punya **2** musim ekstrem, dan musim terbesar (2015) hilang
   - Kalau latih 2018–2025 lalu uji 2026, model diminta **ekstrapolasi** — tahun paling
     ekstrem yang pernah dilihat hanya 2019 (436.391), sedangkan 2026 lebih besar
   - Dengan 2012–2025, model sudah melihat 2015 (874.521) → 2026 menjadi **interpolasi**
   - Bukti bentuk musiman (r=0,97) mendukung bahwa perbedaan sensor itu **pengali
     sederhana** yang bisa dikoreksi
2. **Pakai `config.START = 2012` dan `END = 2026-09`** — keduanya sudah benar
3. **Pilih bentuk target yang tahan terhadap offset tingkat**: klasifikasi biner
   (ada api / tidak per sel-hari) atau target dinormalisasi. Regresi jumlah hotspot mentah
   paling rentan terhadap bias sensor
4. **Validasi wajib blocked temporal** (mis. latih 2012–2025 / uji 2026), **bukan split acak**
   — data harian punya autokorelasi kuat, split acak = kebocoran
5. **Tambahkan spatial holdout** (tahan satu provinsi) untuk uji generalisasi
6. **Metrik: PR-AUC, bukan akurasi/ROC-AUC** — api itu kejadian langka; model "tidak pernah
   ada api" bisa dapat akurasi >99%
7. **Arah angin sekarang punya alasan** (transpor asap lintas Selat Malaka). Datanya **sudah
   terunduh** (`u10`, `v10`); `postprocess_era5.py` membuangnya dengan `np.hypot(u10, v10)`.
   Cukup tambahkan kolom `u10_mean`, `v10_mean` — tidak perlu unduh ulang
8. **Untuk horizon panjang (bulanan), ENSO/IOD adalah tulang punggungnya**, bukan cuaca.
   Cuaca hanya memberi 1–3 hari; ENSO bisa diprakirakan berbulan-bulan. Jadi masuk akal
   punya **dua model**: harian (cuaca) dan bulanan (ENSO/IOD)

## Tugas tim label (bukan bagian crawler cuaca ini)

1. **Unduh SNPP 2018-04 → 2026-10 SEBELUM 2 November 2026** — mendapat 8,5 tahun
   tumpang-tindih untuk kalibrasi silang; setelah tanggal itu opsi ini hilang permanen
2. **Gabungkan Oktober 2026** — `hotspot_raw/VIIRS_NOAA20_NRT_2026-10.parquet` sudah ada
   tapi belum masuk agregat (agregat baru s/d September)
3. **Pakai SP, bukan NRT, untuk pelatihan**; unduh ulang Jul–Sep 2026 sebagai SP saat terbit
4. **Uji dengan dan tanpa 2026** untuk mengukur seberapa berbeda karakter tahun itu
5. **Pakai MCD64A1 sebagai jangkar kalibrasi** — membentang 2000–2026, melewati batas 2018;
   kalau VIIRS melompat di Apr 2018 tapi burned area MODIS tidak, berarti artefak alat
6. **Pertimbangkan fitur penanda sensor** (SNPP vs NOAA-20), lalu uji sensitivitasnya

## Cara verifikasi ulang

- Profil/agregat ringkas: tool `data_profile` pada
  `APIKAH/data/hotspot_indonesia_2012_2026-09.parquet`; pindai folder per bulan dengan
  `data_scan` pada `APIKAH/data/hotspot_indonesia`
- **Jangan** `read` file parquet/CSV di `data/` secara langsung
- ENSO: `python crawl_static.py enso --dry-run` lalu jalankan tanpa `--dry-run`
  (kecil, aman) — atau baca URL di `config.ENSO_URLS`
- Cakupan API: `python verify_params.py` (lapis 1 tanpa kredensial)
- Analisis tahunan/sensor: pakai `data_agg` dengan `time_bucket` (`year`/`month`) dan
  `group_by: ["produk"]` — tidak perlu menulis skrip groupby sendiri

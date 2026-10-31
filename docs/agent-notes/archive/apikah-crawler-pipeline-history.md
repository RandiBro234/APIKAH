> Arsip catatan sesi/riwayat. Sebagian path dan status lama; sumber kebenaran terbaru: `docs/pipeline/README.md`, `docs/superpowers/specs/`, dan `docs/superpowers/plans/`.

# APIKAH — pipeline crawler data pendukung (cuaca, iklim, lahan)

Diperiksa: 2026-10-25

## Lokasi & keadaan git

- Repo: `APIKAH/` (remote `https://github.com/RandiBro234/APIKAH`, branch `main`)
- Crawler: `APIKAH/hotspot_crawler/hotspot_crawler/` (perhatikan: folder bertingkat dua)
- HEAD lokal: `01e88cd` — sudah di-push 2026-10-25, sama dengan `origin/main`
- `.gitignore` **sudah dibuat + di-push** (`01e88cd`): mengabaikan
  `hotspot_crawler/hotspot_crawler/data/`, `data/{raw,processed,static}/` (jebakan path relatif
  `config.DATA_DIR`), `__pycache__/`, dan semua `*.nc/*.nc4/*.tif/*.pbf/*.hdf/*.zip`
- Masih **belum di-commit**: 5 file termodifikasi (`config.py`, `crawl_copernicus.py`,
  `preflight.py`, `PIPELINE_DEV.md` ×2) + untracked `verify_params.py`
- Git identity lokal repo: `faizrh26 <faizradityahadi@gmail.com>`

### Ukuran repo (terukur 2026-10-25)

| Item | Angka |
|---|---|
| File terlacak | **370** (357 di `data/`; 356 di antaranya `.parquet`) |
| pack `.git` | **223,5 MiB** |
| Terbesar | CSV 80,4 MB + parquet 75,3 MB (data sama, **duplikat**) |

- **Keputusan user 2026-10-25: JANGAN sentuh pelacakan data** — cukup `.gitignore` saja.
  Riwayat tetap 223,5 MiB; yang dihentikan hanya pertumbuhan dari crawler
- Sampah: `.git/objects/pack/tmp_pack_eLfaUF` (sisa operasi git terputus) — bersihkan
  dengan `git gc --prune=now` bila perlu
- Uji jaring pengaman: `git check-ignore -v -- <path>`; sudah diverifikasi bahwa
  `data/hotspot_indonesia_2012_2026-09.parquet` dan `verify_params.py` **tetap bisa dilacak**

## Status crawl (terakhir diperiksa 28 Okt 2026, 11:15)

**SEDANG BERJALAN -- tiga proses sekaligus:**

| Proses | PID | Isi |
|---|---|---|
| `crawl_copernicus.py all` | 8912 -> **22208** (11:15) | ERA5-Land, lalu CEMS Fire |
| `crawl_static.py all` | 10792 | lapisan statis |
| `crawl_copernicus.py era5 --from 2025-01 --to 2026-09 --tag b` | 1656 | worker kedua (uji paralel) |

PID dicatat di `data/logs/*.pid`; stderr SETIAP proses kini disalurkan ke
`data/logs/crawl_console.err` (lihat "Insiden 28 Okt" di bawah).

### Insiden 28 Okt 10:02--11:04: crawl utama mati tanpa jejak

Gejala: log `copernicus.log` berhenti di `11:04:27` **tanpa satu pun baris `GAGAL`/`ERROR`/
`Traceback`**, dan prosesnya hilang. Penyebab paling mungkin: **manifest race**. Crawl utama
waktu itu masih menjalankan KODE LAMA (manifest ditulis non-atomik), sementara worker B
menjalankan kode baru dan menulis `manifest_era5land.json` yang SAMA. Berkas terbaca separuh
-> `JSONDecodeError` -> di `run_era5()` galat itu tertangkap, lalu `manifest_update()` di blok
`except` melempar LAGI -> tidak tertangkap -> proses mati. Traceback-nya hanya muncul di
terminal pemilik proses, bukan di log berkas -- karena itu tidak ada jejak.

Dampak: **nol data hilang** (104 bulan sudah di disk; hanya request yang sedang jalan batal).
Tindakan: proses dijalankan ulang dengan kode baru (manifest atomik + toleran), jadi mode
kegagalan ini sudah ditutup. **Pelajaran: jangan campur proses kode lama dan kode baru yang
menulis berkas sama.**

### Riwayat panjang crawl dinamis

mulai 25 Okt 15:36 (PID 22492) -> berhenti 20:29 -> lanjut 26 Okt 09:28 (PID 17704) ->
berhenti 11:45 -> dilanjutkan user -> proses 28 Okt 10:02 (PID 8912) -> mati 11:04 ->
lanjut 28 Okt 11:15 (PID 22208). Semua penghentian atas permintaan user (jaringan lambat)
atau insiden di atas.

### Statis boleh jalan bareng dinamis (terbukti 28 Okt, TANPA ubah kode)

Sudah dijalankan nyata dan tidak saling ganggu, karena semuanya terpisah:

| | `crawl_copernicus.py` | `crawl_static.py` |
|---|---|---|
| Log | `copernicus.log` | `static.log` |
| Manifest | `manifest_era5land.json`, `manifest_cems_fire.json` | `manifest_static.json` |
| Output | `data/raw/` | `data/static/` |
| Batas `cost` | ada (CDS 12000, EWDS 3720) | **tidak ada** |
| Server | CDS + EWDS | Google Cloud, AWS, Geofabrik, NOAA |

### KOREKSI PENGUKURAN: yang lambat itu ECMWF, bukan jaringan user

Kesimpulan lama ("jaringan lokal jadi hambatan utama, kapasitas ~1,8 Mbps") **SALAH**.
Terukur 28 Okt: unduhan tile Hansen dari Google Cloud mencapai **~1 MB/s (~8 Mbps)**,
sementara ECMWF hanya ~126 KB/s. Jadi **endpoint ECMWF-nya** yang lambat.

Konsekuensi: (a) menjalankan lapisan statis bareng era5 praktis **gratis**; (b) memecah era5
jadi beberapa proses paralel **mungkin benar-benar mempercepat unduhan** kalau ECMWF membatasi
per koneksi -- **belum diuji**, dan ini kandidat optimasi berikutnya.

### Catatan penting: CEMS Fire ada di EWDS, bukan CDS

`cems-fire-historical-v1` dilayani `ewds.climate.copernicus.eu` -- **host dan antrean berbeda**
dari `cds.climate.copernicus.eu`, dan batas `cost`-nya juga terpisah (3720 vs 12000).
Jadi era5 + fire sebenarnya aman dijalankan paralel; manifest-nya pun sudah terpisah.
- **Melanjutkan:** jalankan lagi `python crawl_copernicus.py all` -- berkas yang sudah ada
  dilewati otomatis. Terbukti di log 26 Okt: `lewati (sudah ada)` untuk 2013-06, 2013-07,
  2013-08, lalu langsung lanjut `kirim request era5land/instant/2013-09`
- **Crawl boleh dimatikan kapan saja**, lalu dijalankan ulang tanpa kehilangan progress.
  Berkas `.part` setengah jadi dihapus saat berhenti (biaya unduh ulang hanya beberapa MB,
  lebih murah daripada risiko berkas rusak)

### Perubahan kode 26 Okt: `sleep_max` 120 -> 10 detik (efisiensi, bukan kebenaran)

`cdsapi.Client` meneruskan `sleep_max` ke klien dalamnya
(`ecmwf.datastores.Client(retry_after=..., sleep_max=..., maximum_tries=...)`); bawaannya
**120 detik**. Diukur 25 Okt: 21 koneksi putus x 120 detik = **~15% waktu terbuang** hanya
untuk menunggu -- dan jaringan user memang putus-putus.

- Ditambah di `config.py` (tidak di-hardcode): `CLIENT_SLEEP_MAX = 10`, `CLIENT_RETRY_MAX = 500`
- `crawl_copernicus.py::make_client()` meneruskan keduanya ke `cdsapi.Client`
- Diverifikasi langsung ke objeknya (bukan dari dokumentasi): `LegacyClient.sleep_max=10`,
  `retry_max=500`, dan klien dalamnya `retry_after=10, maximum_tries=500`
- Uji ulang setelah perubahan: 66 tes satuan OK, `verify_params.py` **60 OK/0 WARN/0 FAIL**,
  dry-run exit 0
- `retry_max` sengaja tetap 500: percobaan ulang gratis, yang mahal hanya delay-nya
- **BELUM DI-COMMIT** -- keputusan user 26 Okt: commit setelah crawl selesai.
  Berkas yang berubah: `config.py` dan `crawl_copernicus.py` (hanya soal `sleep_max`)

### Pengukuran kecepatan (25 Okt, dari 4,9 jam berjalan / 40 request)

| Bagian | Rata-rata | Porsi |
|---|---|---|
| Antrean CDS (kirim -> mulai unduh) | 2,4 menit | 34% |
| Unduhan | 4,7 menit | 66% |
| backoff akibat koneksi putus (21x120 detik) | ~42 menit | ~15% terbuang |

- Throughput 25 Okt: CDN umum ~226 KB/s vs ECMWF ~126 KB/s -> **jaringan lokal yang jadi
  hambatan utama, bukan limit API maupun sisi ECMWF**
- 26 Okt tampak lebih cepat (`2013-09` instant 32,5 MB selesai ~65 detik), **tapi belum adil
  dibandingkan**: berkas itu sudah ada di cache CDS sejak 25 Okt
- **Perkiraan sisa waktu: ~10-50 jam**, sangat bergantung kualitas jaringan

### Cara memantau dan melanjutkan

```powershell
cd "APIKAH\hotspot_crawler\hotspot_crawler"
python crawl_copernicus.py all         # melanjutkan (melewati berkas yang sudah ada)
python report_manifest.py              # progres: belum / gagal / hilang
Get-Content data\logs\copernicus.log -Tail 20
```

Setelah crawl selesai, urutannya:
`postprocess_era5.py` -> `postprocess_fire.py` ->
`build_derived_features.py` -> `build_training_table.py`.
Ingat: `postprocess_era5.py` **harus dijalankan sekali lagi** setelah crawl selesai, karena
hari terakhir setiap bulan baru lengkap ketika berkas accum bulan berikutnya sudah ada
(bagian 9.1).

## Entry point

| Skrip | Fungsi |
|---|---|
| `preflight.py` | cek library, kredensial, endpoint, disk. Tanpa argumen = semua |
| `verify_params.py` | **baru, dibuat sesi ini.** Validasi `config.py` vs enum + constraints resmi CDS/EWDS. 2 lapis: lapis 1 tanpa kredensial (nama parameter), lapis 2 dengan kredensial (kombinasi + batas biaya) |
| `crawl_copernicus.py` | ERA5-Land (CDS) + CEMS Fire (EWDS), per bulan. `--dry-run` tersedia |
| `crawl_static.py` | 9 job: `enso bounds hansen worldcover dem osm worldpop burned peat`. `all` = semua kecuali `worldcover` + `burned` |
| `postprocess_era5.py` | NetCDF mentah → parquet harian per sel 0,25° |
| `PIPELINE_DEV.md` | dokumen serah-terima (2 salinan: root repo + di dalam folder crawler — disinkronkan) |

## Data yang diambil — inventaris

### Dinamis (per bulan, butuh akun Copernicus)

**ERA5-Land (CDS)** — 354 request = 177 bulan × 2 grup, area `indonesia`

- grup `instant`: 6 variabel × 4 jam (00/06/12/18 UTC) = 744 field/bulan
  `2m_temperature`, `2m_dewpoint_temperature`, `10m_u_component_of_wind`,
  `10m_v_component_of_wind`, `volumetric_soil_water_layer_1`, `volumetric_soil_water_layer_4`
- grup `accum`: 3 variabel × 1 jam (00:00) = 93 field/bulan
  `total_precipitation`, `surface_solar_radiation_downwards`, `potential_evaporation`
- output: `data/raw/era5land/{instant,accum}/YYYY-MM.nc`

**CEMS Fire (EWDS)** — 177 request = 1 per bulan

- 4 variabel: `fire_weather_index`, `drought_code`, `duff_moisture_code`, `keetch_byram_drought_index`
- `grid=0.25/0.25`, `system_version=4_1`, `data_format=netcdf`
- output: `data/raw/cems_fire/YYYY-MM.nc`
- `dataset_type` bergantung bulan: 2012–2022 hanya `consolidated_dataset`;
  Agu–Sep 2026 hanya `intermediate_dataset`. Rantai fallback di `run_fire()` menangani ini

### Statis (sekali unduh, tanpa akun)

| Job | Jumlah | Catatan |
|---|---|---|
| `enso` | 2 file | Niño 3.4 + DMI → `data/static/climate_index/` |
| `bounds` | 2 file | geoBoundaries IDN ADM1+ADM2 |
| `hansen` | 12 tile | 6 tile × 2 layer (`treecover2000`, `lossyear`) |
| `worldcover` | 36 tile | **opt-in** |
| `dem` | 312 tile | banyak 404 karena laut → dicatat `missing`, bukan gagal |
| `osm` | 2 file | Geofabrik sumatra + kalimantan (`.osm.pbf`) |
| `worldpop` | 1 file | IDN 1 km |
| `burned` | ? | MCD64A1, **opt-in, butuh akun Earthdata** |
| `peat` | 0 | peta gambut **manual lewat browser** |

### Hasil olahan

- `postprocess_era5.py` → `data/processed/era5_daily/YYYY-MM.parquet`,
  1 baris per (hari, sel 0,25°), 15 kolom: `date, lat_c, lon_c, t2m_mean/max/min,
  rh_mean/min, wind_mean/max, swvl1_mean, swvl4_mean, precip_mm, ssrd_mjm2, pev_mm`
- **`postprocess_fire.py`** (dulu TODO #4) — **SUDAH ADA 25 Okt 2026**: membaca NetCDF CEMS,
  memetakan nama variabel (`fwinx`, `drtcode`, `dufmcode`, `kbdi` — beda dari nama request!)
  dan melakukan remap 4-sel (pusat CEMS ada di kelipatan 0,25 → geser setengah sel dari grid
  label). Tanpa remap ini, join menghasilkan 0 kecocokan **tanpa error**. Output:
  `data/processed/fire_daily/YYYY-MM.parquet`
- **ENSO dicatat**: `nino34`/`dmi` bulan berjalan **dibuang karena bocor** (rata-rata bulan
  T memuat hari T); yang dipakai hanya `nino34_lag1..3` dan `dmi_lag1..3`

### Kelengkapan rantai fitur (audit 2026-10-25)

Jawaban untuk pertanyaan "apakah crawler sudah lengkap untuk semua fitur yang diinginkan".
**Kunci: bedakan "mengunduh mentah" dari "membangun fitur"** — dua tahap terpisah.

**Tahap A — unduh mentah: hampir lengkap**, 4 fitur belum ada:

| Kelompok | Status | Kurang |
|---|---|---|
| Hujan/suhu/RH/angin/radiasi/PET, kelembapan tanah 2 lapis | ✅ ERA5-Land | — |
| FWI/DC/DMC/KBDI | ✅ | — (pengolah selesai 25 Okt) |
| ENSO/IOD, Hansen, populasi/elevasi/batas | ✅ | agregasi (TODO #15) |
| OSM jalan/sungai/permukiman | ⚠️ **file mentah saja** | jarak (TODO #15) |
| WorldCover, MCD64A1 | ⚠️ **opt-in, belum aktif** | — |
| Gambut | ⚠️ **manual via browser** | TODO #17 |
| **Konsesi sawit/HTI** | ❌ | TODO #12 |
| **Kanal drainase gambut** | ❌ | TODO #13 |
| **VPD** | ❌ | TODO #14 |
| **Arah angin** | ❌ `np.hypot(u10,v10)` membuangnya | TODO #14 |
| Gust, ketebalan gambut | ❌ tidak ada sumber gratis | tidak direncanakan |

**Tahap B — rantai mentah → tabel latih: LENGKAP 8 dari 8 skrip (per 2026-10-25)**

| Skrip | Ada? |
|---|---|
| `crawl_copernicus.py`, `crawl_static.py` | ✅ teruji unduh nyata |
| `postprocess_era5.py` | ✅ VPD + arah angin + **perbaikan hari terakhir bulan** |
| `postprocess_fire.py` | ✅ **TODO #4 SELESAI 25 Okt** — nama variabel & offset grid terbukti |
| `build_static_features.py` | ✅ **TODO #8/#15 SELESAI 25 Okt** — `rasterio`+`geopandas` terpasang |
| `build_derived_features.py` | ✅ **TODO #16 inti SELESAI 25 Okt** |
| `report_manifest.py` | ✅ **TODO #7 SELESAI 25 Okt** |
| `smoke_static.py` | ✅ **baru** — uji end-to-end statis; menemukan bug gambut |
| `test_postprocess.py`, `test_derived.py`, `test_static.py` | ✅ **baru: 17 + 16 + 18 = 51 uji, semua lulus** |
| `build_training_table.py` | ✅ **TODO #19 SELESAI 25 Okt** — 111.073 baris x 47 kolom per bulan |
| `test_postprocess.py`, `test_derived.py`, `test_static.py`, `test_training.py` | ✅ **baru: 17 + 16 + 18 + 15 = 66 uji, semua lulus** |

**Kesimpulan: rantai LENGKAP.** Semua pengolahan sudah ada dan teruji. Yang tersisa bukan
kode, melainkan **menjalankan crawl penuh** (berhari-hari karena jaringan lambat) dan
mengunduh lapisan statis.

### Skrip baru 25 Okt 2026

| Skrip | Fungsi | Bukti |
|---|---|---|
| `report_manifest.py` | laporan kelengkapan dari manifest; membedakan `belum` / `gagal` / `hilang` (manifest bilang ok tapi berkas tidak ada) | dijalankan: benar melaporkan 354 + 177 = 531 kunci `belum` |
| `build_derived_features.py` | hujan 3/7/14/30 hari, rentetan hari kering, anomali klimatologis, SPI empiris, indeks iklim + lag 1-3, kalender | `test_derived.py`: 16 OK / 0 FAIL |
| `test_postprocess.py` | uji fungsi murni postprocess (VPD, RH, agregasi, konvensi grid, tile) | 17 OK / 0 FAIL |
| `test_derived.py` | uji fitur turunan | 16 OK / 0 FAIL |

Desain `build_derived_features.py`: seluruh kolom turunan digeser `--lag` hari (default 1),
jadi fitur di tanggal T berasal dari <= T-1. Cuaca mentah hari T dibiarkan apa adanya
(dipakai untuk nowcasting). Uji `test_anti_bocor_*` membuktikan ini dengan mengubah cuaca
hari >= T lalu memastikan fitur di T tidak berubah.

**Kaveat yang wajib disebut di metodologi:** kolom `*_anom` dan `spi_*` memakai klimatologi
SELURUH rekaman sebagai acuan. Itu praktik baku (normal iklim, bukan kebocoran label), tapi
bukan *strictly causal* untuk tahun-tahun awal. Ganti `empirical_spi` bila tim ingin SPI
gamma klasik (`climate-indices`); nama kolom keluaran tidak perlu berubah.

## Kredensial (sudah terpasang, sudah diverifikasi)

| Layanan | File | Isi |
|---|---|---|
| CDS | `C:\Users\faizr\.cdsapirc` | `url: https://cds.climate.copernicus.eu/api` + `key: <token>` |
| EWDS | `C:\Users\faizr\.ewdsapirc` | `url: https://ewds.climate.copernicus.eu/api` + token yang **sama** |

- Akun: `faizradityahadi@ds.student.pens.ac.id` (Faiz Raditya Hadi, PENS, Indonesia)
- Satu akun ECMWF untuk CDS + EWDS; token-nya sama (36 karakter, UUID)
- **Penting:** dokumentasi resmi EWDS menyuruh menaruh token EWDS di `.cdsapirc` (file sama
  dengan CDS) — itu akan menimpa token CDS. Kode crawler sengaja pakai `.ewdsapirc` terpisah
- **Lisensi SUDAH diterima:** CDS = `cc-by`, `data-protection-privacy-statement`, `terms-of-use-cds`;
  EWDS = `cc-by`, `terms-of-use-cems`. Tidak perlu klik apa pun lagi
- Pendaftaran akun: `https://accounts.ecmwf.int/`
- Ambil token: `https://cds.climate.copernicus.eu/how-to-api` dan
  `https://ewds.climate.copernicus.eu/how-to-api` (token muncul **setelah login**;
  kalau masih tampil `<PERSONAL-ACCESS-TOKEN>` berarti belum login)

## Fakta API terverifikasi (hasil ukur, bukan dari dokumentasi)

### Batas biaya per request — satuan yang benar adalah `cost`, bukan `field`

| Dataset | limit `cost` | rumus | batas field efektif |
|---|---|---|---|
| ERA5-Land | **12.000** | `cost = 2 × field` | **6.000** |
| CEMS Fire | **3.720** | `cost = 1 × field` (variabel × hari) | 3.720 |

- Dokumentasi CDS menulis "12.000 field" → **menyesatkan**, terlalu longgar 2×.
  Dokumentasi memakai satuan `field`, API memakai `cost`
- Batas persis (terukur): instant 8 bulan × 28 hari = 5.376 field → 89,6% (OK);
  9 bulan = 6.048 field → 100,8% (**ditolak**)
- Pemakaian sebenarnya: instant 744 field → cost 1488 (12,4%); accum 93 → 186 (1,6%);
  CEMS 124 dari 3.720 (3,3%)
- Batas ini **tidak punya periode reset** — bukan kuota. Dokumentasi: *"these limits are
  changed from time to time according to the current workload"*; kalau lewat → **diantrikan**,
  bukan ditolak

### Lain-lain

- `area` urutannya **North, West, South, East** (default API `[90, -180, -90, 180]`)
- **`cost` TIDAK bergantung pada `area`** (diukur 2026-10-25: `indonesia` dan `sumkal` sama-sama
  cost 1488/186 untuk ERA5 dan 124 untuk CEMS). Jumlah request dan risiko limit **identik**;
  hanya ukuran file yang membesar. Artinya memilih area besar tidak melanggar limit
- Kunci request **cocok persis** dengan input resmi: ERA5 8 input, CEMS 10 input
- `area` didukung CEMS Fire (jadi `FIRE_TRY_AREA=True` sah)
- Enum variabel: ERA5-Land 60 nilai, CEMS Fire 14 nilai — semua yang dipakai config ada
- Untuk CEMS Fire: `original_grid` **hanya** sah dengan `data_format=grib` (lihat bug #2)
- `estimate_costs()` **tidak** memvalidasi kombinasi — hanya menghitung biaya.
  Validator kombinasi adalah `apply_constraints()`
- `apply_constraints()` hasilnya degenerate untuk request tidak sah, dan **tidak bisa
  diandalkan** untuk kombinasi bulan/hari tidak valid (mis. Februari + tanggal 30).
  Jangan dipakai untuk memvalidasi pemadatan bulan

## Gambut: sumber, ambang, dan fitur baru (28 Okt 2026)

**Sumber ditemukan -- tidak perlu browser lagi.** Paket Open-Earth-Monitor di Zenodo
(record 13951439) menyediakan GeoTIFF 1 km EPSG:4326 yang bisa diunduh **langsung tanpa
akun**: `peat_extent` (23,4 MB), `peat_thickness` (31,1 MB), `peat_carbon` (41,5 MB).
Dulu langkah ini MANUAL karena `gis-gfw.wri.org` tidak bisa dihubungi dari mesin ini
(HTTP maupun HTTPS), dan versi Indonesia-nya minta token API. `crawl_static.py peat`
sekarang mengunduh otomatis; lapisan WRI/Miettinen 2016 tetap perlu manual.

**Ambang itu keputusan terukur, bukan tebakan.** `extent` berisi probabilitas 0-100 (berapa
dari 3 peta sumber -- WRI/GFW, PEATGRIDS, Global Peatlands Map 2.0 -- menyebut gambut):

| Ambang | Luas di jendela Indonesia | vs literatur 13-15 juta ha |
|---|---|---|
| `> 0` (kode LAMA) | 98,6 juta ha | ~7x lipat -- salah |
| `>= 50` | 33,2 juta ha | ~2,4x |
| `>= 75` | 23,3 juta ha | ~1,7x |
| **`== 100`** (dipakai) | **11,6 juta ha** | paling dekat |

`config.PEAT_THRESHOLD = 100`. Jangan turunkan tanpa mengukur ulang dan membandingkan
dengan literatur.

**Gambut dan hutan itu DUA SUMBU BERBEDA** -- ini yang mudah tertukar:
- **hutan** (Hansen, WorldCover) = apa yang ada DI ATAS -> tutupan / bahan bakar
- **gambut** (peta gambut) = apa yang ada DI BAWAH -> jenis tanah

Satu sel bisa berisi: hutan gambut / gambut terbuka / hutan mineral / semak. Yang menjawab
"dampak kalau terbakar" adalah GABUNGANNYA. **Gambut bukan bagian dari hutan.**

**Fitur baru di `build_peat()`:** `peat_fraksi`, `peat_thickness_mean`, `peat_carbon_mean`
(keduanya dirata-ratakan HANYA di piksel gambut), dan `peat_loss_frac_1y/3y/5y` = bagian
SEL yang gambut DAN kehilangan hutan.

**Cara menghitung deforestasi gambut itu penting.** Lapisan gambut dan Hansen dikawinkan
lebih dulu pada grid halus 0,05 derajat (~5,5 km), baru dirata-ratakan ke sel 0,25 derajat.
Mengalikan dua fraksi langsung di 25 km menyimpang sistematis: kehilangan hutan memusat di
bagian gambut yang sudah dibuka, jadi hasilnya tertekan. Arti `peat_loss_frac` = bagian SEL
(bukan bagian dari luas gambut); untuk yang kedua, bagi dengan `peat_fraksi`.

**Keterbatasan jujur:** status DRAINASE (kanal) dan konsesi tidak tersedia terbuka di mana
pun, padahal itu pemicu api gambut terkuat. Tidak bisa diakali.

**Belum dikerjakan:** tabel dampak terpisah (luas per kelas lahan x gambut) -- lihat
"Langkah berikutnya".

## Tiga bug baru ditemukan 28 Okt 2026 (total jadi 8)

6. **Unit test mengotori data ASLI dan memblokir unduhan NOAA.** `test_derived.py` menulis
   CSV palsu ke `data/static/climate_index/`, dan hanya membersihkannya kalau FOLDER-nya
   baru dibuat. Karena `mkdir` meninggalkan folder, jalan kedua membuat berkas palsu
   tertinggal permanen -> `crawl_static.py` melihat berkasnya ada -> `lewati` -> **data NOAA
   asli tidak pernah terunduh**. Terbukti: isinya hanya 6 baris 2012 dengan nilai 0,1..0,6.
   Diperbaiki: tes memakai folder sementara. Diverifikasi dijalankan 2x -> 0 berkas sisa.

7. **`lossyear` menyimpan TAHUN - 2000, bukan tahun penuh.** Kode baru `build_peat` sempat
   membandingkan dengan `HANSEN_LOSS_REF_YEAR - lag` (= 2024) padahal raster berisi 24 ->
   fitur gambut akan **semuanya nol tanpa error apa pun**. Tertangkap uji satuan, bukan di
   data asli. `build_hansen` sudah benar; yang salah hanya kode baru.

8. **`cell_ids()` dan `cell_index_of()` tertukar.** Keduanya mengembalikan bentuk berbeda
   (`(ids, (r0,c0,n_lat,n_lon))` vs `(r, c)`) -> galat "too many values to unpack". Karena
   ini pernah menjatuhkan smoke test, kontraknya kini ditulis di docstring `_step_centers`.

Uji setelah semua perubahan: **27 OK test_static** (dari 18), smoke_static LULUS,
17+16+15 OK tes lain, `verify_params` 60 OK/0 WARN/0 FAIL.

## "Missing" pada Hansen = tile LAUTAN, bukan celah data (dikoreksi 28 Okt 2026)

Sempat dikira celah serius: `lossyear` untuk `10S_090E` dan `10S_100E` membalas **404** di
v1.13 dan v1.12, padahal ada di v1.11. **Ternyata itu tile lautan kosong -- tidak ada data
yang hilang.** Jangan ulangi kekeliruan ini.

Bukti (semua dari HEAD request + ukuran berkas, bukan tebakan):

- Penamaan tile Hansen memakai sudut **kiri-atas / tepi utara**, dibuktikan dari ukuran:
  `treecover2000_50N_000E` = **357,1 MB** (lat 40-50N, Prancis/Jerman) sedangkan
  `40N_000E` = 50,9 MB (lat 30-40N, Mediterania). Kalau penamaannya kiri-bawah, hasilnya
  akan terbalik.
- Karena itu `10S_090E` = lat -20..-10, lon 90..100 -> **Samudra Hindia**, BUKAN Sumatra.
- Ukurannya **12,7 MB, persis sama** dengan tile lautan murni yang diketahui:
  `40S_080E` = 12,7 MB dan `20S_100E` = 12,7 MB -> isinya kosong.
- Daratan Sumatra dilayani baris `00N` dan `10N`, dan **semuanya ada**:
  `00N_100E` = 268,2 MB (Jambi/Sumsel/Lampung), `10N_100E` = 190,7 MB (Riau/Sumut);
  `lossyear` keduanya **200**.
- v1.12/v1.13 berhenti menerbitkan tile lautan kosong -> 404 itu **normal dan benar**.

**Kesimpulan: TIDAK perlu fallback versi.** Entri `missing` untuk hansen di
`manifest_static.json` (2 kunci) adalah tile lautan -> aman diabaikan.
`build_static_features.py` tidak terpengaruh karena tile lautan tidak berisi sel darat.

Pelajaran umum: **jangan simpulkan "data hilang" dari 404 sebelum memeriksa ukuran tile**.
Tabel `hansen_tiles()` di `crawl_static.py` sudah benar (memakai `lat_top = la + 10`).

## Bug 1-5 yang ditemukan & diperbaiki (25-26 Okt 2026)

1. **URL Niño 3.4 mati (404).**
   `psl.noaa.gov/gcos_wgsp/Timeseries/Data/nino34.long.anom.data` → diganti
   `https://psl.noaa.gov/data/correlation/nina34.anom.data` (HTTP 200, format cocok)
2. **Kombinasi parameter CEMS Fire terlarang.** Config memakai `grid=original_grid` +
   `data_format=netcdf`; dari berkas constraints resmi (84 blok kombinasi sah),
   `original_grid` hanya sah dengan `grib` → request ditolak **400 "not produced a valid
   combination"**. Diganti ke `FIRE_GRID = "0.25/0.25"` (resolusi asli CEMS memang 0,25°,
   jadi sama tapi bisa dibaca netCDF4 tanpa `cfgrib`/`eccodes`)
3. **Guard limit memakai satuan salah (2× terlalu longgar).** `ERA5_FIELD_LIMIT` bernilai
   12000 padahal batas `cost` = 12000 → batas field = 6000. Juga CEMS Fire **tidak dijaga
   sama sekali** (batas 3.720). Diperbaiki: `ERA5_COST_LIMIT`/`ERA5_COST_PER_FIELD`/
   `ERA5_FIELD_LIMIT` dan `FIRE_COST_LIMIT`/`FIRE_COST_PER_FIELD`
4. **Lapisan `peat` mencari folder yang salah (25 Okt 2026).** `build_static_features.py`
   mencari `data/static/peat`, padahal `crawl_static.py` menyimpannya di
   `data/static/peatlands/`. Akibatnya **peta gambut tidak akan pernah terbaca** di
   produksi. Diperbaiki dengan peta `DIRS` (lapisan -> folder). Ditemukan oleh
   `smoke_static.py`, bukan oleh uji fungsi murni. **Bukti:** `smoke_static.py` sekarang
   memastikan `peat_fraksi` benar-benar ada di keluaran
5. **Hari terakhir setiap bulan kehilangan hujan/radiasi/PET (25 Okt 2026).** Nilai
   akumulasi ERA5-Land pada 00:00 UTC tanggal 1 bulan berikutnya adalah total untuk hari
   terakhir bulan ini, jadi letaknya di berkas bulan **berikutnya**. Dampaknya besar:
   `hujan_7h/14h/30h` memakai `min_periods=jendela penuh`, sehingga satu nilai kosong
   membuat fitur hujan **NaN sampai 30 hari ke depan** (~360 hari per tahun). Diperbaiki
   di `process_month()` dengan **lookahead**: berkas accum bulan berikutnya dibuka untuk
   melengkapi hari terakhir. Ditambah: keluaran kini dipotong ke bulan itu saja (sebelumnya
   terbawa hari "leak-back" bulan sebelumnya, jadi 32 hari dan muncul di dua berkas), dan
   bulan **tidak dianggap selesai** sampai berkas accum berikutnya ada (kalau tidak,
   perbaikan tidak akan pernah terjadi karena `done()` melewatinya). Cara yang benar: parquet
   ditulis ulang otomatis bila berkas accum bulan berikutnya lebih BARU (cek `mtime`).
   Mengandalkan keberadaan berkas saja salah, dan itu persis kesalahan percobaan pertama
   **Bukti terukur 2023-07:** sebelum = 433.952 baris / **32 hari** (2023-07-31 punya
   hujan 0 dari 3.583 sel); sesudah = 420.391 baris / **31 hari**

   *Bukti setelah 2023-08 diunduh (perbaikan berlaku penuh):* `2023-07-31` hujan terisi
   **0 -> 3.583 sel** (rata-rata 2,63 mm); `hujan_7h` kosong **22,6% -> hanya Jul 1-7** dan
   **Agustus 0%**; `hujan_30h` kosong **96,8% -> hanya 30 hari pemanasan**; `kering_beruntun`
   **3,2% -> 0%**. Ini bukti empiris bahwa satu hari kosong memang meracuni 7 hari dan
   30 hari ke depan

## Bukti pipeline jalan (tes nyata, 2026-10-24)

| Tes | Hasil |
|---|---|
| CDS, 1 variabel × 1 hari | ✅ **53.471 byte**, 126 detik |
| EWDS, 4 variabel × 1 hari | ✅ **83.925 byte**, 406 detik (setelah perbaikan bug #2) |
| `preflight.py` | 22 OK, 2 WARN, 0 FAIL (WARN = Earthdata opsional) |
| `verify_params.py` | **54 OK, 0 WARN, 0 FAIL** |
| `crawl_copernicus.py --dry-run` | jalan, exit 0 |
| `crawl_static.py --dry-run` | jalan, exit 0 |

Catatan: EWDS jauh lebih lambat dari CDS untuk request sekecil apa pun (406 vs 126 detik),
dan hampir semua waktu itu **antrean**, bukan pemrosesan. Perkiraan crawl penuh:
531 request → belasan jam sampai puluhan jam.

## Pengukuran nyata 25 Okt 2026 (area `indonesia`, uji 2023-07)

### Ukuran berkas — JAUH lebih kecil dari perkiraan awal

| Berkas | Ukuran |
|---|---|
| `data/raw/era5land/instant/2023-07.nc` | **34,745 MB** |
| `data/raw/era5land/accum/2023-07.nc` | **6,024 MB** |
| `data/raw/cems_fire/2023-07.nc` | **1,804 MB** |
| **Total per bulan** | **42,57 MB** |

- **Koreksi penting: perkiraan `indonesia` ~100 GB SALAH.** Ekstrapolasi 42,57 MB x 177
  bulan = **~7,5 GB** untuk seluruh data dinamis. `sumkal` kira-kira separuhnya
- Jadi pilihan `indonesia` **aman dari sisi disk**. Yang benar-benar membebani disk adalah
  lapisan **statis** (WorldCover 102 tile @10 m, Hansen 18 tile @30 m, DEM 864 tile) --
  perkiraan 20-30 GB
- Angka lama "~100 MB/bulan-grup" di preflight terlalu besar ~2,5x

### Hambatan sebenarnya: jaringan lambat dan tidak stabil

> **DIKOREKSI 28 Okt 2026:** angka di bawah menggambarkan kecepatan **endpoint ECMWF**, BUKAN
> kapasitas jaringan user. Unduhan dari Google Cloud terukur **~1 MB/s pada link yang sama**.
> Lihat bagian "KOREKSI PENGUKURAN" di atas.

- instant 34,7 MB butuh **~21 menit** dengan **3x retry `IncompleteRead`** -> **~30 KB/s**
- accum 6,0 MB ~3 menit, pola sama
- **`IncompleteRead` terjadi pada 3 dari 3 berkas besar** (Juli instant, Juli accum, Agustus
  instant). Setiap kali: sebagian terunduh, koneksi putus, mundur 120 detik, lalu **resume**
  dari byte terakhir (`.part` menyelamatkan). Jadi **polanya sistematis, bukan acak**
- Dugaan: masalah MTU / firewall / proxy pada jaringan ini, bukan soal CDS. **Layak dicoba
  diukur ulang di jaringan lain** sebelum crawl penuh dimulai; kalau memang khas jaringan ini,
  crawl tetap bisa selesai (resume bekerja) tetapi jauh lebih lambat dan **harus jalan
  tak-terjaga berhari-hari**
- Artinya **throughput jaringan, bukan kuota API**, yang menentukan durasi crawl.
  177 bulan x 3 request @ ~10-20 menit = **berhari-hari**, bukan berjam-jam

### Ukuran tabel harian (`data/processed/era5_daily`)

| Item | Nilai |
|---|---|
| 1 bulan (2023-07) | **420.391 baris**, 31 hari, **10,3 detik** |
| Sel 0,25 derajat total (termasuk laut) | **13.561** |
| **Sel darat** (yang punya cuaca) | **3.583** |
| Perkiraan tabel latih penuh | 3.583 sel x 5.368 hari = **19,2 juta baris** (~5,0 GB float32 @ 68 fitur) |

- Konsisten dengan label: 3.267 sel pernah ada hotspot, dari 3.583 sel darat
  (91% sel darat pernah terbakar)
- **Sel laut ikut tertulis dengan NaN** -> saring di tahap penggabung
- Batas fisik lulus: `rh_min` 0..100, `vpd_max` >= 0, `precip_mm` >= 0
- Nilai wajar untuk Juli: t2m_mean 24,8 C; rh_min rata-rata 72,9%; vpd_max 1,04 kPa

### TODO #2 dan #3: nama variabel NetCDF TERBUKTI (bukan tebakan)

Dibaca langsung dari berkas yang terunduh (aturan repo: klaim sumber luar wajib berbukti).

| Grup | coords | data_vars |
|---|---|---|
| `instant` | `number, valid_time, latitude, longitude, expver` | `t2m, d2m, u10, v10, swvl1, swvl4` |
| `accum` | idem | `tp, ssrd, pev` |

- Cocok **persis** dengan `SHORT` di `postprocess_era5.py`; `time_name()` menangkap
  `valid_time` dengan benar
- Dimensi: instant 124 `valid_time` (31 hari x 4 jam), accum 31. Grid 176 x 476 titik 0,1 derajat
- Sisa yang belum: perilaku `dataset_type=intermediate_dataset` per bulan (baca berkas
  `cems_fire/2023-07.nc` untuk memastikan nama variabelnya: lihat TODO #4)

### TODO #4: CEMS Fire — DUA jebakan yang terbukti dari berkas asli (25 Okt 2026)

**Jebakan 1 — nama variabel di NetCDF BERBEDA dari nama parameter request:**

| Request (crawl) | Isi NetCDF |
|---|---|
| `fire_weather_index` | **`fwinx`** |
| `drought_code` | **`drtcode`** |
| `duff_moisture_code` | **`dufmcode`** |
| `keetch_byram_drought_index` | **`kbdi`** |

Menebak nama request akan langsung `KeyError`. Koordinat waktu: `valid_time`.

**Jebakan 2 — grid CEMS berselisih SETENGAH SEL dari grid label.**
Pusat sel CEMS di **kelipatan 0,25** (94.0, 94.25, ... 141.5; lat 6.0 .. -11.5),
sedangkan grid label dan ERA5 di **n*0,25 + 0,125**. Keduanya sama-sama 71 x 191 sel
tetapi **bergeser 0,125**. Menggabungkan langsung berdasarkan koordinat akan
menghasilkan **NOL baris cocok** — fitur api jadi NaN semua tanpa error apa pun.

Karena pusat sel CEMS jatuh tepat di **tepi** sel label, tumpang tindih areanya selalu
50/50 per arah -> nilai sel label = **rata-rata 4 sel CEMS** (masing-masing 25%).
`postprocess_fire.py` melakukan ini dan mengabaikan NaN, sehingga sel pesisir tidak
kosong hanya karena satu tetangganya laut.

**Bukti terukur 2023-07:** 420.391 baris, 31 hari, kunci **identik** dengan `era5_daily`
(gabung `inner` = 420.391 baris, tanpa kunci ganda). Pusat sel lulus uji
`% 0,25 == 0,125`. Cakupan di sel darat: **FWI 98,6%**, hujan 96,8%
(kekurangan 3,2% = tepat hari terakhir Juli, menunggu accum 2023-08).
Nilai wajar: FWI mean 3,62 / maks 58,1; DC mean 102 / maks 786; KBDI mean 11,3 / maks 88.

## Keputusan tertunda

1. ~~**Area: `sumkal` atau `indonesia`?**~~ **DIPUTUSKAN 25 Okt 2026: `indonesia`.**
   `config.ACTIVE_AREA` sudah diubah, dan uji `--dry-run`/`verify_params` tetap hijau.
   Fakta terukur 2026-10-25:

   | | `sumkal` [6,94,-6,119.5] | `indonesia` [6,94,-11.5,141.5] |
   |---|---|---|
   | Cakupan label | **2.726.820 (69,2%)** | 3.941.038 (100%) |
   | Request ERA5+CEMS | **531** | **531 — sama** |
   | cost ERA5 instant / accum | 1488 / 186 | **sama** |
   | cost CEMS fire | 124 | **sama** |
   | Disk (perkiraan) | ~40–50 GB | ~2× → ~100 GB (bebas: 136 GB) |
   | Tile statis (Hansen+WorldCover+DEM) | 354 | **984 (2,8×)** |

   **KOREKSI 25 Okt: angka disk di atas SALAH.** Terukur: data dinamis penuh hanya
   **~7,5 GB** (42,57 MB/bulan x 177 bulan), bukan 100 GB. Disk bukan masalah sama sekali
   (bebas 125,7 GB saat crawl dihentikan).

   Yang **hilang** kalau pilih `sumkal` (1.214.218 baris, 30,8%) hampir semuanya
   savana/bukan-gambut: Papua 282.955 · NTT 249.728 · NTB 103.645 · JawaTimur 99.683 ·
   SulawesiTengah 78.173 · Maluku 73.759 · SulawesiSelatan 71.349 · SulawesiTenggara 64.660 ·
   MalukuUtara 42.821 · JawaBarat 33.155 · JawaTengah 30.607 · SulawesiUtara 22.193 ·
   PapuaBarat 19.157 · Gorontalo 17.647 · Banten 14.573 · Bali 2.667 · Yogyakarta 1.870 ·
   JakartaRaya 756 · SulawesiBarat 2.852 · Lampung 1.968 (di luar kotak)

   **KOREKSI: keputusan ini TIDAK benar-benar ireversibel.** `area` adalah parameter request,
   jadi wilayah yang belum diunduh bisa ditambah belakangan lewat crawl pelengkap
   (mis. `[6, 119.5, -6, 141.5]` untuk timur + `[-6, 94, -11.5, 119.5]` untuk selatan), lalu
   digabung di tahap fitur. Harganya ~1.062 request tambahan + tata kelola file lebih rumit.
   Jadi ini "mahal diubah", bukan "tidak bisa diubah"
2. **Perluas mundur ke 2000–2011?** (288 request tambahan). Hanya berguna kalau label era
   itu ada. Lihat catatan `apikah-data-label.md`
3. ~~**`.gitignore`**~~ **SELESAI 2026-10-25** — dibuat, diuji, di-commit, di-push (`01e88cd`)
4. ~~**Commit + push** perubahan sesi ini~~ **SELESAI 25 Okt 2026** -- 3 commit sudah di-push:
   `01e88cd` (.gitignore), `db7a084` (rantai fitur + bug), `91deab8` (skrip penggabung)
5. ~~**`postprocess_fire.py`** (TODO #4)~~ **SELESAI 25 Okt 2026** -- rantai 8 dari 8 skrip LENGKAP
6. **Pertanyaan user yang belum terjawab: "rtk tidak terinstall disini ya?"** — aku sudah
   cari "rtk"/"redux" di seluruh workspace (kecuali `node_modules`, `.git`, `data`) dan
   **tidak ada**. `IntegrityView-PENS/package.json` hanya berisi react, react-dom, vite,
   oxlint, @types. Perlu diklarifikasi maksudnya apa

## Langkah berikutnya (untuk sesi berikutnya)

**Kondisi saat ini:** rantai fitur **LENGKAP 8 dari 8 skrip** dan sudah ter-commit + ter-push.
Crawl penuh **BERHENTI** (baru 20 bulan: 2012-01..2013-08; sisa 485 request). Tidak ada kode
yang perlu diperbaiki agar bisa jalan -- hanya perlu jaringan.

1. **Lanjutkan crawl** kapan saja: `python crawl_copernicus.py all`
   (melewati 46 berkas yang sudah ada; 4,9 jam kerja sebelumnya tidak terbuang)
2. **Opsional, hemat ~7 jam:** turunkan `retry_after` klien ECMWF dari 120 detik ke ~10 detik
   di `make_client()` (`crawl_copernicus.py`). Butuh restart crawl. Lihat bagian kecepatan
3. **Lapisan statis belum diunduh** (`data/static/` kosong). Butuh jaringan:
   `python crawl_static.py all` lalu `python build_static_features.py` (984 tile)
4. **Templat notebook training** -- TANPA jaringan, bisa dikerjakan sekarang dengan 2 bulan
   data yang sudah ada (`data/processed/training/`). Isi yang direncanakan: muat per bulan,
   split temporal berblok (latih 2012-2025 / uji 2026), PR-AUC, feature importance,
   pemangkasan 68 -> ~25 fitur sesuai usul MVP di `apikah-fitur.md`
5. **TENGGAT 2 NOVEMBER 2026: data SNPP** (bukan bagian crawler ini).
   Lihat `apikah-data-label.md` bagian "Tugas tim label"
6. **Pertanyaan user yang belum terjawab:** "rtk tidak terinstall disini ya?" -- sudah dicari
   di seluruh workspace, tidak ada. Perlu diklarifikasi maksudnya

## Hal penting yang jangan diulang

- **Jangan commit `gadm41_IDN_1.json`** — sudah ada di repo dari commit orang lain, padahal
  `PIPELINE_DEV.md` bagian 7 poin 6 menulis GADM dilarang diredistribusi. Repo **publik**
- Uji pemadatan request (menggabung beberapa bulan ke 1 request) **secara teknis bisa**
  (8 bulan = 5.376 field, 89,6%) tetapi **sebaiknya jangan**: (a) dokumentasi CDS menyarankan
  request kecil agar tidak "penalised in the CDS request queue"; (b) resume jadi kasar;
  (c) `apply_constraints` tidak andal untuk kombinasi bulan/hari. Desain per bulan dipakai

## Cara verifikasi ulang

```powershell
cd "APIKAH\hotspot_crawler\hotspot_crawler"
python preflight.py            # target: 0 FAIL
python verify_params.py        # target: 0 FAIL (54 OK)
python crawl_copernicus.py all --from 2023-07 --to 2023-07 --dry-run
python crawl_static.py all --dry-run
```

- Batas biaya: `python -c "from ecmwf.datastores import Client; ..."` lalu `estimate_costs()`
  (lihat riwayat sesi) — atau langsung `verify_params.py` yang sudah memuatnya
- Rincian analisis label & sensor: `apikah-data-label.md`

## Rencana setelah seluruh crawl selesai (disepakati 2026-10-30)

- Jangan mulai refactor sampai semua crawl aktif selesai.
- Setelah selesai, buat branch baru khusus refactor; jangan campur dengan `main`.
- Tujuan: sederhanakan/efisienkan kode dan tujuan pipeline, rapikan penamaan serta struktur.
- Data hasil crawler dikumpulkan di satu root `data/`, lalu dibagi ke subfolder menurut kategori/kebutuhan; kode crawler tetap terpisah dari data.
- **Koreksi keputusan 2026-10-31:** data tetap berada di dalam folder project/repo `APIKAH/`, bukan di root eksternal. Refactor nanti akan membuat satu root data yang rapi dan terpisah dari folder kode/proyek lain (misalnya `APIKAH/data/{raw,static,processed,manifests}`); isi dataset besar tetap dikecualikan dari Git.
- **Klarifikasi 2026-10-31:** gunakan `APIKAH/data/` sebagai satu root untuk seluruh data. Data hotspot yang sudah ada tetap tracked di Git; hasil unduhan crawler dikecualikan. Kelompokkan data berdasar fungsi (label, raw, features, training, metadata/manifests); keputusan tracking untuk keluaran fitur/training masih perlu dikonfirmasi.
- **Klarifikasi struktur data:** top-level yang diusulkan user: `data/hotspot_indonesia/`, `data/hotspot_raw/`, `data/features_raw/`, `data/features_processed/`, `data/metadata/`. `features_raw` secara khusus berisi input fitur yang sama sekali belum diproses (termasuk hasil unduh crawler); `features_processed` berisi keluaran transformasi/fitur siap. Dua folder hotspot existing tetap tracked. Tracking policy `features_processed` masih menunggu keputusan.
- Buat commit kecil yang bermakna pada setiap perubahan agar riwayat refactor tercatat.
- Sebelum migrasi, inventarisasi data dan referensi path agar tidak merusak hasil unduhan atau pipeline; verifikasi setelah perubahan.

### Pemeriksaan kelengkapan 2026-10-31 16:16

- CEMS Fire lengkap: 177/177 bulan; ERA5 manifest 352/354 kunci dan file fisik 176/177 bulan.
- Satu bulan tersisa: `2022-12`, instant sedang diunduh oleh PID 21992 (`.nc.part` sekitar 15 MB); accum belum ada. Log menunjukkan retry/resume dari incomplete read, crawler masih hidup.
- Jangan mulai refactor atau pindah data sampai proses ini selesai dan kedua NetCDF Desember lolos verifikasi keberadaan/ukuran serta manifest.
- Pemeriksaan Git menunjukkan branch `main` punya perubahan lokal dan berkas untracked (`tests/`, notebook, `.opencode/`, serta perubahan crawler). Pertahankan semuanya; audit kepemilikan/perubahan sebelum membuat baseline commit/branch refactor.

### Crawl selesai & audit awal struktur 2026-10-31 16:35

- `status.ps1`: tidak ada crawler aktif; ERA5 instant 177/177 dan accum 177/177 (354/354 kunci OK), CEMS Fire 177/177. Tidak ada `.part` tersisa. Desember 2022 kini ada: instant 35.11 MB, accum 6.09 MB.
- Statis tercatat: MCD64A1 2.992 granula (~4.17 GB), WorldCover 81 file (~1.17 GB), DEM 486, Hansen 33, OSM 2, peatlands 3, boundaries 4, climate index 4, WorldPop 1. Tidak ada static crawler aktif.
- Audit awal path: repo sudah memiliki `APIKAH/data/` berisi label (`hotspot_indonesia`, `hotspot_raw`, CSV/Parquet gabungan); hasil crawler pendukung masih di `APIKAH/hotspot_crawler/hotspot_crawler/data/{raw,static,processed,logs}` karena `config.DATA_DIR = Path("data")` relatif CWD. Refactor perlu satu struktur kategori di dalam repo dan mencegah keluaran bergantung pada CWD.
- Git masih `main` dengan perubahan lokal dan untracked. Jangan hilangkan atau sertakan data besar dalam commit; audit diff dan aturan ignore sebelum branch/commit.
- 2026-10-31: fetch menemukan satu commit tim `cd1b892` (modeling EDA; `model.ipynb`, `modeling/EDA.ipynb`), tanpa path collision dengan kerja crawler. Local `main` sudah fast-forward ke commit itu; EDA notebook lokal `eda_awal.ipynb` dan folder `tests/` tetap terpisah/untracked.
- Baseline validasi setelah crawl: skrip tes standalone `test_derived.py` 16 OK, `test_postprocess.py` 17 OK, `test_static.py` 27 OK, `test_training.py` 15 OK; `smoke_static.py` LULUS; `verify_params.py` 60 OK/0 WARN/0 FAIL; `git diff --check` bersih. `pytest` tidak terpasang dan `unittest discover` bukan runner yang tepat (0 test ditemukan), jadi jangan mengklaim kedua perintah itu sebagai suite yang lulus.
- 2026-10-31: perubahan crawler yang menunggu crawl selesai dikomit sebagai baseline `0afc14d` di `main`; branch `refactor/crawler-data-layout` dibuat sesudahnya. Desain refactor selesai, diperiksa builder-check (pertanyaan tentang tabel gabungan dijawab dengan menempatkannya di `data/hotspot_indonesia/combined/`) dan dikomit sebagai `0d7d38a` di branch. Implementasi/pemindahan data belum dimulai; menunggu persetujuan desain pengguna.
- Audit juga menemukan EDA tim di remote (`cd1b892`), sudah di-fast-forward ke local `main`; berkas EDA lokal yang untracked tetap tidak disentuh. Local `main` dan branch refactor memiliki commit baseline yang belum di-push.

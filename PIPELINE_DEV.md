# Pipeline Crawl Data Pendukung: Prediksi Risiko Hotspot Karhutla

Dokumen serah-terima untuk developer atau agent lain yang melanjutkan pipeline ini. Baca bagian 1-3 dulu, lalu kerjakan daftar TODO di bagian 9.

- Proyek induk: prediksi risiko hotspot karhutla per sel grid 0,25 derajat per hari (1-3 hari ke depan), data hotspot VIIRS dari NASA FIRMS (sudah dimiliki tim, bukan bagian crawler ini).
- Rentang data crawler: **Januari 2012 sampai September 2026** (`config.START`, `config.END`).
- Keputusan tim: **data cuaca/iklim diambil dari Copernicus** (ERA5-Land lewat CDS, indeks bahaya api CEMS lewat EWDS), bukan Open-Meteo.
- Bahasa dokumen dan log: Indonesia. Kode: Python 3.10+.

## 1. Status (jujur)

| Komponen | Status |
|---|---|
| Struktur kode, retry, resume, manifest | Ditulis, lolos kompilasi, dry-run berjalan |
| Logika agregasi harian (`postprocess_era5.py`) | Lolos uji dengan data sintetis (bukan data CDS asli) |
| Logika tile Hansen/WorldCover/DEM dan parser PSL | Lolos uji offline |
| Akses ke API/endpoint | **BELUM TERBUKTI.** Sandbox tempat kode ditulis memblokir semua koneksi keluar (HTTP 403 dari proxy), jadi tidak ada satu pun unduhan nyata yang pernah dijalankan |
| Parameter request ERA5-Land | Disusun dari pola `cdsapi` umum; verifikasi lewat "Show API request" |
| Parameter request CEMS Fire | **Belum terverifikasi** (nama variabel, `dataset_type`, `system_version`, `grid`, dukungan `area`) |
| URL ENSO/DMI, WorldPop, DEM | Belum terverifikasi (lihat bagian 9) |

Aturan utama: jalankan `preflight.py` di mesin yang punya internet **sebelum** crawl apa pun, dan jangan percaya klaim "tersedia" di dokumen ini sebelum preflight hijau.

## 2. Struktur folder

```
hotspot_crawler/
  config.py              # satu-satunya tempat parameter (rentang, area, variabel, URL)
  common.py              # iter_months, with_retry, download_file (resume .part), manifest, helper tile
  preflight.py           # cek library, kredensial, endpoint, dataset ada, limit, disk
  crawl_copernicus.py    # ERA5-Land (CDS) + CEMS Fire (EWDS), per bulan
  crawl_static.py        # ENSO/DMI, batas wilayah, Hansen, WorldCover, DEM, OSM, WorldPop, MCD64A1, gambut
  postprocess_era5.py    # NetCDF mentah -> parquet harian per sel 0,25 derajat
  requirements.txt
  PIPELINE_DEV.md        # dokumen ini
  data/                  # dibuat saat dijalankan
    raw/era5land/{instant,accum}/YYYY-MM.nc
    raw/cems_fire/YYYY-MM.nc
    static/{climate_index,boundaries,hansen,worldcover,dem,osm,worldpop,mcd64a1,peatlands}/
    processed/era5_daily/YYYY-MM.parquet
    logs/{copernicus,static,postprocess}.log  dan  manifest_*.json
```

## 3. Cara menjalankan (urutan wajib)

```bash
pip install -r requirements.txt

# 0. kredensial (sekali)
#    ~/.cdsapirc   : url: https://cds.climate.copernicus.eu/api   +  key: <token CDS>
#    ~/.ewdsapirc  : url: https://ewds.climate.copernicus.eu/api  +  key: <token EWDS>
#    (format: dua baris "url: ..." dan "key: ...")
#    Terima lisensi dataset secara manual di halaman ERA5-Land dan CEMS Fire.

python preflight.py                          # harus tanpa FAIL untuk sumber yang dipakai
python crawl_copernicus.py all --dry-run     # lihat request tanpa mengirim
python crawl_copernicus.py era5 --from 2023-07 --to 2023-07   # uji satu bulan dulu
python postprocess_era5.py --from 2023-07 --to 2023-07        # validasi hasil satu bulan
python crawl_copernicus.py all               # baru jalankan penuh (aman diulang, ada resume)
python crawl_static.py all                   # enso bounds hansen dem osm worldpop peat
python crawl_static.py burned                # opsional, butuh EARTHDATA_USERNAME/PASSWORD
python crawl_static.py worldcover            # opsional, BESAR (36 tile area sumkal)
python postprocess_era5.py
```

Semua skrip idempoten: file yang sudah ada dilewati, unduhan terputus dilanjutkan dari `.part`, kegagalan dicatat di `data/logs/manifest_*.json` dan tidak menghentikan batch.

## 4. Konfigurasi penting (`config.py`)

| Parameter | Nilai default | Catatan |
|---|---|---|
| `START`, `END` | 2012-01-01, 2026-09-30 | 177 bulan |
| `ACTIVE_AREA` | `sumkal` ([N,W,S,E] = [6, 94, -6, 119.5]) | Pilihan lain: `indonesia` ([6, 94, -11.5, 141.5]); disk bisa lebih dari 2x |
| `ERA5_INSTANT` | t2m, d2m, u10, v10, swvl1, swvl4 | Diambil pada 00/06/12/18 UTC |
| `ERA5_ACCUM` | total_precipitation, surface_solar_radiation_downwards, potential_evaporation | Diambil pada 00:00 UTC saja |
| `FIRE_VARIABLES` | FWI, DC, DMC, KBDI | Nama belum terverifikasi |
| `FIRE_INTERMEDIATE_LAST_N_MONTHS` | 4 | Bulan terbaru dicoba sebagai `intermediate_dataset` dulu |

Alasan desain ERA5-Land: batas CDS untuk ERA5-Land hourly adalah 12.000 field per request (variabel x hari x jam). Mengambil 24 jam penuh membuat file sangat besar. Karena itu variabel instan hanya diambil 4 jam per hari (07, 13, 19, 01 WIB, sehingga RH minimum siang tertangkap) dan variabel akumulasi cukup 1 nilai per hari. Per request: 744 field (instan) dan 93 field (akumulasi), jauh di bawah batas.

## 5. Kontrak data

### 5.1 `data/processed/era5_daily/YYYY-MM.parquet`

Satu baris per (hari, sel 0,25 derajat). Kunci: `date` (hari UTC), `lat_c`, `lon_c` (pusat sel = kelipatan 0,25 ditambah 0,125).

| Kolom | Satuan | Asal |
|---|---|---|
| `t2m_mean/max/min` | derajat C | rata-rata/ekstrem 4 langkah waktu |
| `rh_mean`, `rh_min` | % | Magnus dari t2m dan d2m, dihitung per langkah waktu lalu diagregasi |
| `wind_mean`, `wind_max` | m/s | sqrt(u10^2 + v10^2) |
| `swvl1_mean`, `swvl4_mean` | m3/m3 | lapisan 0-7 cm dan 100-289 cm |
| `precip_mm` | mm | tp pada 00:00 UTC hari D+1 x 1000, diberi tanggal hari D |
| `ssrd_mjm2` | MJ/m2 | ssrd pada 00:00 UTC hari D+1 / 1e6 |
| `pev_mm` | mm | minus pev x 1000 (nilai ERA5-Land negatif = penguapan) |

Catatan: "hari" adalah hari UTC, bukan WIB. Selisih 7 jam bisa penting untuk presisi lag; putuskan konvensi sebelum membuat fitur.

### 5.2 Lain-lain

- `data/static/climate_index/{nino34,dmi}.csv`: kolom `year,month,<nama>`; nilai hilang dibuang. File mentah disimpan berdampingan (`.raw.txt`).
- `data/static/boundaries/idn_adm{1,2}.geojson`: dari geoBoundaries gbOpen; cek `*.meta.json` untuk lisensi (file IDN tercatat ODbL di HDX).
- `data/raw/cems_fire/YYYY-MM.nc`: belum ada skrip postprocess (lihat TODO).
- `data/logs/manifest_*.json`: `{kunci: {status: ok|failed|skipped|missing|manual_pending, note, ts}}`. Gunakan ini untuk membuat laporan kelengkapan.

## 6. Limitasi layanan

| Layanan | Limit/syarat | Dampak pada desain |
|---|---|---|
| CDS ERA5-Land | Maks 12.000 field per request. Request yang melebihi batas masuk antrean. Jumlah request per user tidak dipublikasikan dan sering berubah | Request kecil per bulan, sekuensial, retry + resume. Sudah ada guard di `era5_request()` |
| CDS/EWDS | Lisensi harus diterima manual per dataset; akun ECMWF gratis | Preflight mengingatkan; error lisensi muncul saat request pertama |
| CEMS Fire | Hanya di EWDS (sejak 26 Sep 2024), bukan CDS | Klien terpisah dan kredensial terpisah |
| ERA5T | Data terbaru sekitar 5 hari di belakang waktu nyata | Bulan berjalan tidak diambil; fitur real-time harus dari sumber prakiraan terpisah |
| Earthdata | Butuh akun gratis | `burned` opsional |
| Geofabrik, Hansen, DEM AWS | Tanpa login | Resume saja |

Semua angka limit di atas berasal dari halaman dokumentasi resmi yang dibaca pada 21 Oktober 2026; cek ulang bila ada error baru.

## 7. Kaveat penting untuk fitur dan pelatihan

1. **Train-serve skew**: ERA5-Land adalah reanalisis. Untuk prediksi harian di website, sumber cuaca harus punya karakteristik setara (ERA5T/ERA5-Land terbaru atau prakiraan yang dikalibrasi). Putuskan sebelum membangun fitur.
2. **Anti-bocor**: fitur target hari T hanya dari T-1 ke belakang. Gunakan `date` + 1 saat menggabungkan, dan lag untuk burned area (bulanan) dan Hansen (tahunan).
3. **Hansen** `lossyear` bertipe tahunan dan tidak membedakan hutan alam dengan tanaman; `treecover2000` dipakai sebagai baseline.
4. **VIIRS SNPP**: pemberitahuan NOAA NESDIS menyebut pengiriman data S-NPP berhenti pada 2 November 2026. Arsip FIRMS SNPP untuk 2012-2026 sebaiknya diunduh **segera** untuk ablation; status ketersediaan arsip setelah tanggal itu belum diverifikasi.
5. Peta gambut BBSDLP 2019 (data.go.id) mengembalikan 404 saat diperiksa dan status hak ciptanya ambigu; sumber utama adalah GFW Global Peatlands (CC BY 4.0), diunduh **manual**.
6. GADM dilarang untuk redistribusi; jangan commit file mentahnya ke repo publik.

## 8. Konvensi pengembangan

- Satu sumber kebenaran parameter: `config.py`. Jangan menaruh URL atau nama variabel di skrip lain.
- Setiap job idempoten, mencatat ke manifest, dan tidak melempar error yang menghentikan batch.
- Unduhan selalu ke `*.part` lalu rename atomik.
- Skrip dijalankan tanpa flag `python -I` (mode itu menyembunyikan modul lokal).
- Tambahkan uji untuk setiap fungsi murni (tile, parser, agregasi); uji jaringan dipisahkan dan hanya dijalankan manual.
- Hormati batas: jangan menambah paralelisme ke CDS/EWDS tanpa mengukur dampak antrean.

## 9. TODO untuk developer/agent berikutnya

Urutkan sesuai prioritas. Setiap butir punya kriteria selesai.

| # | Tugas | Kriteria selesai |
|---|---|---|
| 1 | Jalankan `preflight.py` di mesin berinternet; perbaiki semua FAIL | Output tanpa FAIL untuk `cds`, `ewds`, `noaa`, `static` |
| 2 | Verifikasi parameter ERA5-Land lewat "Show API request"; uji 1 bulan (2023-07) | Dua file `.nc` terunduh; `postprocess_era5.py` menghasilkan parquet; nama variabel NetCDF (`t2m`, `d2m`, `u10`, `v10`, `swvl1`, `swvl4`, `tp`, `ssrd`, `pev`) dan koordinat waktu (`valid_time`) sesuai; sesuaikan `SHORT`/`time_name` bila beda |
| 3 | Verifikasi parameter CEMS Fire (nama variabel, `dataset_type`, `system_version`, `grid`, dukungan `area`); uji 1 bulan | `data/raw/cems_fire/2023-07.nc` terunduh; `config.FIRE_*` diperbarui sesuai kenyataan; hapus peringatan di config |
| 4 | Tulis `postprocess_fire.py` (NetCDF CEMS -> parquet harian per sel 0,25 derajat; grid sudah 0,25 sehingga cukup pilih sel dalam bbox) | Kolom `fwi`, `dc`, `dmc`, `kbdi` per `date, lat_c, lon_c`; uji sintetis seperti ERA5 |
| 5 | Pastikan pusat sel ERA5-Land (0,1 derajat) dan grid label hotspot 0,25 derajat konsisten (konvensi pusat sel `n*0,25+0,125`) | Uji: tiap sel 0,25 derajat punya jumlah sel-sumber yang masuk akal (sekitar 6 sel 0,1 derajat per sel penuh di darat, karena 0,25/0,1 = 2,5 per sisi; sel pesisir lebih sedikit) |
| 6 | Verifikasi URL ENSO/DMI (`psl.noaa.gov/gcos_wgsp/Timeseries/Data/...`), WorldPop, dan pola URL DEM | `preflight --only noaa static` hijau; perbarui `config.py` bila URL berubah |
| 7 | Tambah laporan kelengkapan dari manifest (bulan gagal, bulan hilang, ukuran file) | `python report_manifest.py` mencetak ringkasan dan daftar bulan yang perlu diulang |
| 8 | Skrip agregasi lapisan statis ke grid (fraksi gambut, fraksi WorldCover, rata-rata elevasi/slope, loss Hansen tahunan, jarak OSM) | Tabel `static_features.parquet` per `lat_c, lon_c` |
| 9 | Pipeline real-time: sumber cuaca untuk H+1 sampai H+3 (ERA5T/prakiraan) dengan koreksi bias terhadap ERA5-Land | Dokumen keputusan + skrip harian terjadwal (cron) |
| 10 | Validasi silang: bandingkan sampel `precip_mm` dengan sumber lain (CHIRPS/BMKG) untuk beberapa sel | Plot/tabel selisih; catat bias |
| 11 | (Opsional) coba `derived-era5-land-daily-statistics` (belum diverifikasi ada) sebagai pengganti pengambilan 4 jam | Perbandingan hasil dan ukuran file; adopsi hanya bila lebih sederhana |
| 12 | Tambah crawler **konsesi sawit/HTI** (bagian 11.2) ke `crawl_static.py` dan `config.py` | File poligon terunduh; lisensi tiap sumber dicatat di manifest; hasil `preflight` untuk URL baru hijau |
| 13 | Tambah crawler **kanal drainase gambut** Dadap dkk. 2021 (bagian 11.2) | Berkas Stanford terunduh; lisensi dicek dan dicatat |
| 14 | Hitung **VPD** (dan opsional arah angin sin/cos) di `postprocess_era5.py` (bagian 11.3) | Kolom `vpd_mean`, `vpd_max` ada di parquet; uji sintetis lulus |
| 15 | Tulis `build_static_features.py`: agregasi semua lapisan statis ke sel 0,25 derajat (bagian 11.4) | `static_features.parquet` dengan satu baris per `lat_c, lon_c`; tidak ada sel ganda |
| 16 | Tulis `build_derived_features.py`: fitur turunan dari tabel harian (bagian 11.5) | Akumulasi hujan, hari kering beruntun, SPI/SPEI, lag; uji anti-bocor (tidak ada fitur dari hari T) |
| 17 | Putuskan jalur **gambut** (bagian 11.2): GFW Global Peatlands sebagai utama; coba BBSDLP 2019 hanya bila bisa diunduh | Catatan keputusan + file ada di `data/static/peatlands/` |
| 18 | Opsi validasi eksternal: CHIRPS v3, NASA POWER, atau BMKG Data Online untuk membandingkan hujan ERA5-Land (bagian 11.6) | Tabel selisih untuk beberapa sel/stasiun, bias dicatat |

## 11. Cakupan variabel dan rencana penambahan

Pembagian kerja: data hotspot (FIRMS) diambil oleh anggota lain dan **bukan** bagian crawler ini. Crawler ini mengurus cuaca, iklim, dan lahan. Tautan di bagian ini berasal dari riset sumber (Oktober 2026) dan belum dibuka dari sandbox; verifikasi dengan `preflight.py` setelah ditambahkan ke `config.py`.

### 11.1 Peta cakupan (status saat ini)

| Kelompok | Status | Rencana |
|---|---|---|
| Hujan, suhu, RH, angin (kecepatan), radiasi, PET | Tercakup (ERA5-Land) | Tidak ada |
| Kelembapan tanah (dua lapisan) | Tercakup | Tidak ada |
| FWI, DC, DMC, KBDI | Tercakup, parameter belum terverifikasi | TODO #3 dan #4 |
| ENSO (Niño 3.4), IOD (DMI) | Tercakup | Latensi: DMI sering tertinggal beberapa bulan dibanding Niño 3.4; pakai nilai terakhir yang tersedia dengan lag |
| Gambut (ada/tidak) | Manual | TODO #17 |
| Tutupan lahan | WorldCover opt-in | Aktifkan bila fraksi tutupan dipakai di model |
| Deforestasi (Hansen) | Tercakup | Agregasi di TODO #15 |
| Area bekas terbakar (MCD64A1) | Tercakup, opsional | Dipakai MODIS, bukan VIIRS (lihat 11.7) |
| Jalan, sungai, permukiman (OSM) | File mentah saja | Jarak dihitung di TODO #15 |
| Penduduk, elevasi, batas wilayah | Tercakup | Agregasi di TODO #15 |
| **Konsesi sawit dan HTI** | **Belum ada** | TODO #12 |
| **Kanal drainase gambut** | **Belum ada** | TODO #13 |
| **VPD** | **Belum dihitung** | TODO #14 |
| **Arah angin** | **Tidak disimpan** | TODO #14 (sin/cos, hanya bila ada alasan modeling) |
| Hembusan angin (gust) | Tidak tersedia di ERA5-Land | Tidak direncanakan |
| Ketebalan gambut | Tidak ada sumber gratis terverifikasi | Hanya kelas ketebalan BBSDLP 2019 bila berkas bisa diunduh |
| Fitur kalender (bulan, musim, libur) | Tidak perlu crawl | Dihitung di TODO #16 |

### 11.2 Sumber yang ditambahkan ke rencana

| Data | Tautan | Format | Catatan dan kaveat |
|---|---|---|---|
| Konsesi sawit (GFW) | https://data.globalforestwatch.org/datasets/indonesia-oil-palm-concessions | Shapefile/GeoJSON | Lisensi kustom GFW; data asli 2015 (portal diperbarui 2023); sebagian sudah usang. Portal GFW kini bernama Global Nature Watch; menurut blog resminya hanya namanya yang berubah. GFW Pro (antarmuka web dan Pro API) dijadwalkan pensiun 31 Des 2026, jadi jangan bergantung pada Pro API |
| Konsesi sawit (Greenpeace Kepo Hutan) | https://kepohutan.greenpeace.org/downloads | Shapefile | Versi Nov 2020, lebih baru dari GFW; **lisensi tidak dicantumkan**, pakai untuk akademik dan cantumkan sumber |
| Konsesi HTI (kayu serat) | GFW "Indonesia wood fiber concessions" (belum diverifikasi); konteks per kabupaten di https://trase.earth/open-data/datasets/spatial-metrics-indonesia-palm-oil-oil-palm-ha dan https://nusantara-atlas.org | Poligon / CSV | Cek ketersediaan poligon di GFW sebelum menulis crawler; Trase hanya agregat per kabupaten |
| Kanal drainase gambut (Dadap dkk. 2021) | https://purl.stanford.edu/yj761xk5815 | Raster/vektor | Sumatera, Kalimantan, Semenanjung Malaysia; snapshot 2017 (citra Planet 5 m) plus kerapatan drainase 1 km; tidak mencakup parit kecil; **lisensi belum dicek** (kemungkinan CC BY) |
| Gambut utama (GFW Global Peatlands) | https://data.globalforestwatch.org/datasets/gfw::global-peatlands/about | Raster ~30 m | CC BY 4.0; Indonesia memakai Miettinen dkk. 2016; hanya ada/tidak, tanpa ketebalan; diunduh manual (URL langsung belum terverifikasi) |
| Gambut resmi (BBSDLP 2019) | https://data.go.id/dataset/dataset/peta-lahan-gambut-skala-1-50-000 | RAR (vektor) | Memuat kelas ketebalan, tetapi halaman 404 saat diperiksa dan literatur menyebut data di bawah hak cipta; jadikan sumber sekunder |
| Gambut alternatif (Kementan 2012 di GFW) | https://data.globalforestwatch.org/datasets/indonesia-peat-lands | Shapefile/GeoJSON | Lebih tua, mudah diunduh; cadangan |
| Penampil kedalaman gambut (tanpa unduhan) | https://pantaugambut.id/peta-gambut/gambaran-umum | Web | Hanya untuk melihat, bukan sumber data |
| Permukiman/penduduk alternatif | https://human-settlement.emergency.copernicus.eu/datasets.php (GHS-POP, GHS-BUILT-S R2023A) | GeoTIFF | Alternatif WorldPop yang lebih stabil; WorldPop Global2 R2025A masih berstatus alpha |
| Tutupan lahan KLHK | https://data.globalforestwatch.org/datasets/land-cover-indonesia | ArcGIS/vektor | Skala 1:250.000, versi 2017 di GFW; kelas lokal berguna (hutan rawa, perkebunan) tetapi tua |

### 11.3 Rencana VPD dan angin

- **VPD** (kPa) per langkah waktu dari `t2m` dan `d2m`: tekanan uap jenuh `es = 0,6108 * exp(17,27 * T / (T + 237,3))` dengan T dalam derajat C; VPD = `es(T) - es(Td)`. Agregasi harian: `vpd_mean` dan `vpd_max`. Rumus sama dengan yang dipakai untuk RH, jadi tambahkan di `instant_daily()` tanpa unduhan baru.
- **Arah angin**: simpan sebagai komponen `u10_mean`, `v10_mean` (atau sin/cos), bukan sudut 0-360, dan hanya bila ada hipotesis modeling yang memerlukannya.

### 11.4 Rencana agregasi lapisan statis ke sel 0,25 derajat (`build_static_features.py`)

| Lapisan | Fitur per sel |
|---|---|
| Gambut | fraksi luas gambut |
| Kanal Dadap | kerapatan drainase rata-rata |
| WorldCover | fraksi tiap kelas (hutan, semak, sawah, terbangun, dst.) |
| Hansen | `treecover2000` rata-rata; persen area `loss` per tahun; `loss` 1-3 tahun terakhir (diberi lag) |
| DEM | elevasi rata-rata, slope rata-rata |
| OSM | jarak rata-rata/minimum ke jalan, sungai, dan permukiman |
| WorldPop/GHSL | kepadatan penduduk |
| Konsesi | fraksi luas sawit dan HTI |
| geoBoundaries | provinsi dan pulau (spasial join pusat sel) |
| MCD64A1 | pernah terbakar 1/3/5 tahun terakhir; frekuensi terbakar (selalu diberi lag) |

Aturan: semua turunan memakai konvensi pusat sel yang sama dengan grid label (`n*0,25 + 0,125`), dan keluaran satu baris per sel.

### 11.5 Rencana fitur turunan (`build_derived_features.py`)

- Akumulasi hujan 7/14/30 hari, hari kering beruntun, anomali suhu dan RH terhadap klimatologi bulanan.
- **SPI** (dan SPEI dari `precip_mm - pev_mm`) skala 30 dan 90 hari, misalnya dengan `climate-indices` atau `xclim`.
- Fitur ENSO/IOD dengan lag 1-3 bulan; fitur kalender (bulan, musim kemarau, minggu dalam tahun).
- Lag hotspot 1-3 hari berasal dari tabel label milik anggota lain; pastikan skema `date, lat_c, lon_c` sama.
- **Uji anti-bocor wajib**: fitur untuk target hari T hanya memakai data sampai T-1.

### 11.6 Opsi validasi eksternal (tidak wajib)

| Sumber | Tautan | Peran | Kaveat |
|---|---|---|---|
| CHIRPS v3 | https://www.chc.ucsb.edu/data/chirps3 | Pembanding curah hujan 0,05 derajat | Data harian adalah disagregasi dari total 5-harian; final terbit sekitar 1,5 bulan terlambat |
| NASA POWER | https://power.larc.nasa.gov/docs/services/api/temporal/daily/ | Pembanding meteorologi (0,5 x 0,625 derajat) | Resolusi kasar; 2-3 hari terakhir kosong |
| BMKG Data Online | https://dataonline.bmkg.go.id/ | Validasi titik stasiun | Perlu registrasi, unduhan dibatasi 1 bulan per permintaan, data titik |
| NASA SMAP L4 | https://nsidc.org/data/spl4smgp/versions/8 | Pembanding kelembapan tanah | Butuh Earthdata Login; produk 14 Mei-28 Jul 2026 sedang diproses ulang |

### 11.7 Catatan perubahan layanan (per Oktober 2026, dari riset sumber)

- Data CEMS Fire hanya ada di EWDS sejak 26 September 2024; skrip yang masih mengarah ke CDS akan gagal.
- NOAA NESDIS (Update #2, 19 Okt 2026): pengiriman data Suomi NPP, termasuk VIIRS, berhenti 2 November 2026 pukul 13.00 UTC. Akibatnya VNP64A1 kemungkinan tidak diperbarui; pakai MCD64A1 (MODIS).
- GADM melarang penggunaan komersial dan redistribusi; geoBoundaries file IDN tercatat ODbL di HDX (cek `boundaryLicense`).
- Riset sumber awalnya merekomendasikan Open-Meteo untuk cuaca; **keputusan tim memakai Copernicus**. Open-Meteo (Forecast, Historical Forecast, Previous Runs API) tetap kandidat untuk **fitur real-time H+1 sampai H+3** pada TODO #9, dengan catatan batas gratis (sekitar 600 panggilan/menit, 5.000/jam, 10.000/hari per IP, non-komersial) dan risiko *train-serve skew* terhadap ERA5-Land.

## 12. Perkiraan ukuran dan waktu (kasar, belum diukur)

- ERA5-Land area `sumkal`: 354 request. Ukuran per file diperkirakan puluhan sampai ratusan MB; total puluhan GB. Waktu bergantung antrean CDS (menit sampai jam per request). Ukur dengan satu bulan sebelum menjalankan penuh.
- Hansen: 6 tile x 2 layer untuk `sumkal`. WorldCover: 36 tile (beberapa GB). DEM 90 m: 312 tile kecil, banyak yang 404 karena laut (dicatat `missing`, wajar).
- Ruang disk disarankan minimal 60 GB untuk `sumkal`, lebih untuk `indonesia`.

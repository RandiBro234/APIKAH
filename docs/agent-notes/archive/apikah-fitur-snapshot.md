> Snapshot fitur 2026-10-25. Path/status dapat berubah; gunakan dokumentasi pipeline terkini sebelum menjalankan.

# APIKAH — daftar fitur lengkap (68 fitur)

Dicatat: 2026-10-25

Daftar ini diturunkan dari **skema berkas nyata** yang sudah dihasilkan, bukan dari ingatan.
Angka "belum ada data" pada bagian statis berarti rasternya belum diunduh.

## Rekap

| Kelompok | Jumlah | Sumber | Berkas |
|---|---|---|---|
| A. Cuaca ERA5-Land | 16 | `postprocess_era5.py` | `data/processed/era5_daily/YYYY-MM.parquet` |
| B. Indeks bahaya api CEMS | 4 | `postprocess_fire.py` | `data/processed/fire_daily/YYYY-MM.parquet` |
| C. Turunan harian | 22 | `build_derived_features.py` | `data/processed/features_daily/YYYY-MM.parquet` |
| D. Statis | 26 | `build_static_features.py` | `data/processed/static_features.parquet` |
| **TOTAL** | **68** | | belum ada skrip penggabung |

Kunci semua tabel: `date`, `lat_c`, `lon_c` (pusat sel = `n*0,25 + 0,125`).

## A. Cuaca ERA5-Land — 16

| Fitur | Satuan | Arti |
|---|---|---|
| `t2m_mean`, `t2m_max`, `t2m_min` | °C | suhu udara 2 m |
| `rh_mean`, `rh_min` | % | kelembapan relatif (Magnus dari t2m, d2m) |
| `vpd_mean`, `vpd_max` | kPa | defisit tekanan uap; prediktor api terpenting setelah angin |
| `wind_mean`, `wind_max` | m/s | `hypot(u10, v10)` |
| `u10_mean`, `v10_mean` | m/s | **komponen** angin mentah (bukan sudut) untuk transport asap |
| `swvl1_mean` | m3/m3 | kelembapan tanah 0-7 cm |
| `swvl4_mean` | m3/m3 | kelembapan tanah 100-289 cm |
| `precip_mm` | mm/hari | hujan |
| `ssrd_mjm2` | MJ/m2 | radiasi matahari |
| `pev_mm` | mm/hari | evapotranspirasi potensial |

## B. Indeks bahaya api CEMS — 4

| Fitur | Arti |
|---|---|
| `fwi` | Forest Fire Weather Index (Canadian Forest Service) |
| `dc` | Drought Code -- kekeringan lapisan dalam, relevan untuk **gambut** |
| `dmc` | Duff Moisture Code |
| `kbdi` | Keetch-Byram Drought Index |

## C. Turunan harian — 22

| Fitur | Satuan | Arti |
|---|---|---|
| `hujan_3h`, `hujan_7h`, `hujan_14h`, `hujan_30h` | mm | total hujan berjalan (jendela penuh saja) |
| `kering_beruntun` | hari | hari beruntun dengan hujan < 1 mm |
| `t2m_mean_anom`, `rh_mean_anom`, `vpd_max_anom`, `precip_mm_anom` | sama dgn asalnya | selisih dari klimatologi bulanan sel |
| `spi_30`, `spi_90` | z-score | SPI empiris (peringkat -> kuantil normal) |
| `bulan` | 1-12 | bulan |
| `hari_dalam_tahun` | 1-366 | posisi dalam tahun |
| `musim_kemarau` | 0/1 | Jul-Okt, heuristik puncak kabut asap |
| `nino34`, `dmi` | °C | El Nino 3.4 dan Dipol Samudra Hindia (bulanan) |
| `nino34_lag1/2/3`, `dmi_lag1/2/3` | °C | lag 1-3 bulan |

## D. Statis — 26 (belum ada data)

| Kelompok | Fitur |
|---|---|
| DEM (4) | `elevasi_mean`, `elevasi_max`, `slope_mean`, `slope_max` |
| WorldCover 2021 (11) | `wc_pohon`, `wc_semak`, `wc_rumput`, `wc_tanaman`, `wc_terbangun`, `wc_gundul`, `wc_salju`, `wc_air`, `wc_lahan_basah`, `wc_mangrove`, `wc_lumut` (fraksi 0-1) |
| Hansen (4) | `treecover2000_mean`, `loss_frac_1y`, `loss_frac_3y`, `loss_frac_5y` |
| WorldPop (2) | `pop_density_mean`, `pop_density_sum` |
| Gambut (1) | `peat_fraksi` |
| OSM (4) | `jarak_jalan_m`, `jarak_jalan_min_m`, `jarak_sungai_m`, `jarak_sungai_min_m` |

## Dua jebakan saat menghitung/menggabungkan

1. **Jangan jumlahkan mentah -> 80 itu SALAH (hitungan ganda).**
   `features_daily` ikut **menyalin** 12 kolom cuaca mentah dari `era5_daily`. Jadi
   16 + 4 + 34 + 26 = 80 akan menghitung cuaca dua kali. Angka benar = **68**
   (16 + 4 + 22 + 26).
2. **`features_daily` MEMBUANG 4 kolom cuaca:** `t2m_max`, `t2m_min`, `wind_mean`,
   `wind_max` (tidak ada di `WEATHER_COLS` di `build_derived_features.py`).
   Karena itu skrip penggabung harus mengambil kolom cuaca dari **`era5_daily`** dan dari
   `features_daily` hanya kolom **turunan** (22), bukan seluruh isinya.

## Usul penandaan bertahap (belum diputuskan tim)

| Status | Jumlah | Catatan |
|---|---|---|
| **MVP** | ~25 | buang yang redundan; tutupan lahan dikelompokkan jadi ~5 kelas, bukan 11 |
| **V2** | ~15 | t2m_min, wind_max, vpd_mean, swvl4_mean, pev_mm, dmc, kbdi, hujan_3h/14h, anomali, SPI, lag iklim |
| **V3** | ~28 | sisanya + statis penuh (OSM, gambut, penduduk) |
| **DROP** | 3 | `pop_density_sum` (= mean x konstanta, luas sel tetap), `jarak_*_min_m` (hampir selalu 0), satu dari 11 `wc_*` (jumlahnya selalu 1 -> multikolinear sempurna) |

Alasan bertahap: hanya ada **4 musim ekstrem** (2014/2015/2019/2026) dalam 15 tahun, jadi
setiap fitur tambahan menaikkan risiko overfit tanpa jaminan manfaat. Ukur feature
importance lalu pangkas -- jangan menambah lapisan baru sebelum model inti terbukti.

## Tabel latih hasil penggabungan (`build_training_table.py`)

`data/processed/training/YYYY-MM.parquet` -- 3 kunci + 16 cuaca + 4 indeks api + 20 turunan
+ 4 target = **47 kolom**. Hanya sel darat (3.583 sel). Baris untuk tanggal T hanya memuat
informasi sampai T-1. Contoh terukur 2023-07: **111.073 baris x 47 kolom**.

Dua hal yang membuat jumlahnya bukan 68:

- `nino34` dan `dmi` (bulan berjalan) **dibuang karena bocor** -- rata-rata bulan T memuat
  hari T. Yang dipakai hanya `nino34_lag1..3` dan `dmi_lag1..3`
- 26 kolom statis **belum ada** (raster belum diunduh). Setelah statis siap, tabel menjadi
  **47 + 26 = 73 kolom**

## Cara verifikasi ulang

```powershell
cd "APIKAH\hotspot_crawler\hotspot_crawler"
python -c "import pandas as pd; d=pd.read_parquet('data/processed/era5_daily/2023-07.parquet'); print(len(d.columns), list(d.columns))"
python -c "import pandas as pd; d=pd.read_parquet('data/processed/fire_daily/2023-07.parquet'); print(len(d.columns), list(d.columns))"
python -c "import pandas as pd; d=pd.read_parquet('data/processed/features_daily/2023-07.parquet'); print(len(d.columns), list(d.columns))"
```

Statis belum punya data. Setelah raster diunduh: `python build_static_features.py`,
lalu periksa `data/processed/static_features.parquet`.

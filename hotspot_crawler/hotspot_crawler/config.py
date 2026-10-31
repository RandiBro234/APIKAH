"""Konfigurasi pusat crawler. Ubah di sini, bukan di skrip lain."""
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- rentang waktu
START = date(2012, 1, 1)    # sesuai keputusan tim: Januari 2012 ...
END = date(2026, 9, 30)     # ... sampai September 2026
# Catatan: VIIRS SNPP ada sejak 2012-01, NOAA-20 baru sejak 2018-04.
# Data cuaca/iklim ditarik dari 2012 supaya ablation SNPP 2012+ bisa jalan.

# ---------------------------------------------------------------- wilayah studi
# format: [north, west, south, east]
AREAS = {
    "sumkal": [6.0, 94.0, -6.0, 119.5],        # Sumatera + Kalimantan (default, hemat disk)
    "indonesia": [6.0, 94.0, -11.5, 141.5],    # seluruh Indonesia
}
# Diputuskan 25 Okt 2026: "indonesia". Alasan (terukur, bukan tebakan):
#   - `cost` dan JUMLAH REQUEST identik untuk kedua area (estimate_costs: ERA5 1488/186,
#     CEMS 124 -- sama persis). Tidak ada kerugian efisiensi, tidak ada risiko limit.
#   - cakupan label: `indonesia` 3.941.038 (100%) vs `sumkal` 2.726.820 (69,2%).
#   - yang berbeda hanya UKURAN FILE (~2x). Ukur dengan uji 1 bulan sebelum crawl penuh.
# Catatan rezim api: di luar sumkal sebagian besar savana (NTT/NTB/Papua/Jawa) yang
# mekanismenya beda dari gambut. Model mungkin perlu penanda wilayah.
ACTIVE_AREA = "indonesia"
AREA = AREAS[ACTIVE_AREA]

# ---------------------------------------------------------------- folder
# Resolve from this file, not CWD, so CLI entrypoints always share one data tree.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
FEATURES_RAW = DATA_DIR / "features_raw"
FEATURES_PROCESSED = DATA_DIR / "features_processed"
METADATA = DATA_DIR / "metadata"

# Compatibility aliases used by current pipeline modules.
RAW = FEATURES_RAW / "copernicus"
STATIC = FEATURES_RAW / "static"
MCD64A1_DIR = FEATURES_RAW / "nasa" / "mcd64a1"
PROCESSED = FEATURES_PROCESSED
LOGS = METADATA / "logs"

# ---------------------------------------------------------------- klien (setelan jaringan)
# Bawaan cdsapi.Client: sleep_max=120 detik, retry_max=500. Diukur 25 Okt 2026: pada jaringan
# yang putus-putus, 21 koneksi putus x 120 detik = ~15% waktu crawl habis HANYA untuk menunggu.
# Delay-nya yang mahal, bukan percobaan ulangnya -- jadi sleep_max diturunkan, retry_max tetap.
# Kalau jaringan stabil, angka ini tidak berpengaruh sama sekali.
CLIENT_SLEEP_MAX = 10     # bawaan 120; jeda maksimum antar percobaan ulang (detik)
CLIENT_RETRY_MAX = 500    # bawaan 500; jumlah percobaan ulang sebelum menyerah

# ---------------------------------------------------------------- ERA5-Land (CDS)
CDS_DATASET = "reanalysis-era5-land"
# Batas CDS berlaku pada nilai "cost" yang dilaporkan API, BUKAN pada jumlah field.
# Diukur 24 Okt 2026 lewat estimate_costs() (bukan dari dokumentasi):
#     cost = 2 x (variabel x hari x jam),  dan limit cost = 12000
#     instant: 8 bulan x 28 hari = 5376 field -> cost 10752 (89,6%)  OK
#              9 bulan x 28 hari = 6048 field -> cost 12096 (100,8%) DITOLAK
#     accum  : 5 tahun x 12 bulan x 28 hari = 5040 field -> 84,0%    OK
#              6 tahun                    = 6048 field -> 100,8%   DITOLAK
# Jadi batas field praktis = 6000, bukan 12000 seperti tertulis di dokumentasi CDS
# (dokumentasi memakai satuan "field", API memakai satuan "cost").
# Jangan naikkan angka ini tanpa mengukur ulang dengan verify_params.py.
ERA5_COST_LIMIT = 12000          # limit "cost" per request, dari API
ERA5_COST_PER_FIELD = 2          # cost = 2 x field (hasil pengukuran)
ERA5_FIELD_LIMIT = ERA5_COST_LIMIT // ERA5_COST_PER_FIELD    # = 6000, batas aman

# Variabel instan -> diambil pada beberapa jam saja (UTC), lalu mean/min/max harian.
ERA5_INSTANT = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "volumetric_soil_water_layer_1",   # 0-7 cm
    "volumetric_soil_water_layer_4",   # 100-289 cm (lapisan dalam)
]
# 00,06,12,18 UTC = 07,13,19,01 WIB. 06 UTC (13 WIB) menangkap RH minimum siang.
ERA5_INSTANT_TIMES = ["00:00", "06:00", "12:00", "18:00"]

# Variabel akumulasi -> cukup 00:00 UTC; nilai di 00:00 hari D+1 = total hari D.
ERA5_ACCUM = [
    "total_precipitation",
    "surface_solar_radiation_downwards",
    "potential_evaporation",
]
ERA5_ACCUM_TIMES = ["00:00"]

# ---------------------------------------------------------------- CEMS Fire (EWDS)
EWDS_DATASET = "cems-fire-historical-v1"
# NAMA parameter di bawah sudah diverifikasi 21 Okt 2026 terhadap enum resmi dataset
# (lihat verify_params.py): 4 variabel, product_type, dataset_type, system_version,
# dan grid semuanya ada, dan `area` memang didukung dataset ini.
# Yang BELUM diuji: unduhan nyata, dan perilaku "intermediate_dataset" untuk bulan terakhir.
FIRE_VARIABLES = [
    "fire_weather_index",
    "drought_code",
    "duff_moisture_code",
    "keetch_byram_drought_index",
]
FIRE_PRODUCT_TYPE = ["reanalysis"]
FIRE_SYSTEM_VERSION = ["4_1"]
FIRE_DATASET_TYPE = "consolidated_dataset"      # bulan terbaru: "intermediate_dataset"
FIRE_INTERMEDIATE_LAST_N_MONTHS = 4             # N bulan terakhir coba intermediate
# Grid "original_grid" HANYA tersedia dalam format grib. Dibuktikan 21 Okt 2026 dari
# berkas constraints resmi (84 blok kombinasi sah): pasangan original_grid + netcdf
# ditolak dengan 400 "has not produced a valid combination of values".
# Karena grid asli CEMS Fire memang 0,25 derajat (lihat TODO #4), meminta "0.25/0.25"
# menghasilkan resolusi yang SAMA tetapi dalam netcdf, yang bisa dibaca xarray/netCDF4
# tanpa perlu cfgrib/eccodes. Jangan kembalikan ke original_grid tanpa ganti ke grib.
FIRE_GRID = "0.25/0.25"
FIRE_TRY_AREA = True                            # coba subset area; fallback global bila ditolak

# Batas biaya CEMS Fire, diukur 24 Okt 2026 lewat estimate_costs():
#     cost = variabel x hari (rasio 1, berbeda dari ERA5-Land yang rasionya 2),
#     dan limit cost = 3720. Pemakaian sekarang 4 var x 31 hari = 124 (3,3%).
# Ini batas dataset, terpisah dari batas ERA5-Land di atas.
FIRE_COST_LIMIT = 3720
FIRE_COST_PER_FIELD = 1

# ---------------------------------------------------------------- sumber lain
# Diverifikasi 21 Okt 2026 dari mesin berinternet:
#   - gcos_wgsp/Timeseries/Data/nino34.long.anom.data  -> 404 (URL lama sudah mati)
#   - data/correlation/nina34.anom.data                -> 200, anomali Niño 3.4 bulanan
#   - gcos_wgsp/Timeseries/Data/dmi.had.long.data      -> 200, DMI (HadISST)
# Format keduanya sama: baris pertama 'tahun_awal tahun_akhir', lalu 'tahun v1..v12'.
ENSO_URLS = {
    "nino34": "https://psl.noaa.gov/data/correlation/nina34.anom.data",
    "dmi": "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data",
}
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/IDN/{level}/"
GEOBOUNDARIES_LEVELS = ["ADM1", "ADM2"]

HANSEN_VERSION = "GFC-2025-v1.13"
HANSEN_URL = ("https://storage.googleapis.com/earthenginepartners-hansen/{ver}/"
              "Hansen_{ver}_{layer}_{lat:02d}{ns}_{lon:03d}{ew}.tif")
HANSEN_LAYERS = ["treecover2000", "lossyear"]
# Tahun acuan untuk lag `lossyear`. Rilis GFC-2025-v1.13 memuat kehilangan sampai 2025
# (lossyear 1..25 = 2001..2025), jadi acuannya 2025. Dipakai build_static_features.py
# untuk menghitung loss_frac_{1,3,5}y sebagai "kehilangan sampai acuan-lag", bukan tahun
# berjalan -- mencegah kebocoran masa depan (bagian 7.3 dokumen).
HANSEN_LOSS_REF_YEAR = 2025

WORLDCOVER_URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                  "ESA_WorldCover_10m_2021_v200_{ns}{lat:02d}{ew}{lon:03d}_Map.tif")

DEM_URL = ("https://copernicus-dem-90m.s3.amazonaws.com/"
           "Copernicus_DSM_COG_30_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
           "Copernicus_DSM_COG_30_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")

GEOFABRIK_URLS = {
    "sumatra": "https://download.geofabrik.de/asia/indonesia/sumatra-latest.osm.pbf",
    "kalimantan": "https://download.geofabrik.de/asia/indonesia/kalimantan-latest.osm.pbf",
}

# WorldPop: rilis Global1 (diarsipkan) dipakai sebagai default karena pola URL-nya stabil.
# Ganti ke R2025A (alpha) bila sudah dicek: https://hub.worldpop.org/geodata/listing?id=135
WORLDPOP_URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/"
                "2020/IDN/idn_ppp_2020_1km_Aggregated.tif")

# NASA Earthdata (MCD64A1 burned area). Butuh akun gratis; kredensial lewat env var
# EARTHDATA_USERNAME / EARTHDATA_PASSWORD.
MCD64A1 = {"short_name": "MCD64A1", "version": "061"}

# ---------------------------------------------------------------- gambut
# Sebelumnya manual lewat browser (peta WRI/GFW). Diganti 28 Okt 2026: paket
# Open-Earth-Monitor di Zenodo punya GeoTIFF 1 km EPSG:4326 yang bisa diunduh LANGSUNG
# tanpa akun, jadi tidak perlu lagi langkah manual. Server WRI sendiri
# (gis-gfw.wri.org) TIDAK bisa dihubungi dari mesin ini (HTTP & HTTPS), dan versi
# Indonesia-nya minta token API -- karena itu jalur browser ditinggalkan.
#
# Isi `extent` adalah PROBABILITAS 0-100: berapa dari 3 peta sumber (WRI/GFW global
# peatlands, PEATGRIDS, Global Peatlands Map 2.0) yang menyebut piksel itu gambut.
# Karena itu `> 0` SALAH (menandai hampir semua piksel). Diukur 28 Okt 2026 di jendela
# Indonesia (94-142E, 12S-7N):
#     > 0   -> 98,6 juta ha   (7x literatur -- jelas salah)
#     >= 25 -> 47,7 juta ha
#     >= 50 -> 33,2 juta ha
#     >= 75 -> 23,3 juta ha
#     == 100 -> 11,6 juta ha  <- paling dekat literatur 13-15 juta ha
# `== 100` juga bermakna: irisan yang disepakati KETIGA peta. Jangan turunkan tanpa
# mengukur ulang dan membandingkan dengan literatur.
PEAT_BASE_URL = "https://zenodo.org/records/13951439/files/"
PEAT_FILES = {
    "extent": "peatland.extent_wri.gfw_p_1km_s_2000_2020_go_epsg4326_v20241017.tif",
    "thickness": "peatland.thickness.cm_peatgrids.v1_m_1km_s_2000_2020_go_epsg4326_v20241017.tif",
    "carbon": "peatland.soc.mgc.ha_peatgrids.v1_m_1km_s_2000_2020_go_epsg4326_v20241017.tif",
}
PEAT_THRESHOLD = 100          # ambang "ini gambut" pada raster `extent` (0-100)
PEAT_REQUIRED = ("extent",)   # `thickness`/`carbon` opsional: tanpa itu fiturnya kosong

# Status drainase/konsesi gambut TIDAK tersedia terbuka di mana pun; itu justru pemicu
# api gambut yang paling kuat. Catat sebagai keterbatasan, jangan diakali.

# ---------------------------------------------------------------- label hotspot (milik tim lain)
# Label titik api BUKAN bagian crawler ini; diambil anggota tim lain dan disimpan di
# data/ repo (bukan data/ crawler). Dipakai hanya oleh build_training_table.py.
# Path relatif terhadap folder crawler: ../../data -> APIKAH/data
HOTSPOT_LABELS = (DATA_DIR / "hotspot_indonesia" / "combined" /
                  "hotspot_indonesia_2012_2026-09.parquet")

# ---------------------------------------------------------------- perilaku download
RETRIES = 3
BACKOFF_SECONDS = 30
HTTP_TIMEOUT = 60
SLEEP_BETWEEN_REQUESTS = 2

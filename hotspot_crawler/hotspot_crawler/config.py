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
DATA_DIR = Path("data")
RAW = DATA_DIR / "raw"
STATIC = DATA_DIR / "static"
PROCESSED = DATA_DIR / "processed"
LOGS = DATA_DIR / "logs"

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

# ---------------------------------------------------------------- perilaku download
RETRIES = 3
BACKOFF_SECONDS = 30
HTTP_TIMEOUT = 60
SLEEP_BETWEEN_REQUESTS = 2

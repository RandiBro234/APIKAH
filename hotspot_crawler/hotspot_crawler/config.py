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
ACTIVE_AREA = "sumkal"
AREA = AREAS[ACTIVE_AREA]

# ---------------------------------------------------------------- folder
DATA_DIR = Path("data")
RAW = DATA_DIR / "raw"
STATIC = DATA_DIR / "static"
PROCESSED = DATA_DIR / "processed"
LOGS = DATA_DIR / "logs"

# ---------------------------------------------------------------- ERA5-Land (CDS)
CDS_DATASET = "reanalysis-era5-land"
# Batas CDS: ERA5-Land hourly maks 12.000 field per request (var x hari x jam).
ERA5_FIELD_LIMIT = 12000

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
# PERINGATAN: nama parameter di bawah disusun dari ingatan/dokumentasi, belum diuji
# dari workspace (akses jaringan diblokir). Verifikasi lewat tombol "Show API request"
# di https://ewds.climate.copernicus.eu/datasets/cems-fire-historical-v1?tab=download
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
FIRE_GRID = "original_grid"
FIRE_TRY_AREA = True                            # coba subset area; fallback global bila ditolak

# ---------------------------------------------------------------- sumber lain
ENSO_URLS = {
    "nino34": "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/nino34.long.anom.data",
    "dmi": "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data",
}
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/IDN/{level}/"
GEOBOUNDARIES_LEVELS = ["ADM1", "ADM2"]

HANSEN_VERSION = "GFC-2025-v1.13"
HANSEN_URL = ("https://storage.googleapis.com/earthenginepartners-hansen/{ver}/"
              "Hansen_{ver}_{layer}_{lat:02d}{ns}_{lon:03d}{ew}.tif")
HANSEN_LAYERS = ["treecover2000", "lossyear"]

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

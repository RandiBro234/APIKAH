# APIKAH — panduan pipeline

Panduan aktif untuk crawler, fitur, dan data. Arsip operasional lama ada di [`../agent-notes/archive/PIPELINE_DEV_history.md`](../agent-notes/archive/PIPELINE_DEV_history.md).

## Struktur repo dan data

```text
APIKAH/
├── data/
│   ├── hotspot_indonesia/              # label area Indonesia (tracked)
│   │   └── combined/                   # Parquet kanonis; CSV legacy terpotong
│   ├── hotspot_raw/                    # label sumber (tracked)
│   ├── features_raw/
│   │   ├── copernicus/era5land/{instant,accum}/
│   │   ├── copernicus/cems_fire/
│   │   ├── nasa/mcd64a1/
│   │   └── static/{boundaries,climate_index,dem,hansen,osm,peatlands,worldcover,worldpop}/
│   ├── features_processed/
│   │   ├── era5_daily/  ├── fire_daily/  ├── climate_index/
│   │   ├── static/      ├── features_daily/  └── training/
│   └── metadata/{manifests,logs}/
├── hotspot_crawler/
│   ├── apikah_crawler/                 # implementasi package
│   ├── tests/                          # unit, integrasi sintetis, CLI
│   └── *.py                            # wrapper command lama
└── docs/{pipeline,agent-notes,superpowers}/
```

Semua path keluaran ditentukan dari lokasi package, bukan current working directory. Jalankan command dari `APIKAH/hotspot_crawler/` agar wrapper dan package ditemukan.

## Format data

- Pertahankan sumber grid/vektor dalam format aslinya: ERA5/CEMS `.nc`, MCD64A1 `.hdf`, raster `.tif`, OSM `.pbf`, dan GeoJSON.
- Tabel tabular yang sudah diparse/diolah disimpan sebagai Parquet. Climate-index NOAA yang dipakai pipeline tersedia di `data/features_processed/climate_index/{nino34,dmi}.parquet`; sumber teks `.raw.txt` tetap di `features_raw` untuk provenance.
- ERA5/CEMS sudah memiliki processor menuju Parquet (`postprocess_era5.py`, `postprocess_fire.py`); raster statis masuk ke `static_features.parquet`. Feature builder membuat `features_daily` dan tabel training.
- MCD64A1 untuk saat ini **hanya data mentah**; belum ada processor burned-area.
- CSV gabungan hotspot legacy hanya berisi 1.048.575 baris; Parquet gabungan berisi 3.941.038. Gunakan Parquet untuk analisis lengkap; CSV dipertahankan sebagai file historis/kompatibilitas.

## Setup dan kredensial

Gunakan Python 3.12. Virtual environment tidak diwajibkan.

```powershell
cd "C:\path\ke\APIKAH\hotspot_crawler"
python -m pip install -r requirements.txt
```

CDS dan EWDS menggunakan file credential di home directory (`.cdsapirc` dan `.ewdsapirc`). Earthdata hanya dibutuhkan jika kelak mengunduh ulang MCD64A1; jangan simpan password/token dalam repo.

## Perintah utama

```powershell
# Pemeriksaan dan dry-run (tanpa request unduhan)
python verify_params.py
python preflight.py --only cds ewds
python crawl_copernicus.py all --dry-run
python crawl_static.py all --dry-run

# Crawl/resume; berkas selesai akan dilewati
python crawl_copernicus.py all
python crawl_static.py all
python crawl_static.py worldcover       # opt-in
python crawl_static.py burned           # opsional, autentikasi Earthdata

# Postprocess/fitur, jalankan setelah input yang dibutuhkan lengkap
python postprocess_era5.py
python postprocess_fire.py
python build_static_features.py
python build_derived_features.py
python build_training_table.py

# Status dari folder mana pun di dalam repo
powershell -ExecutionPolicy Bypass -File "C:\path\ke\APIKAH\hotspot_crawler\status.ps1"
```

Gunakan rentang `--from YYYY-MM --to YYYY-MM` untuk uji/lanjutan terbatas. Jangan jalankan dua worker pada berkas/bulan yang sama. Manifest memiliki lock lintas proses agar update worker tidak saling menimpa.

## Tes dan verifikasi

Jalankan dari `hotspot_crawler/`:

```powershell
python -m tests.test_derived
python -m tests.test_postprocess
python -m tests.test_static
python -m tests.test_training
python -m tests.test_paths
python -m unittest tests.test_cli_wrappers tests.test_climate_parquet tests.test_migrate_data_layout tests.test_manifest_concurrency
python smoke_static.py
python verify_params.py
```

Tes tidak memakai network/dataset produksi kecuali `verify_params.py` yang memeriksa katalog API. Smoke test statis menggunakan raster sintetis di temporary directory.

## Kebijakan Git dan migrasi

- `data/features_raw/` dan `data/metadata/logs/` di-ignore Git. Label hotspot yang telah dilacak tetap tracked.
- `features_processed/` tidak di-ignore menyeluruh; sebelum staging, audit ukuran dan lisensi. Hindari file tunggal lebih dari 100 MB dan jangan stage semua folder sekaligus.
- `data/metadata/manifests/` berisi catatan status kecil yang boleh dilacak; file `.lock` bersifat runtime dan di-ignore.
- `migrate_data_layout.py` default hanya menampilkan dry-run. `--apply` menyalin data lama dan memverifikasi SHA-256, **tanpa menghapus sumber**. Hapus sumber lama hanya setelah count/hash/status semua tervalidasi.

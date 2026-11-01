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
│   └── metadata/{manifests,logs,locks}/
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
- MCD64A1 untuk saat ini **hanya data mentah**; belum ada processor burned-area. Job `burned` memakai lock direktori dan skip hanya jika fingerprint query serta semua nama granula HDF yang diharapkan ada sebagai file lokal non-kosong.
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

Gunakan rentang `--from YYYY-MM --to YYYY-MM` untuk uji/lanjutan terbatas. Lock per target mencegah dua worker mengunduh/menulis berkas yang sama; manifest juga dikunci lintas proses. Tetap bagi rentang worker agar tidak membuang request pada bulan yang sama.

Unduhan HTTP hanya melanjutkan `.part` jika sidecar cocok dengan URL sumber, validator (ETag/Last-Modified), panjang total, dan `Content-Range`. Jika URL/objek/range berubah atau metadata tidak tersedia, file parsial dibuang dan unduhan dimulai ulang agar byte dari versi berbeda tidak tercampur. Partial kosong tidak pernah dipublikasikan; tujuan 0-byte dapat diganti unduhan valid. Migrasi memakai hard-link no-clobber; filesystem target harus mendukung hard links (NTFS lokal yang dipakai sudah mendukung). Jika tidak, migrasi gagal dengan aman dan salinan sumber tetap ada.

## Tes dan verifikasi

Jalankan dari `hotspot_crawler/`:

```powershell
python -m tests.test_derived
python -m tests.test_postprocess
python -m tests.test_static
python -m tests.test_training
python -m tests.test_paths
python -m unittest tests.test_cli_wrappers tests.test_climate_parquet tests.test_migrate_data_layout tests.test_manifest_concurrency tests.test_download_file tests.test_copernicus_concurrency tests.test_burned_download_lock
python smoke_static.py
python verify_params.py
```

Tes tidak memakai network/dataset produksi kecuali `verify_params.py` yang memeriksa katalog API. Smoke test statis menggunakan raster sintetis di temporary directory.

## Kebijakan Git dan migrasi

- `data/features_raw/` dan `data/metadata/logs/` di-ignore Git. Label hotspot yang telah dilacak tetap tracked.
- `features_processed/` tidak di-ignore menyeluruh. Contoh keluaran dua bulan (ERA5/CEMS/turunan/training, total ~81,8 MB, terbesar 16,2 MB) sudah di-track beserta atribusi di [`data/NOTICE.md`](../../data/NOTICE.md). Sebelum menambah keluaran lain: audit ukuran (<100 MB per file) dan pastikan atribusi tetap benar.
- Data turunan Copernicus memakai CC-BY 4.0, jadi redistribusi boleh **asalkan atribusi disertakan**. Jangan hapus `data/NOTICE.md` selama tabel turunan masih ada di repo.
- `data/metadata/manifests/` berisi catatan status kecil yang boleh dilacak; lock files lintas proses berada di `data/metadata/locks/` dan di-ignore.
- `migrate_data_layout.py` default hanya menampilkan dry-run. `--apply` menyalin data lama dan memverifikasi SHA-256, **tanpa menghapus sumber**. Hapus sumber lama hanya setelah count/hash/status semua tervalidasi.

## Berbagi data mentah ke rekan

Data mentah crawler **tidak** disimpan di Git: 4.135 berkas, 16,91 GB, dan 14 berkas di antaranya >100 MB (batas keras GitHub per file). Menaruhnya di Git akan membuat clone sangat lambat dan push ditolak.

Pembagiannya:

| Arsip Drive | Ukuran | Isi |
|---|---|---|
| `copernicus.zip` | 7,16 GB | `era5land/{instant,accum}`, `cems_fire` (531 `.nc`) |
| `nasa.zip` | 4,07 GB | `mcd64a1` (2.992 `.hdf`) |
| `static.zip` | 5,68 GB | hansen, worldcover, dem, osm, boundaries, peatlands (612 berkas) |

Tempat arsip dan cara memasangnya dijelaskan di `data/features_raw/README_data_mentah.txt` (satu file, ikut Git).

Ekstrak ke `data/features_raw/` tanpa mengubah nama folder, lalu verifikasi.

Yang dibagikan lewat Git hanyalah **daftar checksum** berkas:

- `data/MANIFEST_raw.csv` — 4.135 baris: `path,bytes,sha256` (path relatif terhadap `data/`).

Alur untuk rekan yang menerima salinan data (dari drive/Zenodo/transfer langsung):

```powershell
cd "C:\path\ke\APIKAH\hotspot_crawler"
python verify_data.py
```

Hasil yang diharapkan:

```text
ok       : 4135
mismatch : 0
missing  : 0
invalid  : 0
SEMUA COCOK dengan manifest.
```

Jika ada `mismatch`/`missing`, jangan pakai datanya: minta ulang berkas yang disebut, atau bangun ulang dari sumber dengan crawler. Verifier membaca ulang seluruh berkas (SHA-256), jadi butuh beberapa menit untuk 17 GB.

Untuk mengambil data langsung dari sumbernya, jalankan `crawl_copernicus.py`/`crawl_static.py`; hasilnya akan cocok dengan manifest selama rentang dan parameter tidak diubah.

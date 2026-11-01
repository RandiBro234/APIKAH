# HotSpot Project Agent Guide

## Overview
- Hotspot risk prediction pipeline for Karhutla (forest fires)
- Two main parts:
  1. `hotspot_crawler/` - Downloads and processes weather/static data
  2. `modeling/` - Jupyter notebooks for EDA and model training
  3. `frontend/` - React + Vite dashboard (see frontend section below)
- Data range: Jan 2012 - Sep 2026 (0.25 degree grid, daily)
- Primary data sources: Copernicus (ERA5-Land via CDS, Fire Risk via EWDS)

## Dokumen acuan (baca dulu)
- `docs/pipeline/README.md` — perintah dan lokasi data yang aktif
- `docs/agent-notes/README.md` — konteks, handoff terkini, arsip catatan lama
- `docs/superpowers/` — desain dan rencana refactor
- `data/NOTICE.md` — atribusi dan lisensi data turunan

## Setup
```powershell
cd .\hotspot_crawler
pip install -r requirements.txt
```
- Python 3.12 recommended
- Some scripts require internet for API connectivity checks

## Struktur kode dan data
- Implementasi crawler: `hotspot_crawler/apikah_crawler/`
- CLI wrapper dengan nama lama: `hotspot_crawler/*.py` (tetap dipakai, jangan ganti nama)
- Tes: `hotspot_crawler/tests/`
- Semua data di `data/`:
  - `hotspot_indonesia/` + `hotspot_raw/` — label (tracked)
  - `features_raw/` — input crawler mentah (diabaikan Git; lihat `README_data_mentah.txt`)
  - `features_processed/` — tabel Parquet turunan (sebagian tracked)
  - `metadata/{manifests,logs,locks}/`

## Key Commands
### Pre-flight Checks (Run before any crawling)
```powershell
cd .\hotspot_crawler
python verify_params.py    # parameter vs enum resmi CDS/EWDS, tanpa unduh
python preflight.py        # cek endpoint dan kredensial
```
Both scripts must pass (green) before crawling.

### Testing
Jalankan dari `hotspot_crawler/`:
```powershell
python -m tests.test_derived
python -m tests.test_postprocess
python -m tests.test_static
python -m tests.test_training
python -m tests.test_paths
python -m unittest tests.test_cli_wrappers tests.test_climate_parquet `
    tests.test_migrate_data_layout tests.test_manifest_concurrency `
    tests.test_download_file tests.test_copernicus_concurrency `
    tests.test_burned_download_lock tests.test_verify_data
python smoke_static.py
```
`unittest discover` bukan runner proyek ini karena tes custom memakai skrip standalone.

### Crawling Scripts
- `crawl_copernicus.py` - Download ERA5-Land and CEMS Fire data
- `crawl_static.py` - Download static sources (DEM, land cover, OSM, MCD64A1, ...)
- Post-processing: `postprocess_era5.py`, `postprocess_fire.py`
- Feature building: `build_static_features.py`, `build_derived_features.py`, `build_training_table.py`
- Utilitas: `report_manifest.py`, `verify_data.py`, `status.ps1`

## Pipeline Order
1. Run `verify_params.py` and `preflight.py` (internet required)
2. Execute crawl scripts as needed (typically Copernicus then static)
3. Run post-processing scripts
4. Generate features with `build_derived_features.py` and `build_static_features.py`
5. Create training table with `build_training_table.py`

## Raw data dan berbagi
- Data mentah crawler (~16,9 GB, 4.135 berkas) **tidak** disimpan di Git.
- Arsip ada di Drive; link, isi zip, dan cara memasang: `data/features_raw/README_data_mentah.txt`.
- Setelah mengekstrak, verifikasi dengan `python verify_data.py` (cek SHA-256 terhadap `data/MANIFEST_raw.csv`).

## Modeling
- Jupyter notebooks in `modeling/`:
  - `EDA.ipynb` - Exploratory data analysis
  - `model.ipynb` - Model training and evaluation
- Run with Jupyter or VS Code

## Important Notes
- All logs and messages are in Indonesian
- Code comments and variable names are in English
- Jangan commit isi `data/features_raw/`, `data/metadata/logs/`, atau `data/metadata/locks/`
- Periksa ukuran dan lisensi satu per satu sebelum menambahkan hasil ke `features_processed/`; jangan `git add -A`
- Pertahankan data hotspot yang sudah tracked; jangan menambah berkas GADM baru ke repo publik
- Setiap perubahan bermakna mendapat commit tersendiri dan tidak di-push tanpa instruksi
- For full pipeline execution, see `docs/pipeline/README.md`

<!-- antislop:start -->
## antislop
Untuk semua pekerjaan UI, copy, atau kode di proyek ini:
1. Baca `DESIGN.md` untuk arah visual (palette, tipografi, dial, token).
2. Baca skill antislop sesuai task:
   - UI / visual: `skill://antislop-ui`
   - Mobile / responsive: `skill://antislop-layoutmobile`
   - Aksesibilitas / kontras: `skill://antislop-human`
   - Copy / teks: `skill://antislop-copywriting`
   - Komentar kode: `skill://antislop-code`
3. Sebelum mulai, tanya kapan antislop diterapkan: saat generate (DURING) atau setelah selesai (AFTER).
<!-- antislop:end -->

<!-- hotspot-frontend:start -->
## Frontend HOTSPOT.ID, diperbarui 30 Okt 2026

### Ringkasan proyek
- Aplikasi React + Vite untuk peta risiko munculnya hotspot di Indonesia.
- Implementasi bertahap; jangan lanjut fase sebelum pengguna menyatakan “lanjut”.
- Frontend baru berada di `frontend/`. Jangan membaca atau mengubah `frontend_old/`.

### Aturan istilah
- UI selalu berbahasa Indonesia. Pakai “risiko munculnya hotspot” dan “perkiraan area terdampak”.
- Tampilkan selalu “Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.”
- Data simulasi harus berlabel “DATA CONTOH”; jangan tampilkan angka simulasi sebagai fakta.
- Jangan tampilkan rujukan dokumen internal di UI. Jangan gunakan istilah “hutan hilang”.

### Teknologi dan perintah
- React, Vite, TypeScript strict, Tailwind CSS, ESLint, MapLibre GL JS.
- `cd .\frontend; npm run dev`
- `cd .\frontend; npm run typecheck`
- `cd .\frontend; npm run lint`
- `cd .\frontend; npm run build`
- `cd .\frontend; npm run data:sample`

### Peta folder
- `frontend/src/`: aplikasi React, komponen peta, utilitas, tipe.
- `frontend/src/styles/`: token terang dan aturan UI.
- `frontend/public/data/`: GeoJSON statis dan metadata contoh.
- `frontend/scripts/`: generator data contoh.

### Token dan desain
- Token hanya di CSS variables pada `frontend/src/styles/tokens.css`; tema terang saja.
- Netral: bg `#F7F7F5`, surface `#FFFFFF`, surface-2 `#F0F0ED`, line `#E2E2DD`, line-strong `#BDBDB6`, text `#141414`, text-muted `#55554F`, text-dim `#6E6E68`.
- Peta: map-bg `#F7F7F5`, map-land `#E4E4DF`, map-line `#FFFFFF`.
- Risiko: `#22D36B`, `#FFD60A`, `#FF8A00`, `#FF2D3D`; varian teks ink `#0A7F3C`, `#7A5F00`, `#B35400`, `#D4172B`.
- Bentuk: radius 6px (kontrol), radius-lg 10px (kartu dan panel melayang); garis 1px; bayangan hanya untuk panel yang melayang di atas peta.
- Tipografi: Inter untuk hampir semua teks; JetBrains Mono hanya untuk angka, ID, waktu, dan koordinat. Label memakai huruf biasa (sentence case), tanpa uppercase dan tanpa jarak huruf lebar.
- Risiko saja memakai warna risiko. Status sistem netral; hotspot aktual hitam bertepi putih.
- Hormati reduced motion, keyboard, fokus terlihat, kontras WCAG AA, target sentuh 44px.

### Kontrak data
- `meta.json`: `generated_at`, `data_hotspot_latest_at`, `model_version`, `data_version`, `stale_after_hours`.
- Risiko d0-d3: GeoJSON Polygon dengan `cell_id`, `level` (1-4), `score` (0-1), `province`, `island`, maksimal 3 `drivers`, `peat_pct`.
- Hotspot 72 jam: GeoJSON Point dengan `time_local`, `confidence` (`l|n|h`), `frp`.
- Grid 0,25°: `lat_i = floor((lat + 12) / 0.25)`, `lon_i = floor((lon - 94) / 0.25)`, `cell_id = lat_i * 1000 + lon_i`. Rumus tidak boleh berubah.
- Tampilkan “DATA BASI” bila `generated_at` melebihi `stale_after_hours`.
- Gunakan tipe GeoJSON/peta eksplisit, jangan pakai `any`.

### Daftar periksa fase
- Fase 1: shell, token/font, header, status, legenda, catatan batasan, peta dasar terang dan atribusi. Jalankan typecheck, lint, build, server dev dan verifikasi browser.
- Fase 2: skrip data contoh, sel risiko, hotspot, pemilih horizon, saklar lapisan. Verifikasi semua pemeriksaan sebelum berhenti.
- Fase 3: tooltip, detail sel, grafik hotspot, gambut, dampak rentang, dok wilayah, alternatif daftar/tabel, layout mobile. Verifikasi semua pemeriksaan sebelum berhenti.
- Fase 4 hanya atas permintaan: halaman Metode dan landing page.
- Setelah tiap fase, laporkan perubahan, file, verifikasi, dan hal terbuka; tunggu persetujuan sebelum lanjut.
<!-- hotspot-frontend:end -->

# Rencana implementasi: refactor crawler dan data APIKAH

**Branch:** `refactor/crawler-data-layout`
**Desain:** [2026-10-31-crawler-data-refactor-design.md](../specs/2026-10-31-crawler-data-refactor-design.md)
**Aturan:** setiap tahap bermakna dikomit terpisah; jangan commit data mentah.

## Progres pelaksanaan (2026-10-31)

- Selesai: remote `origin/main` diperbarui dengan commit tim `cd1b892`; baseline crawler lokal dikomit; branch refactor dibuat.
- Selesai: project-root path resolver, data migrator salin+SHA-256, migrasi lokal seluruh crawler data (~16.99 GiB), relokasi combined labels, raw/source `.raw.txt` dipertahankan, salinan nested lama dihapus setelah verifikasi.
- Selesai: package `apikah_crawler`, wrapper CLI bernama sama, tests di `hotspot_crawler/tests/`, dan `requirements.txt`/`status.ps1` di crawler root.
- Selesai: NOAA climate table Parquet (177 baris NINO3.4, 173 DMI; sama dengan tabel CSV lama), notebook aktif memakai Parquet. MCD64A1 tetap raw-only; download dikunci dan dataset lengkap dilewati.
- Selesai: lock per-target unduhan dan lock manifest lintas proses; root `AGENTS.md`, runbook/agent notes dipisahkan dan arsip lama diberi peringatan.
- Selesai setelah review: migrator memakai no-clobber finalisasi (hard-link pada filesystem yang mendukung); lock per-target/dataset mencegah worker mengunduh file yang sama; HTTP resume divalidasi terhadap URL-hash, ETag/Last-Modified, Content-Range dan panjang file. MCD64A1 skip memakai fingerprint query dan identitas granula, bukan jumlah file saja. Tes mencakup skip, resume, URL/range/ETag berubah, zero-length partial, 416, HTTP failure, 404, failed manifest status, dan concurrent download/ENSO/Copernicus/MCD64A1.
- Audit data: CSV hotspot legacy 1.048.575 baris vs Parquet 3.941.038, jadi tetap disimpan sebagai file historis dan tidak dipakai pipeline. Tujuh Parquet hasil olahan lama (81.8 MB, hanya dua bulan) tidak di-stage karena parsial dan lisensi redistribusi belum diaudit; dua Parquet climate-index kecil sudah tracked.
- Verifikasi akhir selesai: 83 tes custom, 33 tes unittest, 2 tes EDA notebook, smoke test, compileall, manifest report, dan `verify_params.py` (60 OK/0 WARN/0 FAIL) lulus. Review read-only independent (4 putaran) menemukan race migrator no-clobber, unduhan target ganda, resume HTTP tanpa validasi, partial kosong, dan racikan identitas granula MCD; semuanya diperbaiki dengan regression tests. Tiga commit terakhir (ignore path legacy + identitas granula MCD64A1) direview in-session karena reviewer subagent terakhir kehabisan waktu pada konteks penuh — tidak ada temuan critical/important yang tersisa.

## Prasyarat dan baseline (selesai)

- Crawl lengkap dan manifest tervalidasi: ERA5 354/354 kunci, CEMS 177/177; MCD64A1 2.992 granula.
- GitHub difetch; commit tim `cd1b892` sudah ada di basis lokal.
- Baseline crawler sebelumnya dikomit `0afc14d`; branch refactor dibuat.
- Baseline test: `test_derived.py` 16, `test_postprocess.py` 17, `test_static.py` 27, `test_training.py` 15 (semua OK); `smoke_static.py` lulus; `verify_params.py` 60 OK.
- Jangan sentuh atau stage pekerjaan EDA lokal yang belum dilacak kecuali referensi path terbukti perlu diperbarui; audit dan pertahankan perubahannya.

## Target susunan

```text
APIKAH/
├── AGENTS.md
├── data/
│   ├── hotspot_indonesia/       # data label yang tetap tracked
│   │   └── combined/            # Parquet kanonis; CSV lama setelah audit
│   ├── hotspot_raw/             # label sumber, tetap tracked
│   ├── features_raw/            # sumber crawl; di-ignore Git
│   │   ├── copernicus/{era5land/{instant,accum},cems_fire}/
│   │   ├── nasa/mcd64a1/         # HDF mentah saja untuk saat ini
│   │   └── static/{boundaries,climate_index,dem,hansen,osm,peatlands,worldcover,worldpop}/
│   ├── features_processed/      # fitur/tabular turunan; track setelah audit ukuran
│   │   ├── era5_daily/  ├── fire_daily/  ├── climate_index/
│   │   ├── static/      ├── derived/     └── training/
│   └── metadata/{manifests,logs}/
├── hotspot_crawler/
│   ├── crawl_copernicus.py, crawl_static.py, postprocess_*.py, build_*.py  # entrypoint kompatibel
│   ├── apikah_crawler/          # path, download, manifest, sumber, pengolahan
│   ├── tests/
│   └── requirements.txt
└── docs/{superpowers/specs,superpowers/plans,agent-notes,pipeline}/
```

`features_raw/` berisi input sebelum feature engineering. File `.nc`, `.hdf`, GeoTIFF, PBF dan format grid/vektor lain tetap dalam format sumber. MCD64A1 tidak diproses pada tahap ini. Tabel tabular yang diparse atau diolah memakai Parquet. NOAA raw response `.raw.txt` tetap untuk provenance; climate index table diproses menjadi Parquet dan consumer memakai Parquet. CSV hotspot gabungan lama tidak dihapus sebelum dibandingkan dengan Parquet dan semua referensinya ditemukan.

## Tahapan, tes, dan commit

### 1. Uji path dan keluaran CLI terlebih dahulu

- Tambahkan tes gagal untuk: default `data/` selalu di bawah root repo dari CWD root maupun crawler; `raw/static/processed/logs` memetakan ke kategori baru; temp root dapat diinjeksi pada tes; wrapper mempertahankan command, argumen, exit code, dan lokasi hasil yang dikonfigurasi.
- Tes menggunakan temporary directory, bukan dataset 17 GB atau kredensial nyata.
- **Commit:** `test: cover project-root data paths and cli contracts`.

### 2. Path resolver dan konfigurasi target

- Refactor `config.py` menjadi resolver root repo yang tidak bergantung pada CWD; petakan label dan empat kategori data.
- Pertahankan script entrypoint/CLI untuk `crawl_copernicus.py`, `crawl_static.py`, postprocess, builder, `verify_params.py`, `report_manifest.py`, dan `status.ps1`.
- Uji command dry-run dari root `APIKAH/` dan folder `hotspot_crawler/`; keduanya harus memilih satu root data yang sama.
- **Commit:** `refactor: anchor crawler paths to project data root`.

### 3. Unduh aman, resume, dan manifest

- Tambahkan tes lebih dahulu untuk skip berkas valid, lanjut `.part`, gagal tidak menandai sukses, atomic finalization, serta update manifest bersamaan tanpa kehilangan entri.
- Satukan hanya mekanisme yang memang sama; pertahankan adaptor request/autentikasi setiap sumber.
- Terapkan perlindungan manifest lintas proses yang kompatibel Windows; jangan mengubah laju/paralelisme default tanpa bukti.
- **Commit:** `refactor: harden shared download and manifest handling`.

### 4. Bentuk package tanpa mematahkan CLI

- Pindahkan implementasi inti secara bertahap ke `hotspot_crawler/apikah_crawler/` dengan modul ringkas: `paths`, `downloads`, `manifests`, `sources`, dan `processing`.
- Entrypoint lama menjadi wrapper tipis bernama sama; jangan pecah fungsi menjadi banyak file kecil.
- Setiap pemindahan module didahului tes import/CLI dan diikuti seluruh baseline test.
- **Commit terpisah per concern:** mis. `refactor: separate source clients`, `refactor: organize feature processors`.

### 5. Pindah file data secara lokal dan terverifikasi

- Buat dry-run/inventory pemetaan file lama: nested `data/raw`, `data/static`, `data/processed`, `data/logs`, dan manifest ke root `APIKAH/data/`.
- Jangan menjalankan crawler selama migrasi. Salin dulu; verifikasi count, ukuran, dan SHA-256 sebelum menghapus sumber lama. Pastikan tidak ada berkas `.part` atau nama bentrok.
- Pindahkan monthly hotspot tetap di kategorinya; pindahkan combined hotspot ke `data/hotspot_indonesia/combined/` tanpa mengubah tracking.
- Pastikan manifest/report/status dapat melihat data baru; data mentah tidak masuk staging Git.
- **Commit kode/tool migrasi terpisah dari file dataset:** `feat: add verified local data migration`; dataset ignored tidak ikut commit.

### 6. Parquet untuk tabel

- Tambahkan tes round-trip yang membandingkan nama/tipe kolom, jumlah baris, nilai/null dan urutan bulan pada climate indices; jangan membaca data produksi untuk tes.
- Ubah hasil parse climate index dari CSV ke Parquet dan consumer untuk membaca Parquet; pertahankan raw NOAA text.
- Audit CSV hotspot gabungan: bandingkan dengan Parquet kanonis dan cari semua referensi notebook/kode. Jangan hapus sumber CSV sebelum equivalence/path audit dan keputusan aman; Parquet menjadi format utama.
- Pastikan semua hasil pipeline tabel (daily/derived/training) tetap Parquet. Jangan mengubah `.nc`, `.hdf`, raster, PBF/GeoJSON menjadi tabel rata.
- **Commit:** `feat: use parquet for tabular feature artifacts`.

### 7. Ignore rules, dokumentasi, catatan agent

- Perbarui `.gitignore` agar raw crawl dan log runtime di path baru diabaikan, tetapi label tetap tracked dan processed tidak ter-ignore menyeluruh.
- Audit ukuran setiap keluaran processed sebelum stage; tolak berkas >100 MB dan jangan stage bulk output. Manifest/data catalog kecil tetap tracked.
- Satukan petunjuk `PIPELINE_DEV.md`, buat pointer dari README, pindahkan handoff APIKAH ke `docs/agent-notes/`, dan tambahkan `AGENTS.md` root yang ringkas.
- Update hanya notebook/test yang terbukti memakai path lama setelah inspeksi; simpan perubahan lain milik user.
- **Commit terpisah:** `docs: organize crawler operating notes` lalu `chore: scope gitignore to crawler data`.

### 8. Verifikasi akhir dan bukti

- Jalankan semua skrip test standalone dan smoke; `verify_params.py`; CLI dry-run dari dua CWD; report manifest; tes path; cek round-trip Parquet.
- Pastikan count/ukuran/checksum data sebelum dan sesudah migrasi sama, tidak ada crawler aktif/partial, data mentah di-ignore, label tetap tracked, dan processed yang stage masih memenuhi batas ukuran.
- Ukur konsumsi waktu/RAM hanya pada transformasi representatif; jangan klaim percepatan jaringan dari refactor.
- **Commit akhir** hanya untuk test/docs kecil yang tersisa; jangan push atau merge tanpa instruksi.

## Berkas utama yang diperkirakan terdampak

- Crawler: `config.py`, `common.py`, `crawl_copernicus.py`, `crawl_static.py`.
- Pipeline: `postprocess_era5.py`, `postprocess_fire.py`, `build_static_features.py`, `build_derived_features.py`, `build_training_table.py`, `report_manifest.py`, `preflight.py`, `verify_params.py`, `status.ps1`.
- Tes, `.gitignore`, README/`PIPELINE_DEV.md`, `AGENTS.md`, dokumentasi dan referensi path notebook.
- Semua file lokal/EDA yang tidak berkaitan dipertahankan dan tidak di-stage otomatis.

## Risiko yang harus ditahan

- Path lama di notebook/script dapat memicu data hilang atau unduhan ulang bila migrasi sebagian.
- Mengubah CSV tanpa row/schema/value comparison dapat menggeser nilai atau null.
- Atomic manifest replace tanpa lock masih bisa kehilangan update antarproses.
- Perubahan path label dapat mematahkan EDA/training; uji consumer dan pertahankan nama CLI.
- File data crawler tidak bisa dikomit sebagai bagian dari log refactor; commit hanya kode, tes, konfigurasi, dan metadata kecil.

# Handoff terkini — APIKAH

Diperbarui 2026-10-31.

## Data dan pipeline

- Crawl selesai: ERA5-Land 177 bulan × instant/accum (354/354 kunci), CEMS Fire 177/177; tidak ada crawler aktif saat verifikasi.
- Data utama di `data/`; crawler sources ada di `features_raw/` (lokal, ignored); keluaran fitur tabular ada di `features_processed/`; manifest di `metadata/manifests/`.
- Climate index NOAA sekarang dibaca sebagai Parquet; sumber `.raw.txt` disimpan untuk provenance.
- MCD64A1 sudah diunduh tetapi sementara hanya raw HDF; jangan menganggapnya sudah menjadi fitur.
- Label bulanan tetap di `hotspot_indonesia/` dan `hotspot_raw/`; tabel gabungan ada di `hotspot_indonesia/combined/`.

## Kode dan verifikasi

- Implementasi di `hotspot_crawler/apikah_crawler/`; wrapper CLI bernama lama di `hotspot_crawler/`.
- Tes custom dijalankan sebagai `python -m tests.test_*`; tes `unittest` dijalankan melalui `python -m unittest tests.<module>`.
- Baseline sebelum refactor: 75 tes lama lulus, smoke statis lulus, parameter check 60 OK. Tes path, migrasi, Parquet, CLI, dan manifest concurrency ditambahkan pada branch refactor.
- Hindari klaim percepatan unduh jaringan; perubahan efisiensi yang diukur saat ini adalah path, penyimpanan, resume/manifest dan format tabular.

## Git dan branch

- Branch kerja: `refactor/crawler-data-layout`.
- Commit awal crawler `0afc14d` dan dokumen desain/rencana berada pada branch ini. Perubahan team `cd1b892` sudah diambil dari remote sebelum branching.
- Setiap perubahan bermakna di-commit; jangan push/merge tanpa instruksi.
- EDA lokal yang tidak terkait (`eda_awal.ipynb`, `tests/`, `.opencode/`) dipertahankan dan tidak boleh di-stage massal.

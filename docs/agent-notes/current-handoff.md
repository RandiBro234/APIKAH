# Handoff terkini — APIKAH

Diperbarui 2026-10-31, setelah verifikasi akhir refactor.

## Data dan pipeline

- Crawl selesai: ERA5-Land 177 bulan × instant/accum (354/354 kunci), CEMS Fire 177/177; tidak ada crawler aktif saat verifikasi.
- Seluruh data kini ada di `data/`; crawler sources di `features_raw/` (lokal, ignored), keluaran tabular di `features_processed/`, manifest di `metadata/manifests/`, log runtime di `metadata/logs/` (ignored). Salinan nested lama sudah dihapus setelah 4.179 file disalin dan SHA-256 diverifikasi; NOAA raw text dipertahankan.
- Climate index NOAA sekarang dibaca sebagai Parquet; sumber `.raw.txt` disimpan untuk provenance.
- Audit jumlah baris menunjukkan CSV hotspot legacy hanya 1.048.575 baris, sedangkan Parquet memuat 3.941.038. Keduanya **tidak setara**; CSV lama tetap tracked untuk kompatibilitas/historis, tetapi jangan digunakan sebagai tabel lengkap. Parquet adalah tabel kanonis.
- `features_processed/` memiliki sembilan file total: dua climate-index Parquet kecil tracked; tujuh keluaran lama untuk dua bulan (~81.8 MB, file terbesar 16.2 MB) tetap lokal/untracked karena hanya sampel parsial dan lisensi redistribusi belum diaudit. Hasil pipeline lengkap 2012–2026 belum dibangun.
- MCD64A1 sudah diunduh tetapi sementara hanya raw HDF; tidak ada processor/fitur. Job crawl-nya mengunci direktori dan melewati dataset lengkap.
- Label bulanan tetap di `hotspot_indonesia/` dan `hotspot_raw/`; tabel gabungan ada di `hotspot_indonesia/combined/`.

## Kode dan verifikasi

- Implementasi di `hotspot_crawler/apikah_crawler/`; wrapper CLI bernama lama di `hotspot_crawler/`.
- Unduhan static, ERA5/CEMS, climate-index output, dan MCD64A1 memakai lock per-target/dataset di `metadata/locks/`; manifest read-modify-write juga dikunci lintas proses.
- HTTP `.part` resume memakai sidecar URL-hash + ETag/Last-Modified/total length, `If-Range`, dan validasi `Content-Range`; jika tidak tervalidasi atau berukuran nol, unduhan dimulai ulang agar representasi berbeda tidak tercampur.
- Tes custom dijalankan sebagai `python -m tests.test_*`; tes `unittest` dijalankan melalui `python -m unittest tests.<module>`.
- Verifikasi akhir 2026-10-31: 83 tes custom + 29 tes unittest lulus; tes EDA notebook 2/2; `smoke_static.py` lulus; `verify_params.py` 60 OK/0 WARN/0 FAIL; `compileall` lulus; report manifest lengkap dan tidak ada `.part`.
- Hindari klaim percepatan unduh jaringan; perubahan efisiensi yang diukur saat ini adalah path, penyimpanan, resume/manifest dan format tabular.

## Git dan branch

- Branch kerja: `refactor/crawler-data-layout`.
- Remote commit tim `cd1b892` sudah diambil. Branch ini memuat baseline `0afc14d` dan commit refactor bertahap; lihat `git log`. Belum ada push/merge.
- Setiap perubahan bermakna di-commit; jangan push/merge tanpa instruksi.
- EDA lokal yang tidak terkait (`eda_awal.ipynb`, `tests/`, `.opencode/`) dipertahankan dan tidak boleh di-stage massal.

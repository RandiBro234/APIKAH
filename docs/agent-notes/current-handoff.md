# Handoff terkini — APIKAH

Diperbarui 2026-10-31, setelah verifikasi akhir refactor.

## Data dan pipeline

- Crawl selesai: ERA5-Land 177 bulan × instant/accum (354/354 kunci), CEMS Fire 177/177; tidak ada crawler aktif saat verifikasi.
- Seluruh data kini ada di `data/`; crawler sources di `features_raw/` (lokal, ignored), keluaran tabular di `features_processed/`, manifest di `metadata/manifests/`, log runtime di `metadata/logs/` (ignored). Salinan nested lama sudah dihapus setelah 4.179 file disalin dan SHA-256 diverifikasi; NOAA raw text dipertahankan.
- Climate index NOAA sekarang dibaca sebagai Parquet; sumber `.raw.txt` disimpan untuk provenance.
- Audit jumlah baris menunjukkan CSV hotspot legacy hanya 1.048.575 baris, sedangkan Parquet memuat 3.941.038. Keduanya **tidak setara**; CSV lama tetap tracked untuk kompatibilitas/historis, tetapi jangan digunakan sebagai tabel lengkap. Parquet adalah tabel kanonis.
- `features_processed/` memiliki sembilan file: dua climate-index Parquet kecil dan tujuh keluaran dua bulan (2023-07/08, ~81,8 MB) — semuanya **tracked** dengan atribusi Copernicus di `data/NOTICE.md`.
- Data mentah tidak masuk Git (16,91 GB, 4.135 berkas, 14 file >100 MB). Untuk dibagikan, tersedia `data/MANIFEST_raw.csv` + `python verify_data.py`; semua 4.135 berkas sudah diverifikasi cocok pada 2026-11-01.
- Hasil pipeline lengkap 2012-2026 belum dibangun; yang ada baru contoh dua bulan.
- MCD64A1 sudah diunduh tetapi sementara hanya raw HDF; tidak ada processor/fitur. Job crawl-nya mengunci direktori dan hanya skip bila fingerprint query serta semua nama granula HDF cocok.
- Label bulanan tetap di `hotspot_indonesia/` dan `hotspot_raw/`; tabel gabungan ada di `hotspot_indonesia/combined/`.

## Kode dan verifikasi

- Implementasi di `hotspot_crawler/apikah_crawler/`; wrapper CLI bernama lama di `hotspot_crawler/`.
- Unduhan static, ERA5/CEMS, climate-index output, dan MCD64A1 memakai lock per-target/dataset di `metadata/locks/`; manifest read-modify-write juga dikunci lintas proses.
- HTTP `.part` resume memakai sidecar URL-hash + ETag/Last-Modified/total length, `If-Range`, dan validasi `Content-Range`; jika tidak tervalidasi atau berukuran nol, unduhan dimulai ulang agar representasi berbeda tidak tercampur.
- Tes custom dijalankan sebagai `python -m tests.test_*`; tes `unittest` dijalankan melalui `python -m unittest tests.<module>`.
- Review: 4 putaran reviewer read-only independen; temuan (race migrasi, target ganda, resume tanpa validasi, partial kosong, skip MCD berbasis jumlah) sudah diperbaiki + regression test. Commit ignore/identitas MCD terakhir direview in-session; tidak ada temuan critical/important.
- Verifikasi akhir 2026-11-01 pada HEAD `276e13d`: 83 tes custom + 33 tes unittest lulus; tes EDA notebook 2/2; `smoke_static.py` LULUS; `verify_params.py` 60 OK/0 WARN/0 FAIL; `compileall` bersih; manifest ERA5 354/354 + CEMS 177/177; tidak ada `.part`; 0 file `features_raw` dan 0 log/lock ter-track.
- Hindari klaim percepatan unduh jaringan; perubahan efisiensi yang diukur saat ini adalah path, penyimpanan, resume/manifest dan format tabular.

## Git dan branch

- Branch kerja: `refactor/crawler-data-layout`.
- Remote commit tim `cd1b892` sudah diambil. Branch ini memuat baseline `0afc14d` dan commit refactor bertahap; lihat `git log`. Belum ada push/merge.
- Setiap perubahan bermakna di-commit; jangan push/merge tanpa instruksi.
- EDA lokal yang tidak terkait (`eda_awal.ipynb`, `tests/`, `.opencode/`) dipertahankan dan tidak boleh di-stage massal.

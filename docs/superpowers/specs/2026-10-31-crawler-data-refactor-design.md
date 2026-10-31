# Desain: Refactor crawler dan tata letak data APIKAH

**Status:** disetujui pengguna 2026-10-31; implementasi berjalan di branch `refactor/crawler-data-layout`.

## Maksud dan alasan

Crawler APIKAH telah menyelesaikan pengambilan data 2012-01–2026-09. Kode, keluaran crawler, label hotspot, hasil olahan, dan catatan operasional kini tersebar di beberapa lokasi. Path keluaran crawler bergantung pada current working directory (CWD), sehingga menjalankan perintah dari folder yang berbeda berisiko membuat data tersebar atau memicu unduhan ulang.

Refactor bertujuan membuat struktur mudah dipahami dan dirawat, mengurangi kode berulang tanpa membuatnya samar, serta memastikan semua data tetap berada di dalam project `APIKAH/` pada satu direktori `data/` yang terkelompok berdasarkan fungsi.

## Tujuan

1. Satukan semua data di `APIKAH/data/` tanpa mencampur data dengan kode.
2. Pertahankan label hotspot yang sudah ada dan tetap tracked di Git.
3. Simpan sumber mentah crawler di `features_raw/`; jangan masukkan file data mentah besar ke Git.
4. Simpan hasil olahan di `features_processed/`; track hanya setelah ukuran dan dampaknya terhadap repo diperiksa. File tunggal di atas batas GitHub 100 MB tidak di-track.
5. Buat path default berakar pada lokasi project, bukan CWD, agar perintah bekerja konsisten dari lokasi mana pun.
6. Sederhanakan kode dengan helper bersama untuk unduhan, retry/resume, validasi hasil, logging, dan manifest; pisahkan logika khusus sumber data dari mekanisme umum.
7. Jaga penggunaan memori tetap rendah ketika mengolah NetCDF/raster; gunakan pemotongan area/chunk saat sesuai.
8. Pertahankan nama perintah CLI, opsi, perilaku skip/resume, rentang data, parameter request, dan skema keluaran yang sudah dipakai.
9. Rapikan dokumentasi pipeline, plan, dan catatan agent; setiap perubahan bermakna memiliki commit tersendiri.

## Bukan tujuan

- Tidak mengubah definisi fitur, rentang waktu, area Indonesia, parameter request, ataupun hasil analisis.
- Tidak mengunduh ulang data yang sudah ada.
- Tidak meratakan grid/raster atau sumber spasial (`.nc`, `.hdf`, `.tif`, `.pbf`, GeoJSON, dan sejenisnya) menjadi CSV/Parquet. Format sumber tersebut dipertahankan; Parquet digunakan untuk data tabular.
- Tidak menambah layanan penyimpanan eksternal atau mewajibkan Git LFS.
- Tidak memasukkan kredensial, log runtime, cache, atau keseluruhan dataset mentah ke Git.
- Tidak mengubah atau menghapus pekerjaan EDA lokal yang tidak terkait.

## Keputusan pengguna

- Branch refactor: `refactor/crawler-data-layout` (sudah dibuat dari baseline lokal terbaru).
- Semua data berada dalam project `APIKAH/`, dengan root tunggal `data/`.
- Data hotspot yang sudah ada tetap tracked dan tetap menjadi input label.
- `features_raw/` berarti sumber fitur yang sama sekali belum diproses, termasuk seluruh unduhan crawler.
- `features_processed/` berisi keluaran transformasi/fitur siap analisis atau model.
- Data mentah crawler dikecualikan dari Git. Data processed boleh di-track jika ukurannya wajar setelah audit; file besar dikecualikan.
- Format sumber mentah non-tabular dipertahankan; tabel tabular/hasil olahan memakai Parquet. Snapshot teks sumber tetap dijaga untuk provenance, dan salinan CSV lama tidak dihapus sebelum konsumen serta kesetaraan datanya diverifikasi.
- MCD64A1 sementara hanya disimpan sebagai data mentah; pemrosesan burned-area bukan bagian refactor ini.
- Audit CSV/Parquet gabungan: CSV legacy 1.048.575 baris vs Parquet 3.941.038; hasil tidak setara. CSV dipertahankan tracked sebagai legacy, Parquet kanonis untuk analisis.
- Tujuh hasil processed lama (~81.8 MB, hanya dua bulan) tetap lokal dan tidak di-track karena parsial dan lisensi redistribusi belum diverifikasi.
- Perintah CLI serta skema hasil dipertahankan.
- Tidak ada pekerjaan refactor yang dimulai sebelum crawl selesai; kondisi crawl sudah diverifikasi lengkap pada 2026-10-31.

## Target struktur data

```text
APIKAH/
├── data/
│   ├── hotspot_indonesia/       # label area studi; tetap tracked
│   │   └── combined/            # Parquet kanonis + CSV legacy terpotong
│   ├── hotspot_raw/             # label sumber; tetap tracked
│   ├── features_raw/
│   │   ├── copernicus/
│   │   │   ├── era5land/instant/
│   │   │   ├── era5land/accum/
│   │   │   └── cems_fire/
│   │   ├── nasa/mcd64a1/
│   │   └── static/
│   │       ├── boundaries/  ├── climate_index/  ├── dem/
│   │       ├── hansen/      ├── osm/            ├── peatlands/
│   │       ├── worldcover/  └── worldpop/
│   ├── features_processed/
│   │   ├── era5_daily/
│   │   ├── fire_daily/
│   │   ├── static/
│   │   ├── climate_index/
│   │   ├── derived/
│   │   └── training/
│   └── metadata/
│       ├── manifests/
│       ├── logs/             # runtime; tidak di-track
│       └── data-catalog.md
├── hotspot_crawler/
│   ├── crawl_copernicus.py   # wrapper CLI, nama/argumen tetap
│   ├── crawl_static.py       # wrapper CLI
│   ├── postprocess_*.py      # wrapper CLI
│   ├── build_*.py            # wrapper CLI
│   ├── apikah_crawler/       # implementasi internal terorganisasi
│   │   ├── paths.py
│   │   ├── downloads.py
│   │   ├── manifests.py
│   │   ├── sources/
│   │   └── processing/
│   └── tests/
├── docs/
│   ├── superpowers/specs/    # desain yang disetujui
│   ├── superpowers/plans/    # rencana implementasi
│   ├── agent-notes/          # handoff/catatan project
│   └── pipeline/             # petunjuk penggunaan dan pipeline
└── AGENTS.md                 # instruksi singkat + tautan ke docs
```

Struktur internal package/file dapat disederhanakan atau disesuaikan setelah audit import dan test; pohon di atas menetapkan pemisahan tanggung jawab, bukan memaksa satu file untuk setiap fungsi.

## Target struktur kode dan perilaku

- Sediakan wrapper bernama sama untuk perintah yang sudah ada (`crawl_copernicus.py`, `crawl_static.py`, postprocess/build scripts), lalu pindahkan implementasi inti ke package `apikah_crawler`.
- `paths.py` menentukan root project dan pemetaan path data; tes boleh mengarahkan root sementara tanpa menyentuh dataset produksi.
- `downloads.py` menangani helper umum yang memang sama: retry/backoff, file sementara/atomik, validasi hasil, dan mekanisme resume yang sesuai kemampuan endpoint. Klien Copernicus/Earthdata/HTTP tetap mempertahankan detail autentikasi dan request masing-masing.
- `manifests.py` menjaga pembaruan metadata aman untuk beberapa proses. Pilih file lock lintas proses atau manifest per worker setelah mengevaluasi kompatibilitas Windows dan kebutuhan merge; atomic replace saja belum mencegah lost update.
- Batas paralelisme tetap terukur dan tidak dinaikkan sebagai bagian refactor tanpa hasil uji serta persetujuan; satu bulan/file tidak boleh diunduh oleh dua worker.
- Pengolahan raster/NetCDF tetap berbatas area atau chunk bila memungkinkan; hindari memuat raster nasional penuh ke RAM.
- Tidak menambah dependency wajib tanpa alasan. Standarisasi satu cara menjalankan test tanpa mengasumsikan pytest terpasang; baseline saat ini memakai skrip test standalone.
- Produk tabular persisten (indeks iklim terparse, tabel harian/turunan/training) menggunakan Parquet. Untuk NOAA, pertahankan response mentah `.raw.txt` sebagai provenance dan tulis tabel terparse sebagai Parquet; CSV lama hanya dipertahankan sementara bila dibutuhkan kompatibilitas.
- Parquet tidak digunakan untuk mengganti file grid/raster/vektor mentah. MCD64A1 tetap HDF mentah tanpa processor baru pada lingkup ini.

## Pemindahan data dan kebijakan Git

Pemetaan awal dari `hotspot_crawler/hotspot_crawler/data/`:

- `raw/era5land` dan `raw/cems_fire` → `data/features_raw/copernicus/`.
- `static/mcd64a1` → `data/features_raw/nasa/mcd64a1/`.
- lapisan lain di `static/` → `data/features_raw/static/`.
- `processed/` → kategori yang sesuai di `data/features_processed/`.
- tabel indeks iklim → Parquet; response sumber teks tetap dipertahankan.
- manifest → `data/metadata/manifests/`; log runtime → `data/metadata/logs/`.
- Berkas bulanan di `data/hotspot_indonesia/` dan `data/hotspot_raw/` tetap di kategorinya dan tracked. CSV/Parquet gabungan yang sekarang berada langsung di root `data/` dipindah ke `data/hotspot_indonesia/combined/`; tetap tracked, dan seluruh referensi path diperbarui.

Pemindahan data lokal dilakukan setelah kode menunjuk ke lokasi baru: salin/migrasikan tanpa konversi, bandingkan jumlah file dan ukuran, verifikasi checksum pada data crawler, pastikan manifest/status dapat membaca lokasi baru, baru hapus sumber lama. Data besar tidak dimasukkan ke staging Git. `.gitignore` dibuat spesifik untuk `features_raw/` dan log/temporary; jangan gunakan aturan luas yang menyembunyikan label tracked atau otomatis menambahkan semua processed.

## Dokumentasi dan catatan agent

- Satukan petunjuk pipeline yang sekarang ada di README/`PIPELINE_DEV.md` root dan folder crawler ke `docs/pipeline/` dengan tautan/pointer dari lokasi lama bila dibutuhkan.
- Simpan plan/desain pada `docs/superpowers/specs/` dan rencana langkah pada `docs/superpowers/plans/`.
- Pindahkan/catat hanya handoff APIKAH yang relevan ke `docs/agent-notes/`; jangan mencampur atau menghapus catatan EDA yang tidak terkait.
- Buat `AGENTS.md` di root repo yang singkat: aturan data besar, cara menjalankan tes, larangan membaca/commit data mentah, dan rujukan ke docs.

## Tahapan implementasi yang diusulkan

1. Audit diff lokal, entrypoint, referensi path, ignore rules, lisensi/metadata sumber, ukuran keluaran processed, serta baseline test. Pertahankan notebook/test/catatan EDA lokal yang tidak terkait.
2. Buat/standarkan tes untuk path resolution, CLI compatibility, skip/resume, unduhan parsial, manifest concurrent update, dan pemetaan output; semua test memakai temporary directories.
3. Implementasikan root/path mapping dan manifest/download behavior; pertahankan wrapper CLI dan uji jalankan dari root repo serta folder crawler.
4. Pindahkan data mentah dan keluaran processed dengan verifikasi file count/size/checksum; pastikan `data/` tidak menambah dataset mentah ke Git.
5. Refactor internal modul secara bertahap, satu concern per commit; jangan melakukan rewrite besar tanpa tes.
6. Standarkan tabel tabular ke Parquet dengan uji jumlah baris/schema/nilai; pertahankan sumber CSV/TXT mentah dan jangan hapus salinan lama sebelum verifikasi kesetaraan serta audit referensi.
7. Rapikan `.gitignore`, test organization, docs, plan, agent notes, dan notebook/test references yang memang mengarah ke path lama.
8. Verifikasi akhir: semua standalone/regression tests, `verify_params.py`, dry-run dari dua working directory, manifest report, smoke test sintetis, status path, file count/size/checksum, dan `git status`/diff untuk memastikan tidak ada data mentah di staging.

Setiap tahap bermakna mendapat commit terpisah pada branch refactor. Tidak ada push/merge ke `main` tanpa instruksi pengguna.

## Batasan dan risiko

- Baseline crawl 2026-10-31: 177 bulan ERA5 instant + 177 accum; 177 bulan CEMS Fire; 2.992 granula MCD64A1; 81 tile WorldCover; crawler lengkap, tanpa `.part`.
- Baseline tes: skrip standalone `test_derived.py` (16), `test_postprocess.py` (17), `test_static.py` (27), `test_training.py` (15) semuanya lulus; `smoke_static.py` lulus; `verify_params.py` 60 OK/0 WARN/0 FAIL. `pytest` tidak tersedia dan `unittest discover` belum menjadi runner yang cocok.
- Remote `origin/main` difetch; commit tim `cd1b892` sudah diambil. Baseline perubahan crawler sebelumnya dicatat di commit `0afc14d`; branch refactor saat ini berada di atas commit itu.
- `data/features_raw` berisi sekitar 17 GB. Penyalinan memerlukan waktu dan ruang, walau ruang disk bebas terakhir sekitar 105 GB.
- Risiko utama: path lama di notebook/test/docs, file tersalin dua kali atau terunduh ulang jika migrasi tidak lengkap, aturan ignore menyembunyikan label atau memasukkan data besar, dan race manifest saat proses paralel.
- Repo memuat data GADM yang sudah tercatat punya batas redistribusi; jangan menambahkan atau memindahkan salinan GADM baru ke Git.

## Status implementasi (2026-10-31)

- Sudah dilakukan: remote tim di-fetch, baseline crawler dikomit, branch dibuat; root data dipusatkan ke `APIKAH/data/`; data mentah disalin dan diverifikasi SHA-256 sebelum salinan lama dihapus; label gabungan dipindah tanpa mengubah tracking.
- Sudah dilakukan: package `apikah_crawler`, wrapper CLI kompatibel, pemisahan tests/docs, Parquet untuk climate-index, manifest lock lintas proses, `.gitignore` spesifik, AGENTS/docs/agent-notes.
- MCD64A1 tetap raw-only seperti keputusan pengguna.
- Audit CSV/Parquet menemukan jumlah baris berbeda (lihat keputusan di atas); keluaran processed parsial ditahan lokal dan tidak distage. Notebook aktif memakai Parquet.
- Push/merge belum dilakukan.

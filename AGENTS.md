# Panduan agent untuk repo APIKAH

- Baca `docs/pipeline/README.md` untuk perintah dan lokasi aktif, `docs/agent-notes/README.md` untuk konteks, dan desain/rencana di `docs/superpowers/` sebelum mengubah pipeline.
- Kode crawler ada di `hotspot_crawler/apikah_crawler/`; perintah kompatibel ada sebagai wrapper di `hotspot_crawler/`.
- Semua data berada di `data/`: label di `hotspot_indonesia/` dan `hotspot_raw/`, input mentah crawler di `features_raw/`, keluaran olahan di `features_processed/`, metadata di `metadata/`.
- Jangan membuka atau memasukkan isi dataset besar (`.nc`, `.hdf`, `.tif`, `.pbf`, Parquet) ke konteks. Gunakan ringkasan/profil atau skrip Python yang hanya mengeluarkan statistik.
- Jangan commit `data/features_raw/`, `data/metadata/logs/`, atau `data/metadata/locks/`. Periksa ukuran dan lisensi satu per satu sebelum menambahkan hasil ke `features_processed/`; jangan gunakan `git add -A`.
- Pertahankan data hotspot yang sudah tracked. Jangan menambah berkas GADM baru ke repo publik.
- Jalankan tes dari `hotspot_crawler/`; format perintah ada di dokumentasi pipeline. Setiap perubahan bermakna mendapat commit tersendiri dan tidak di-push tanpa instruksi.

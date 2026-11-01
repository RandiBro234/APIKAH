# Pipeline development notes

Panduan operasional terbaru pindah ke [`docs/pipeline/README.md`](docs/pipeline/README.md).

Dokumen historis lengkap (status per Oktober 2026, limitasi layanan, konvensi tile,
kontrak data, dan daftar TODO) ada di
[`docs/agent-notes/archive/PIPELINE_DEV_history.md`](docs/agent-notes/archive/PIPELINE_DEV_history.md).

Sebagian isi di arsip itu sudah usang setelah refactor:

| Topik | Kondisi sekarang |
|---|---|
| Lokasi kode | `hotspot_crawler/apikah_crawler/`, wrapper CLI di `hotspot_crawler/` |
| Lokasi data | satu root `data/` (`features_raw`, `features_processed`, `metadata`) |
| Path default | mengikuti lokasi project, bukan CWD |
| Indeks iklim | `data/features_processed/climate_index/*.parquet` |
| Lock | per-target di `data/metadata/locks/`, manifest dikunci lintas proses |
| Raw data | tidak di Git; arsip Drive + `README_data_mentah.txt` |

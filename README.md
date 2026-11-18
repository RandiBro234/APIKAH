# Proyek APIKAH: Prediksi Risiko Hotspot Karhutla di Indonesia Berbasis Data Satelit dan Fitur Cuaca

Proyek **APIKAH** (*Analisis dan Prediksi Indeks Risiko Karhutla Terpadu*) berfokus pada pembangunan sistem prediksi risiko kemunculan titik panas (*hotspot*) karhutla di Indonesia (1-3 hari ke depan) pada petak grid 0.25 derajat dengan mengintegrasikan data satelit penginderaan jauh (VIIRS SNPP dan NOAA-20) serta variabel meteorologi/cuaca ERA5.

---

## Struktur Direktori

```text
APIKAH_PROJECT/
├── dataset_apikah/
│   ├── data hotspot_indonesia/     # Data historis titik panas satelit VIIRS per bulan (Parquet)
│   ├── data training_iklim/        # Data grid cuaca & target per bulan (Parquet)
│   ├── data train_val_test/        # Dataset hasil preprocessing siap modeling (Format CSV & JSON)
│   │   ├── train_preprocessed.csv
│   │   ├── val_preprocessed.csv
│   │   ├── test_preprocessed.csv
│   │   └── feature_metadata.json
│   ├── sample_dataset_utama.csv    # Sampel 1.000 baris dataset utama untuk verifikasi cepat
│   ├── merge_dataset.py            # Skrip reproduktif penggabungan data satelit dan cuaca
│   └── dataset_utama_apikah.csv    # Dataset master terpadu (7.22 GB, 22.4M baris - disimpan lokal)
├── eda_apikah/
│   ├── eda_apikah_new.ipynb        # Notebook EDA terpadu (11 Step Analisis & Visualisasi Lengkap)
│   └── plots/                      # Berkas gambar visualisasi resolusi tinggi (PNG)
│       ├── karakteristik_sensor_satelit.png
│       ├── distribusi_fitur_kunci.png
│       ├── heatmap_korelasi.png
│       ├── peta_spasial_hotspot.png
│       ├── peringkat_provinsi_hotspot.png
│       └── tren_musiman_tahunan.png
├── prepro_apikah/
│   └── prepro_apikah_new.ipynb     # Notebook Preprocessing (9 Step Prapemrosesan Siap Modeling)
├── .gitignore                      # Konfigurasi pengabaian file berukuran besar (>100MB)
└── README.md                       # Dokumentasi resmi proyek
```

---

## Ringkasan Metodologi

1. **Target Prediksi:**
   - Target Utama: `ada_api` (Klasifikasi biner: 0 = tidak ada kebakaran, 1 = ada kebakaran di petak grid).
   - Target Multi-Horizon: `target_lead1` (H+1), `target_lead2` (H+2), `target_lead3` (H+3).
   - Target Tingkat Risiko (FDR): `risk_class` (0 = Low, 1 = Moderate, 2 = High, 3 = Extreme).

2. **Fitur Prediktor Terpilih (Variabel X):**
   - Fitur Cuaca & Kekeringan: Suhu 2m (`t2m_mean`, `t2m_max`), kelembaban (`rh_mean`, `rh_min`), defisit tekanan uap (`vpd_max`), kecepatan angin (`wind_max`), lengas tanah (`swvl1_mean`), curah hujan harian (`precip_mm`), indeks kekeringan (`fwi`, `dc`, `dmc`, `kbdi`), dan akumulasi hujan (`hujan_7h`, `hujan_30h`).
   - Fitur Spasio-Temporal: `lat_c`, `lon_c`, `bulan`, `hari_dalam_tahun`.
   - Riwayat Kebakaran: Lag hotspot 1-3 hari sebelumnya (`hotspot_lag1`, `hotspot_lag2`, `hotspot_lag3`).
   - Interaksi Fisik: `fwi_vpd_interaction`, `is_dry_day`.

3. **Pembersihan Data Leakage:**
   - Seluruh variabel fisik satelit pada hari yang sama (`frp`, `bright_ti4`, `confidence`, `daynight`, `satellite`, dll.) dieliminasi dari prediktor X untuk mencegah kebocoran informasi masa depan.
   - Sumber panas industri stasioner (*permanent flare* kilang migas/smelter) disaring keluar.

4. **Pembagian Data:**
   - *Temporal Split* (70% Train, 15% Validation, 15% Test) tanpa pengacakan acak untuk mencegah kebocoran korelasi waktu.

---

## Catatan Dataset Skala Besar

Berkas dataset utama `dataset_utama_apikah.csv` berukuran 7.22 GB (22.411.062 baris) dan `train_preprocessed.csv` berukuran 145 MB melebihi batas unggah langsung GitHub (100 MB per berkas). Kedua berkas dikecualikan dari Git melalui `.gitignore` untuk mencegah penolakan push. Untuk menjalankan eksperimen cepat, berkas sampel `dataset_apikah/sample_dataset_utama.csv` disediakan di dalam repositori.

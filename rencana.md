# Rencana pengembangan — mock up HOTSPOT.ID

Dokumen kerja untuk sisa pekerjaan setelah M1–M4. Isinya keputusan yang sudah
disepakati, yang ditunda, dan alasannya.

Status terakhir: M1–M4 selesai di kode (lolos `tsc -b`), belum diverifikasi
secara visual karena sandbox tidak bisa membuka browser.

---

## Yang sudah selesai

| Tahap | Isi | Status |
|---|---|---|
| M1 | Fondasi peta, panel detail, legenda | selesai |
| M2 | Data ADM2 (519 kabupaten/kota) + agregasi risiko per kabupaten | selesai |
| M3 | Layer kabupaten di peta (zoom 4–5,5), hover, klik, kartu ikhtisar | selesai |
| M4 | Tab Wilayah bisa ditelusuri provinsi → kabupaten | selesai |

### Keputusan yang sudah diambil

- **Zoom bertingkat**: provinsi < 4 · kabupaten 4–5,5 · sel grid ≥ 5,5.
  Kabupaten sengaja hanya muncul di pita zoom itu agar tidak menumpuk.
- **Angka kabupaten adalah agregasi sel**, bukan prediksi resolusi lebih halus.
  Ini disebutkan di kartu dan di tab Wilayah supaya tidak menyesatkan.
- **Data contoh ditandai eksplisit.** Angka kabupaten berasal dari fixture
  (`is_mock: true`) dan diberi label "ANGKA KABUPATEN MASIH DATA CONTOH" di
  header daftar kabupaten. Label hilang sendiri bila `is_mock` jadi `false`.
- **Wilayah tanpa data diwarnai warna daratan**, bukan warna "risiko rendah",
  agar tidak terbaca sebagai "aman".

---

## M5 — Hotspot aktual (belum dikerjakan)

Rencana yang disepakati:

- **Titik mentah individual**, bukan klaster. Diletakkan di zoom ≥ 5,5.
- **Dibandingkan dengan sel risiko**: titik ditumpuk di atas sel, dan kartu
  titik menyebut jarak ke pusat sel terdekat.
- **Tanggal ditampilkan apa adanya.** Data NRT di disk berhenti sekitar
  September 2026, sedangkan tanggal sistem November 2026. Tidak digeser.
  Isu "aktual sekarang" ditunda.

### Catatan penting

Rentang waktu (mingguan/bulanan) **belum diputuskan** dan tidak menghalangi
pekerjaan: skrip hanya perlu satu parameter `--days`.

---

## Pipeline pembaruan harian — RENCANA, sebagian crawler sudah dibuat

NASA FIRMS menjadi sumber hotspot aktual. Pengambilan dilakukan harian agar peta
dan fitur model memakai observasi terbaru, bukan menunggu pembaruan mingguan.

### Alur waktu WIB

```text
00:30  ambil hotspot NASA FIRMS
01:00  ambil data Copernicus ERA5-Land dan CEMS Fire
02:00  validasi input dan bangun fitur harian
03:00  jalankan prediksi H+1, H+2, dan H+7
03:30  publish output ke dashboard
```

Jika data belum lengkap, job retry tiap 30 menit sampai 05:00 WIB. Output baru
hanya dipublish jika input wajib lengkap; jika gagal, prediksi terakhir diberi
status **DATA BASI**.

### NASA FIRMS

- Sumber: `VIIRS_SNPP_NRT` dan `VIIRS_NOAA20_NRT`.
- Area: seluruh Indonesia, bbox `94,-11.5,141.5,6.5`.
- Setiap eksekusi mengambil observasi 72 jam terakhir.
- Retry request maksimal 3 kali dengan jeda bertahap.
- Output mentah:

```text
data/hotspot_indonesia/raw/
├── VIIRS_SNPP_NRT_YYYY-MM-DD.parquet
└── VIIRS_NOAA20_NRT_YYYY-MM-DD.parquet
```

Implementasi: `hotspot_crawler/apikah_crawler/nasa/firms.py`, wrapper:
`hotspot_crawler/crawl_nasa.py`.

API key tidak boleh masuk source code, notebook, dokumen, argumen CLI, atau Git.
Gunakan penyimpanan rahasia lokal yang disediakan environment.

### Copernicus

- ERA5-Land: cuaca harian per grid 0,25°.
- CEMS Fire: indeks bahaya api harian, bukan deteksi titik hotspot.
- Hasil olahan masuk `data/features_processed/copernicus/`.

### Visualisasi peta

Hotspot aktual dan prediksi harus terpisah:

- **Hotspot aktual**: titik merah dari NASA FIRMS, dengan waktu observasi,
  confidence, dan FRP. Tampilkan sebagai deteksi satelit, bukan konfirmasi
  kebakaran.
- **Risiko prediksi**: grid transparan hijau–merah untuk H+1, H+2, dan H+7.
- Sediakan toggle terpisah: `Hotspot aktual`, `Risiko prediksi`, dan `Citra satelit`.

### Modeling multi-horizon

```text
hotspot historis lag 1–3 hari
+ cuaca historis ERA5-Land
+ prakiraan cuaca masa depan
+ FWI dan fitur kekeringan
→ prediksi H+1, H+2, H+7
```

Hotspot FIRMS terbaru dipakai sebagai fitur lag dan validasi visual. Data setelah
waktu prediksi tidak boleh masuk fitur karena menyebabkan **data leakage**.
ERA5-Land adalah reanalysis historis; prediksi masa depan perlu prakiraan cuaca,
bukan ERA5-Land masa depan yang belum tersedia.

### Penjadwalan

Gunakan **Windows Task Scheduler** untuk menjalankan pipeline harian. Tidak perlu
proses server hidup; cocok untuk laptop.

### Keputusan yang ditunda

- Mekanisme publish output ke frontend.
- Format manifest harian dan aturan pemulihan saat input tidak lengkap.
- Sumber prakiraan cuaca untuk fitur H+1, H+2, dan H+7.
- Pengelompokan titik hotspot menjadi cluster; tahap awal memakai titik individual.


---

## Utang teknis yang diketahui

| Hal | Dampak |
|---|---|
| ADM1 di disk masih 34 provinsi | Belum 38 provinsi. Butuh unduhan ADM1 versi baru; `prepare_adm2.py` tidak bisa mengunduh sendiri. |
| `kabupaten.geojson` 3,8 MB | Belum diukur di browser. Bila berat, naikkan toleransi penyederhanaan dari 0,004° ke 0,008°. |
| Angka kabupaten masih fixture | Perlu diganti keluaran model nyata dari anggota tim. |
| `npm run build` gagal di sandbox | `spawn EPERM` (batas sandbox), bukan galat kode. `tsc -b` lolos. Jalankan `npm run build` di mesin sendiri. |
| Tampilan belum dilihat | Semua tahap M3–M4 belum diperiksa secara visual. |

---

## M6 — Evaluasi (belum direncanakan)

Ide yang sempat muncul: menghitung presisi/recall antara prediksi dan hotspot
aktual. Belum diputuskan ambang levelnya. Ditunda.

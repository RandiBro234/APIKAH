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

### Integrasi hasil model dengan backend FastAPI dan frontend

Model prediksi dikerjakan oleh anggota tim lain. Backend FastAPI tidak melatih
model; tugasnya menerima hasil model, menyimpan atau membacanya, lalu menyediakan
hasil yang sama kepada frontend dan layanan notifikasi.

#### Alur sederhana

```text
NASA FIRMS + data cuaca
        ↓
proses data dan model prediksi (anggota tim model)
        ↓ hasil H+1, H+2, H+7
backend FastAPI
        ├── menyediakan prediksi untuk dashboard
        └── nanti memeriksa ambang dan mengirim notifikasi Telegram
        ↓
frontend React menampilkan hasil sesuai wilayah pilihan user
```

Untuk tahap awal, kerjakan hasil **Besok (H+1)** di halaman Peringatan. H+2 dan
H+7 tetap tersedia untuk peta bila hasil model sudah siap. Frontend tidak
menghitung atau menebak risiko sendiri; frontend hanya meminta dan menampilkan
hasil dari backend.

#### Bagian yang dikerjakan tiap anggota

- **Anggota model**: menghasilkan prediksi per wilayah dan horizon, beserta
  tanggal prediksi, skor/probabilitas, level risiko, dan versi model.
- **Backend FastAPI**: menerima atau membaca hasil model, menyediakan API untuk
  frontend, dan memeriksa apakah data masih baru. Token Telegram hanya disimpan
  di backend, bukan di frontend atau Git.
- **Frontend React**: mengirim pilihan wilayah dan horizon ke API, lalu
  menampilkan hasil, waktu pembaruan, status data, serta pesan saat data belum
  tersedia atau gagal dimuat.

#### Kontrak hasil prediksi

Sebelum menghubungkan kode, sepakati satu bentuk data. Contoh berikut hanya
contoh format, bukan hasil prediksi nyata:

```json
{
  "region_id": "IDN-ADM2-0063",
  "region_name": "Bojonegoro",
  "province": "Jawa Timur",
  "horizon": "h1",
  "prediction_date": "2026-11-29",
  "risk_level": 3,
  "probability": 0.42,
  "drivers": ["curah hujan rendah", "riwayat hotspot meningkat"],
  "generated_at": "2026-11-28T03:30:00Z",
  "model_version": "v0.1"
}
```

Arti field: `region_id` adalah ID wilayah yang stabil dan sama dengan ID di
frontend; `horizon` bernilai `h1`, `h2`, atau `h7`; `risk_level` bernilai 1-4;
`probability` bernilai 0-1; `drivers` berisi alasan dari model bila tersedia;
`generated_at` adalah waktu hasil dibuat dalam UTC. `drivers` tidak wajib untuk
rilis awal. Jangan mengirim field buatan atau menampilkan nilai contoh sebagai
hasil operasional.

#### Endpoint backend yang direncanakan

- `GET /api/predictions?region_id=IDN-ADM2-0063&horizon=h1`: ambil prediksi
  satu wilayah untuk horizon yang diminta. Balas data prediksi di atas, atau
  status belum tersedia bila model belum menghasilkan data.
- `GET /api/regions`: ambil daftar ID, nama kabupaten/kota, dan provinsinya,
  bila frontend nantinya tidak lagi memakai daftar lokal.
- `GET /health`: cek apakah backend dapat dijangkau.

Endpoint pengiriman data model diperlukan hanya bila hasilnya dikirim langsung
ke FastAPI. Pilih salah satu cara bersama anggota model:

1. Backend membaca file hasil model dari lokasi yang disepakati; sederhana untuk
   prototipe di satu mesin.
2. Proses model mengirim hasil ke endpoint internal FastAPI, misalnya
   `POST /api/internal/predictions`; lindungi endpoint ini dengan autentikasi
   layanan dan jangan buka untuk publik.

Jangan membuat dua sumber hasil yang berbeda. Tetapkan satu cara dan satu format
sebelum integrasi.

#### Tampilan dan arti data di halaman Peringatan

- User memilih provinsi, lalu kabupaten/kota. Pilihan manual tetap tersedia dan
  lokasi GPS tidak diminta otomatis.
- Bagian utama menampilkan **risiko munculnya hotspot besok** dari model untuk
  wilayah pilihan, jika memang model menyediakan hasil pada tingkat tersebut.
- Tampilkan level risiko, probabilitas atau skor sesuai definisi model, tanggal
  prediksi, waktu hasil dibuat, dan versi model. Jangan menyamakan probabilitas
  dengan kepastian kebakaran.
- Jika model hanya menghasilkan prediksi tingkat provinsi atau grid, beri label
  tingkat data sebenarnya. Jangan menyebutnya prediksi kabupaten. Untuk nilai
  kabupaten hasil agregasi grid, tampilkan juga cakupan sel yang dipakai.
- Faktor risiko hanya ditampilkan bila disediakan model atau analisis yang
  disepakati. Jangan menyimpulkan penyebab dari angka hotspot saja.
- Jika prediksi belum ada, data gagal dimuat, atau sudah basi, tampilkan status
  tersebut dengan jelas. Jangan menggantinya diam-diam dengan data contoh.
- Hotspot NASA FIRMS tetap menjadi bagian **kondisi teramati**, terpisah dari
  **risiko prediksi**. Jumlah hotspot dihitung dari titik yang masuk ke geometri
  wilayah pilihan. Selalu tampilkan waktu sumber dan catatan: “Hotspot adalah
  deteksi satelit, bukan konfirmasi kebakaran.”

#### Tahapan integrasi

1. Anggota model dan backend menyepakati ID wilayah, horizon, nama field, zona
   waktu, dan cara mengirim atau membaca hasil.
2. Uji satu hasil H+1 untuk satu wilayah, lalu pastikan ID-nya cocok dengan
   pilihan di frontend.
3. Sambungkan halaman Peringatan ke `GET /api/predictions` dan buat tampilan
   memuat, berhasil, kosong, gagal, serta data basi.
4. Cocokkan angka di halaman dengan file atau layanan sumber sebelum menyalakan
   penggunaan operasional.
5. Setelah alur prediksi stabil, baru sambungkan preferensi wilayah dan ambang
   user ke pengiriman Telegram terjadwal.

### Keputusan yang ditunda

- Lokasi dan format final file hasil model.
- Apakah hasil model dibaca dari file atau dikirim ke FastAPI.
- Nama field final dan definisi apakah nilai utama adalah skor atau probabilitas.
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

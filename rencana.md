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

## Pipeline pembaruan mingguan — RENCANA, belum dibangun

Diminta agar proyek memicu pengambilan data sendiri tiap minggu. Untuk mock up
ini **sengaja tidak dibangun**; dicatat di sini agar tidak hilang.

### Prasyarat

| Hal | Keadaan |
|---|---|
| Akses jaringan | Sandbox pengembangan **tidak punya**. Skrip tidak bisa diuji end-to-end di sini. |
| API key FIRMS | Dibutuhkan. **Jangan pernah ditulis di kode/dokumen.** Masuk `.env` saja (`.env` sudah di-gitignore baris 132). |
| Data hotspot | Menurut `PIPELINE_DEV.md`, pengambilan FIRMS dipegang anggota lain. Koordinasikan sebelum menggandakan. |

### Rancangan

1. `tools/fetch_hotspots.py`
   - Baca `FIRMS_MAP_KEY` dari `.env`, bukan dari argumen CLI (argumen masuk
     riwayat shell).
   - Unduh periode baru dari API area FIRMS, simpan ke
     `data/hotspot_indonesia/`.
   - **Idempoten**: lewati bulan yang berkasnya sudah ada dan ukurannya wajar.
   - Tulis manifest kecil (tanggal unduh, jumlah baris, sumber) agar bisa diaudit.

2. `tools/refresh_weekly.py` — rantai: unduh → `prepare_adm2.py` →
   `build_hotspots.py` → salin ke `frontend/public/data/`.

3. Penjadwalan: **Windows Task Scheduler**, tiap Senin.
   Tidak perlu proses server hidup; cocok untuk laptop.

### Keputusan yang ditunda

- Mekanisme pemicu (Task Scheduler vs loop Python vs tombol manual).
- Apakah tanggal observasi digeser agar tampak mutakhir. **Saran: jangan** —
  menggeser tanggal observasi berarti memalsukan data.
- Sumber "aktual sekarang" yang lebih mutakhir, bila ada.

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

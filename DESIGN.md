# Design System: "Command Grade" v2

*Untuk: Sistem Peringatan Dini Risiko Hotspot Karhutla | Stack: React + Vite + Tailwind CSS + MapLibre GL | Versi: 2.0 | 30 Okt 2026*

*Menggantikan design system sebelumnya. Dial: ENERGY 2 / RHYTHM 2 / MOTION 1. Gaya: dashboard pemantauan bergaya HUD panel kendali untuk analis instansi. Dokumen ini dibuat agar dapat langsung diterjemahkan ke token Tailwind dan komponen React.*

## 1. Prinsip

1. **Warna = makna.** Hanya skala risiko yang berwarna. Semua elemen lain hitam, abu, atau putih.
2. **Tegas, bukan ribut.** Warna jenuh dipakai di area kecil dan jelas; latar tetap bersih.
3. **Struktur terlihat.** Bingkai siku, garis tipis, label kapital kecil, tab bersudut potong.
4. **Tiga penanda untuk setiap level:** warna, teks level, dan bentuk (ikon batang 1-4). Tidak ada informasi yang hanya bergantung pada warna.
5. **Jujur soal ketidakpastian.** Rentang, waktu pembaruan, dan batasan selalu terlihat.
6. **Bahasa netral.** Tidak memakai istilah militer atau ancaman (target, serang, bahaya).
7. **Status sistem bukan risiko.** Aktif, basi, dan galat memakai putih dan abu, tidak pernah hijau, merah, atau warna risiko lain.

## 2. Token warna

Ada dua tema: **gelap** (default) dan **terang**. Semua komponen membaca token lewat CSS variables; tidak ada warna yang ditulis langsung di komponen.

### 2.1 Netral

| Token | Gelap | Terang | Pemakaian |
| --- | --- | --- | --- |
| `--bg` | `#0A0B0A` | `#F4F6F5` | Latar halaman |
| `--surface` | `#111312` | `#FFFFFF` | Panel |
| `--surface-2` | `#181B19` | `#ECEFED` | Kartu, baris terpilih, tooltip |
| `--line` | `#2A2E2B` | `#D3D8D5` | Garis dasar 1 px |
| `--line-strong` | `#4A504C` | `#8A918D` | Garis aktif, bingkai |
| `--text` | `#F2F5F3` | `#0A0B0A` | Teks utama |
| `--text-muted` | `#9AA29D` | `#4F5652` | Teks sekunder |
| `--text-dim` | `#747B77` | `#6B726E` | Label tak aktif |
| `--accent` | `#FFFFFF` | `#0A0B0A` | Pilihan, tombol utama, bingkai terpilih |
| `--on-accent` | `#0A0B0A` | `#FFFFFF` | Teks di atas `--accent` |
| `--scrim` | `rgba(0,0,0,0.6)` | `rgba(10,11,10,0.4)` | Lapisan di bawah modal |

Nilai tema terang dan `--text-dim` perlu diperiksa dengan alat kontras sebelum dikunci. Target: teks 4,5:1, komponen non-teks 3:1.

### 2.2 Skala risiko (satu-satunya warna fungsional)

| Level | Token | Hex | Teks pada chip | Ikon batang | Arti |
| --- | --- | --- | --- | --- | --- |
| 1 RENDAH | `--risk-1` | `#22D36B` | hitam | 1 dari 4 | Kondisi terkendali |
| 2 SEDANG | `--risk-2` | `#FFD60A` | hitam | 2 dari 4 | Perlu dipantau |
| 3 TINGGI | `--risk-3` | `#FF8A00` | hitam | 3 dari 4 | Prioritas tindakan |
| 4 SANGAT TINGGI | `--risk-4` | `#FF2D3D` | hitam | 4 dari 4 | Prioritas tertinggi |

Ambang level: RENDAH di bawah 10%, SEDANG 10-25%, TINGGI 25-50%, SANGAT TINGGI 50% ke atas (usulan awal, mengikuti PRD).

Skala risiko yang sama dipakai di kedua tema. Warna tidak diubah antar tema agar maknanya konsisten.

### 2.3 Palet alternatif buta warna (opsi)

Diaktifkan lewat pengaturan "Palet ramah buta warna". Berbasis palet Okabe-Ito:

| Level | Hex |
| --- | --- |
| RENDAH | `#56B4E9` |
| SEDANG | `#F0E442` |
| TINGGI | `#E69F00` |
| SANGAT TINGGI | `#D55E00` |

Usulan; diuji dengan simulator buta warna (protanopia, deuteranopia, tritanopia) sebelum dikunci. Karena ikon batang dan pola peta selalu ada, palet ini bersifat tambahan, bukan satu-satunya penyelamat.

### 2.4 Aturan pemakaian warna

- Status sistem: putih/abu. Titik putih terisi = AKTIF, titik abu kosong = NONAKTIF, garis putus = BASI.
- Pilihan (selected): bingkai siku `--accent`, bukan warna lain.
- Hotspot aktual: titik `--accent` dengan cahaya lembut (tema gelap) atau titik hampir hitam bergaris putih (tema terang). Tidak memakai warna risiko.
- Hotspot baru (kurang dari 6 jam): cincin berdenyut, hanya bila `prefers-reduced-motion` tidak aktif.
- Level hanya boleh ditampilkan pada elemen yang mewakili risiko (chip, sel peta, meteran, ikon batang, kolom 3D).

## 3. Tipografi

| Peran | Font | Fallback |
| --- | --- | --- |
| Mono (label, angka, ID, koordinat, waktu) | JetBrains Mono | IBM Plex Mono, ui-monospace, monospace |
| Sans (kalimat, penjelasan) | Space Grotesk | IBM Plex Sans, system-ui, sans-serif |

Font dimuat lewat paket npm (`@fontsource-variable/jetbrains-mono`, `@fontsource-variable/space-grotesk`) atau dihost sendiri agar tidak bergantung pada CDN. Gunakan `font-display: swap`.

### Skala tipografi

| Token | Ukuran / tinggi baris | Gaya | Pemakaian |
| --- | --- | --- | --- |
| `label` | 12 / 16 px | Mono, kapital, jarak huruf 0,12 em, bobot 500 | Label, tab, chip, tag |
| `body-s` | 14 / 20 px | Sans, normal | Teks bantu, catatan |
| `body` | 15 / 22 px | Sans, normal | Teks isi, penjelasan faktor |
| `title-s` | 16 / 24 px | Mono, kapital, bobot 600 | Judul kartu |
| `title` | 20 / 28 px | Mono, kapital, bobot 600 | Judul panel |
| `stat` | 32 / 36 px | Mono, bobot 600 | Angka besar (skor, jumlah wilayah) |
| `display` | 48 / 52 px | Mono, bobot 600 | Rentang dampak utama |

Aturan: kalimat panjang tidak boleh dalam mono kapital. Angka memakai `font-variant-numeric: tabular-nums`. Panjang baris teks isi maksimal sekitar 70 karakter.

## 4. Spasi, bentuk, dan lapisan

### Spasi

Skala dasar 4 px: `1=4, 2=8, 3=12, 4=16, 6=24, 8=32, 12=48`. Padding panel 16 px (mobile 12 px). Jarak antar-panel 8 px. Tinggi bilah atas 48 px.

### Bentuk dan garis

- Radius 0-2 px (`--radius: 2px`). Chip dan tombol persegi.
- Garis 1 px `--line`. Tanpa bayangan tebal; kedalaman dari lapisan dan garis.
- **Bingkai siku (corner brackets):** empat siku di tiap sudut panel, panjang 10 px, tebal 1,5 px, `--accent` 60%; elemen terpilih 100%. Dibuat dengan pseudo-element atau komponen `<Frame>`.
- **Tab sudut potong:** pojok kanan atas dipotong 8 px dengan `clip-path`; tab aktif punya garis bawah `--accent` setebal 2 px.
- Pola kisi sangat halus (opasitas di bawah 5%) boleh dipakai di latar panel besar.

### Lapisan (z-index)

| Lapisan | Nilai |
| --- | --- |
| Peta | 0 |
| Kontrol peta, legenda | 10 |
| Kartu info mengambang | 20 |
| Dok bawah | 30 |
| Bilah atas | 40 |
| Tooltip | 50 |
| Modal dan drawer | 60 |
| Toast | 70 |

### Breakpoint

| Nama | Lebar | Perilaku |
| --- | --- | --- |
| `sm` | di bawah 768 px | Rel ikon menjadi tab bawah; dok bawah menjadi bottom sheet; kartu info penuh lebar |
| `md` | 768-1279 px | Rel ikon ramping; dok bawah dapat dilipat |
| `lg` | 1280 px ke atas | Tata letak HUD penuh |

## 5. Tata letak

1. **Bilah atas:** logo kiri; tab navigasi tengah (BERANDA, PETA, WILAYAH, RIWAYAT, METODE); kanan: lokasi/jam ("INDONESIA 02:30 WIB"), status data, tombol notifikasi, dan tombol tema.
2. **Rel ikon kiri:** ikon garis tipis 24 px; aktif berbingkai siku; pemisah 1 px antar-grup.
3. **Pengontrol skala** di atas peta: NASIONAL | PULAU | PROVINSI.
4. **Pemilih hari:** AKTUAL | BESOK | LUSA | TULAT (segmented control).
5. **Kanvas peta** penuh.
6. **Kartu info mengambang** tersambung garis 1 px ke sel terpilih.
7. **Zoom +/- dan tombol lapisan** di kanan bawah peta.
8. **Dok bawah:** tab (DAFTAR WILAYAH, STATISTIK, PERKIRAAN DAMPAK, RINGKASAN, CATATAN) dan baris kartu yang dapat digeser.
9. **Pita pernyataan batasan** tetap di dasar peta: "HOTSPOT ADALAH DETEKSI SATELIT, BUKAN KONFIRMASI KEBAKARAN."

## 6. Komponen

Semua komponen punya keadaan: **default, hover, fokus (keyboard), aktif/terpilih, nonaktif, memuat, galat** bila relevan. Cincin fokus: garis 2 px `--accent` dengan jarak 2 px. Target sentuh minimal 44 x 44 px.

### 6.1 Penanda risiko

| Komponen | Spesifikasi |
| --- | --- |
| **Level chip** | Persegi, isi warna level, teks hitam mono kapital ("RENDAH", "SEDANG", "TINGGI", "SANGAT TINGGI"), ikon batang di kiri. Ukuran: `sm` tinggi 24 px, `md` 32 px |
| **Ikon batang level** | Empat batang vertikal tipis; terisi sebanyak level (1-4), sisanya garis kosong. Dipakai juga pada tooltip dan daftar |
| **Meteran segmen** | 20 segmen vertikal tipis; terisi berwarna level, sisa abu gelap; angka persen mono di kanan. Mewakili skor 0-1 |
| **Legenda** | Empat blok warna berderet beserta label dan rentang probabilitas ("< 10%", "10-25%", "25-50%", "50%+"), ditambah penanda HOTSPOT (titik `--accent`) |
| **Kartu dampak** | Rentang area terdampak (`display`), batang rentang dengan penanda tengah, tag "PERKIRAAN", tautan "DASAR PERHITUNGAN"; selalu rentang, tidak pernah satu angka |

### 6.2 Status dan pesan

| Komponen | Spesifikasi |
| --- | --- |
| **Status tag sistem** | Garis tipis putih/abu, titik di kiri, teks mono kapital ("AKTIF", "NONAKTIF", "BASI"). BASI memakai garis putus |
| **Chip status data** | "DIPERBARUI 06:10 WIB"; berubah menjadi "DATA BASI: pembaruan terakhir 31 JAM LALU" bila melewati batas |
| **Pesan sistem (banner)** | Garis putih/abu, tanpa warna risiko; ikon info; dapat ditutup kecuali pernyataan batasan |
| **Toast** | Muncul 4 detik, kanan bawah; untuk konfirmasi ("Lokasi notifikasi disimpan"); tidak untuk risiko |
| **Keadaan kosong** | Teks netral: "BELUM ADA WILAYAH RISIKO TINGGI HARI INI" |
| **Keadaan galat** | Teks sans jelas + tombol "COBA LAGI"; tidak memakai merah |
| **Skeleton pemuatan** | Blok `--surface-2` dengan meteran segmen berjalan; "MENGHITUNG PERKIRAAN DAMPAK..." |

### 6.3 Navigasi dan kontrol

| Komponen | Spesifikasi |
| --- | --- |
| **Tab bilah atas** | Mono kapital 12 px, sudut potong, tab aktif bergaris bawah `--accent`; tab belum tersedia berlabel "SEGERA" dan tidak dapat difokus untuk dipilih |
| **Segmented control** | Satu garis, segmen aktif berisi `--accent` dengan teks `--on-accent` |
| **Tombol utama** | Isi `--accent`, teks `--on-accent` mono kapital, persegi, tinggi 44 px |
| **Tombol sekunder** | Garis `--accent` tipis, teks `--accent` |
| **Tombol ikon** | 44 x 44 px, ikon garis 24 px, `aria-label` wajib |
| **Toggle lapisan** | Persegi 20 px dalam target 44 px; aktif berisi `--accent`; label mono |
| **Input teks dan pencarian** | Garis 1 px `--line-strong`, fokus garis `--accent`; label kapital di atas; pesan galat sans di bawah |
| **Drawer/modal** | Panel `--surface` dengan bingkai siku, `--scrim` di belakang, fokus terkunci di dalam, `Esc` menutup |

### 6.4 Peta dan wilayah

| Komponen | Spesifikasi |
| --- | --- |
| **Kartu wilayah** (dok bawah) | Level chip + ID wilayah mono + ikon panah keluar; tinggi seragam 72 px; geser horizontal; terpilih berbingkai siku penuh |
| **Kartu info mengambang** | Chip level; judul ID sel dan nama wilayah; baris kunci-nilai (SKOR, KEKERINGAN, HOTSPOT 7 HARI) dengan meteran; tab RISIKO / KONTEKS; maksimal 3 faktor pendorong dalam kalimat sans; garis penyambung 1 px ke sel |
| **Tooltip** | `--surface-2`, bingkai siku, isi: level, skor, wilayah; muncul saat hover dan fokus |
| **Tabel wilayah** | Alternatif peta; kolom: level (ikon + teks), wilayah, skor, hotspot 7 hari; dapat diurutkan; baris terpilih `--surface-2` |

### 6.5 Notifikasi Telegram (di dalam web)

| Komponen | Spesifikasi |
| --- | --- |
| **Tombol notifikasi** (bilah atas) | Ikon lonceng; titik `--accent` bila langganan aktif |
| **Panel langganan** | Drawer berisi: status tautan Telegram, lokasi (nama kota/kabupaten + sel), ambang level (default TINGGI), radius (sel sendiri atau sel sendiri + sel sekitar), jam tenang, tombol "TAUTKAN TELEGRAM", "UJI KIRIM PESAN", "HENTIKAN NOTIFIKASI" |
| **Pemilih lokasi** | Dua cara: cari nama kota/kabupaten, atau tandai titik di peta mini. Menampilkan sel 25 km terkait. Tidak memakai lokasi GPS otomatis tanpa izin |
| **Penjelasan privasi** | Teks sans 14 px: lokasi disimpan hanya sebagai sel dan nama wilayah, dapat dihapus kapan saja |

## 7. Peta

- **Dasar:** relief gelap Indonesia (arang), garis pantai `--accent` 30%, batas provinsi 12%, tekstur gambut berupa pola garis halus. Tema terang memakai dasar abu muda dengan garis gelap yang setara. Penyedia tile `[ISI: kandidat peta vektor gratis seperti OpenFreeMap atau Protomaps; periksa lisensi dan atribusi]`. Semua nilai warna peta dibaca dari token.
- **Sel risiko 0,25 derajat:** persegi bergaris tipis; isi mengikuti level dengan opasitas: RENDAH 20%, SEDANG 40%, TINGGI 65%, SANGAT TINGGI 90%. Sel SANGAT TINGGI boleh berpendar tipis.
- **Pola isi saat zoom dekat:** garis diagonal untuk SEDANG, titik untuk TINGGI, silang untuk SANGAT TINGGI, polos untuk RENDAH.
- **Mode 3D (opsional):** sel menjadi kolom ekstrusi; tinggi = skor, warna = level. Ada tombol kembali ke 2D.
- **Hotspot aktual:** titik `--accent` dengan cahaya tipis; ukuran mengikuti FRP dalam tiga kelas; hotspot baru berdenyut.
- **Sel terpilih:** bingkai siku penuh dan garis ke kartu info.
- **Lokasi pengguna (bila ada langganan):** penanda lokasi berbentuk ikon pin garis putih; sel lokasi diberi bingkai putus-putus.
- **Label peta:** mono kapital kecil, `--accent` 60%.
- **Atribusi:** selalu tampil di sudut kanan bawah.

## 8. Nada bahasa

- **Label:** kapital, singkat ("PERKIRAAN AREA TERDAMPAK", "DIPERBARUI 06:10 WIB").
- **Kalimat:** huruf biasa, tenang, jelas.
- **Kata wajib:** "risiko munculnya hotspot", "perkiraan area terdampak". **Hindari:** "prediksi kebakaran pasti", "hutan hilang", "bahaya", "target", "serangan".
- **Contoh baik:** "Risiko tinggi muncul hotspot dalam 2 hari ke depan di sel ini." **Contoh buruk:** "BAHAYA KEBAKARAN!"
- **Catatan tetap:** "Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran."
- Teks yang tampil ke pengguna tidak boleh memuat rujukan dokumen internal (ID fitur, nomor bagian PRD).

## 9. Notifikasi Telegram: pesan

Pesan mengikuti nada yang sama: tenang, ringkas, dan selalu memuat waktu pembaruan serta batasan. Emoji bulat berwarna hanya dipakai untuk level risiko, sejalan dengan prinsip warna = makna. Tidak ada emoji api atau sirene.

**Pesan risiko baru atau naik level:**

> 🟠 RISIKO TINGGI: Surabaya Hari: Besok (31 Okt) Peluang munculnya hotspot di sekitar lokasimu: 25-50% Faktor utama: beberapa hari tanpa hujan; banyak hotspot di sel sekitar. Diperbarui 06:10 WIB. Model v0.3. Ini risiko munculnya hotspot, bukan konfirmasi kebakaran. Buka peta: \[tautan\]

**Pesan hotspot terdeteksi di sekitar lokasi:**

> ⚪ Hotspot terdeteksi di sekitar Surabaya (± 25 km) Waktu deteksi: 14:35 WIB Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.

**Pesan data basi:**

> Data belum diperbarui sejak 31 jam lalu. Informasi di atas mungkin tidak terkini.

**Perintah bot:** `/mulai`, `/lokasi`, `/ambang`, `/radius`, `/jamtenang`, `/status`, `/berhenti`. Semua balasan bahasa Indonesia dan memuat tombol inline bila memungkinkan.

## 10. Gerak

- Denyut cincin hanya untuk hotspot baru. Pemuatan memakai meteran segmen yang terisi bertahap.
- Transisi 120-200 ms, easing linear atau ease-out; tanpa animasi dekoratif besar.
- Pergantian hari pada peta: fade 160 ms.
- Hormati `prefers-reduced-motion`: denyut diganti cincin statis, transisi dipersingkat menjadi 0 ms.

## 11. Aksesibilitas

- Setiap level punya teks, ikon batang, dan pola (saat zoom dekat), tidak hanya warna.
- Teks isi minimal 14 px, label mono minimal 12 px, target sentuh minimal 44 px.
- Semua kontrol dapat dioperasikan dengan keyboard; urutan fokus logis; cincin fokus selalu terlihat.
- Tersedia tampilan tabel sebagai alternatif peta, dapat dicapai dengan satu tombol di bilah atas.
- Peta diberi `role="application"` dengan label dan petunjuk keyboard; perubahan data diumumkan lewat region `aria-live="polite"` (mis. "Peta Besok dimuat").
- Kontras: teks 4,5:1; garis dan ikon 3:1. Diperiksa untuk kedua tema dan kedua palet.
- Bahasa dokumen `lang="id"`.
- Opsi palet ramah buta warna (2.3) tersedia di pengaturan.

## 12. Implementasi di React + Vite + Tailwind

### 12.1 Token

Semua token berada di satu berkas, `src/styles/tokens.css`. Tema ditukar lewat atribut `data-theme` pada `<html>`; nilai awal mengikuti `prefers-color-scheme` dan pilihan pengguna disimpan.

```css
:root,
[data-theme="dark"] {
  --bg: #0A0B0A;
  --surface: #111312;
  --surface-2: #181B19;
  --line: #2A2E2B;
  --line-strong: #4A504C;
  --text: #F2F5F3;
  --text-muted: #9AA29D;
  --text-dim: #747B77;
  --accent: #FFFFFF;
  --on-accent: #0A0B0A;
  --risk-1: #22D36B;
  --risk-2: #FFD60A;
  --risk-3: #FF8A00;
  --risk-4: #FF2D3D;
  --radius: 2px;
  --bracket: 10px;
  --font-mono: "JetBrains Mono Variable", "IBM Plex Mono", ui-monospace, monospace;
  --font-sans: "Space Grotesk Variable", "IBM Plex Sans", system-ui, sans-serif;
}
[data-theme="light"] {
  --bg: #F4F6F5;
  --surface: #FFFFFF;
  --surface-2: #ECEFED;
  --line: #D3D8D5;
  --line-strong: #8A918D;
  --text: #0A0B0A;
  --text-muted: #4F5652;
  --text-dim: #6B726E;
  --accent: #0A0B0A;
  --on-accent: #FFFFFF;
}
[data-palette="cvd"] {
  --risk-1: #56B4E9;
  --risk-2: #F0E442;
  --risk-3: #E69F00;
  --risk-4: #D55E00;
}
```

Tailwind membaca token tersebut lewat konfigurasi tema (`@theme` pada Tailwind v4, atau `theme.extend.colors` pada v3; sesuaikan dengan versi yang terpasang), misalnya `bg-surface`, `text-muted`, `border-line`, `bg-risk-3`. **Aturan:** tidak ada hex di komponen; tinjauan kode menolak nilai warna langsung.

### 12.2 Struktur folder usulan

```
frontend/
  src/
    styles/        tokens.css, base.css
    components/
      ui/          Frame, Button, Chip, Tab, Segmented, Meter, Toggle, Tooltip, Drawer, Toast
      risk/        LevelChip, LevelBars, ScoreMeter, Legend, ImpactCard
      map/         MapView, RiskLayer, HotspotLayer, CellInfoCard, MapControls
      notify/      SubscribePanel, LocationPicker
      layout/      TopBar, IconRail, BottomDock
    pages/         Peta, Wilayah, Riwayat, Metode
    lib/           api.ts, risk.ts (ambang, label), time.ts
    types/         geojson.ts, api.ts
  public/
```

`lib/risk.ts` menjadi satu-satunya tempat pemetaan skor ke level, label, dan jumlah batang, sehingga ambang dapat diubah di satu tempat.

### 12.3 Prinsip komponen

- TypeScript strict; tanpa `any` untuk instance peta atau GeoJSON.
- Komponen risiko menerima `level: 1 | 2 | 3 | 4`, bukan warna.
- Komponen peta dipisah dari UI agar dapat diuji; instance MapLibre hanya dibuat sekali dan dibersihkan saat unmount.
- Seluruh teks tampil dari berkas string terpusat bahasa Indonesia, agar aturan bahasa mudah diperiksa.

## 13. Daftar periksa desain sebelum rilis

- [ ] Tidak ada warna risiko pada status sistem atau dekorasi.
- [ ] Setiap tampilan level memiliki teks dan ikon batang.
- [ ] Kontras dua tema dan dua palet sudah diperiksa.
- [ ] Pernyataan batasan terlihat di halaman peta dan pesan Telegram.
- [ ] Dampak selalu rentang dan memuat penanda PERKIRAAN.
- [ ] Tidak ada rujukan internal pada teks pengguna.
- [ ] Seluruh kontrol dapat dicapai dengan keyboard dan target sentuh minimal 44 px.
- [ ] Tampilan tabel setara dengan peta.
- [ ] `prefers-reduced-motion` dihormati.

## 14. Hal yang dihindari

- Warna risiko untuk dekorasi atau status sistem.
- Ikon api, ilustrasi asap, atau foto hutan terbakar.
- Gradasi neon berlebihan dan efek kaca buram.
- Bahasa militer atau sensasional.
- Satu angka dampak tanpa rentang dan penjelasan.
- Warna yang ditulis langsung di komponen.

## 15. Belum diputuskan

- Ambang akhir empat level setelah validasi model.
- Nama proyek dan logo (sementara "HOTSPOT.ID").
- Penyedia tile peta dasar dan lisensinya.
- Palet buta warna final setelah uji simulator.
- Apakah mode 3D masuk MVP atau fase berikutnya.

# PRD: Sistem Peringatan Dini Risiko Hotspot Karhutla

*Versi: draf 0.2 | Tanggal: 30 Okt 2026 | Penyusun: `[ISI nama tim]` | Mata kuliah: Projek Sistem Cerdas, semester 5*

*Catatan: kebutuhan pemangku kepentingan masih hipotesis (ditandai \[H\]) dan divalidasi lewat dosen serta studi dokumen. Butir bertanda `[ISI]` belum diputuskan.*

## 1. Ringkasan

Produk web yang memperkirakan **risiko munculnya hotspot** 1-3 hari ke depan untuk setiap sel grid 0,25 derajat (sekitar 25 km) di Indonesia, menampilkan hotspot aktual terkini, dan memberi **perkiraan area terdampak** sebagai rentang. Pemangku kepentingan yang diperankan adalah **BNPB**, sebagai pihak yang seolah-olah meminta sistem ini untuk kesiapsiagaan dan penentuan prioritas wilayah.

Produk ini adalah **alat bantu keputusan**. Produk ini bukan peringatan resmi dan bukan konfirmasi kebakaran.

## 2. Latar belakang dan masalah

- Karhutla rutin terjadi tiap musim kemarau, terutama di lahan gambut Riau, Sumatera Selatan, dan Kalimantan, dan makin parah pada tahun El Niño. Dampaknya mencakup asap lintas wilayah, gangguan kesehatan, dan kerugian ekonomi.
- Pemantauan hotspot yang ada bersifat **reaktif** (melaporkan yang sudah terdeteksi). Peringatan dini yang berorientasi ke depan dan spesifik per area membantu penentuan prioritas kesiapsiagaan. `[H: kaji sistem yang sudah ada, misalnya SiPongi, agar produk ini melengkapi, bukan menduplikasi]`
- Temuan awal analisis data (2012-Sep 2026, 3,94 juta deteksi VIIRS):
  - Hotspot sangat musiman (Agu-Okt sekitar 71%) dan sangat bervariasi antar tahun.
  - Hotspot terkonsentrasi: 50% berasal dari 9% sel grid.
  - Aturan sederhana "ada hotspot hari ini, maka ada lagi dalam 1-3 hari" (persistensi) menghasilkan presisi 62% dan recall 31%. Ruang perbaikan ada pada recall.

## 3. Tujuan dan non-tujuan

### Tujuan

1. Peta risiko hotspot 1-3 hari ke depan, diperbarui otomatis tiap hari.
2. Menjelaskan faktor pendorong risiko dalam bahasa non-teknis.
3. Perkiraan area terdampak sebagai rentang, lengkap dengan dasar perhitungan.
4. Membantu BNPB memprioritaskan wilayah untuk kesiapsiagaan dan koordinasi.
5. Transparan soal akurasi, ketidakpastian, dan keterbatasan.
6. Memenuhi deliverable mata kuliah: model terevaluasi, sistem berjalan, dan demo akhir.

### Non-tujuan

- Simulasi perambatan atau arah penyebaran api.
- Estimasi emisi karbon dan kualitas udara.
- Prediksi lebih dari 3 hari.
- Konfirmasi kebakaran atau pengganti peringatan resmi.
- Resolusi lebih halus dari 0,25 derajat.
- Notifikasi, manajemen akses berperan, dan API publik (di luar semester ini).

## 4. Pemangku kepentingan

| Pemangku | Peran | Kebutuhan \[H\] | Keputusan yang didukung |
| --- | --- | --- | --- |
| **BNPB** | Pemangku utama (diperankan), koordinasi kesiapsiagaan dan tanggap darurat | Gambaran risiko lintas provinsi 1-3 hari, daftar wilayah prioritas, perkiraan dampak, ringkasan harian | Alokasi sumber daya, koordinasi dengan daerah |
| Dosen pembimbing | Penguji dan validator kebutuhan | Kejelasan metode, evaluasi jujur, kelayakan sistem | Penilaian proyek |
| Kementerian Kehutanan, BPBD, BMKG | Calon pengguna dan mitra, di luar validasi semester ini | Informasi risiko di wilayahnya, konsistensi dengan peringatan resmi | Pengembangan lanjutan |
| Masyarakat umum | Pengguna sekunder | Informasi risiko yang mudah dipahami | Kewaspadaan |
| Tim pengembang | Pembangun dan pemelihara | Pipeline andal, model terpantau | - |

**Validasi kebutuhan:** karena wawancara langsung dengan BNPB tidak dilakukan, kebutuhan divalidasi melalui (1) tinjauan oleh dosen, dan (2) studi dokumen publik BNPB dan sistem pemantauan yang ada. Hal ini dicatat sebagai keterbatasan di laporan akhir.

## 5. Cerita pengguna

| ID | Sebagai | Saya ingin | Agar |
| --- | --- | --- | --- |
| U1 | Analis BNPB | melihat provinsi dan kabupaten dengan risiko tertinggi 3 hari ke depan | menentukan wilayah yang perlu koordinasi lebih dulu |
| U2 | Analis BNPB | mengetahui alasan sebuah sel berisiko tinggi | memilih tindakan pencegahan yang tepat |
| U3 | Analis BNPB | melihat perkiraan area terdampak sebagai rentang | memahami skala kemungkinan dampak |
| U4 | Pimpinan | melihat ringkasan situasi harian | mengambil keputusan dengan pemahaman ketidakpastian |
| U5 | Dosen/peneliti | membaca metode dan metrik evaluasi | menilai kepercayaan terhadap hasil |
| U6 | Admin | mengetahui status pipeline dan versi model | memastikan data tidak basi dan hasil dapat ditelusuri |

## 6. Definisi inti (dikunci sebelum pengembangan)

### 6.1 Satuan prediksi

Satu baris data = satu **sel grid 0,25 derajat** pada satu **tanggal lokal (waktu surya)**. ID sel: `lat_i = floor((lat + 12) / 0.25)`, `lon_i = floor((lon - 94) / 0.25)`, `cell_id = lat_i * 1000 + lon_i`. Pergeseran grid 0,125 derajat agar sejajar titik ERA5 masih keputusan terbuka dan tidak diubah tanpa kesepakatan tim.

### 6.2 Label dan horizon

- **Label**: 1 bila sel memiliki minimal satu deteksi hotspot VIIRS pada tanggal target, 0 bila tidak. Label berasal langsung dari data hotspot yang teramati.
- **Horizon**: tiga model terpisah, masing-masing untuk **Besok (t+1)**, **Lusa (t+2)**, dan **Tulat (t+3)**. Fitur hanya memakai informasi yang tersedia pada hari t.
- **Aktual (t+0)**: bukan prediksi. Ini adalah hotspot yang sudah terdeteksi 24 jam terakhir, ditampilkan sebagai observasi dan tingkat sel hari ini.

### 6.3 Peran clustering

Clustering **tidak dipakai untuk menentukan label**, karena label hotspot sudah teramati langsung. Menggunakan hasil clustering sebagai label berisiko membuat kelas yang sulit dijelaskan dan sulit dievaluasi. Clustering dipakai untuk dua hal yang lebih tepat:

1. **Tipologi wilayah (fitur):** mengelompokkan sel berdasarkan pola musiman dan intensitas historis (mis. K-Means pada profil bulanan), lalu ID kelompok menjadi fitur model.
2. **Kejadian spasial (untuk dampak):** mengelompokkan hotspot berdekatan (mis. DBSCAN) menjadi satu klaster kejadian untuk menghubungkan hotspot dengan luas area terbakar historis.

`[ISI: konfirmasi dengan dosen apakah klasifikasi dengan label teramati dapat diterima sebagai pendekatan utama]`

### 6.4 Level risiko (4 level, ambang sederhana)

Model mengeluarkan **probabilitas terkalibrasi** per sel per hari. Level ditentukan dengan ambang tetap yang mudah dijelaskan:

| Level | Probabilitas | Cara menjelaskan ke pengguna |
| --- | --- | --- |
| RENDAH | di bawah 10% | Hotspot di sel ini jarang muncul |
| SEDANG | 10% sampai di bawah 25% | Sekitar 1 dari 4 sel serupa akan muncul hotspot |
| TINGGI | 25% sampai di bawah 50% | Sekitar 1 dari 3 sampai 1 dari 2 sel serupa akan muncul hotspot |
| SANGAT TINGGI | 50% ke atas | Setengah atau lebih sel serupa akan muncul hotspot |

Ambang di atas adalah **usulan awal**. Karena probabilitas dikalibrasi, kalimat "dari 100 sel berlevel Tinggi, sekitar 25 sampai 50 akan muncul hotspot" dapat dibuktikan lewat kurva kalibrasi dan ditampilkan di halaman metode. Ambang dapat disesuaikan setelah validasi, tetapi tetap dengan angka bulat. Karena laju dasar berubah dari 3,4% (Desember) sampai 23,7% (September), peta musim hujan akan didominasi Rendah dan itu dianggap wajar; ini dijelaskan di halaman metode.

## 7. Kebutuhan fungsional

Prioritas: **M** = Must, **S** = Should, **C** = Could. Fase: 1 = MVP.

| ID | Kebutuhan | Prio | Fase | Kriteria penerimaan |
| --- | --- | --- | --- | --- |
| F1 | **Peta risiko.** Level dan skor tiap sel untuk Aktual, Besok, Lusa, Tulat | M | 1 | Seluruh sel aktif tampil; pergantian hari tanpa muat ulang penuh |
| F2 | **Hotspot aktual 72 jam.** Waktu lokal, confidence, FRP | M | 1 | Bersumber dari FIRMS NRT; ada pernyataan "Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran" |
| F3 | **Detail sel.** Level, skor, maksimal 3 faktor pendorong, hotspot 7 hari, persentase gambut | M | 1 | Faktor berupa kalimat bahasa awam, konsisten dengan penjelasan model |
| F4 | **Status pembaruan dan batasan.** Waktu pembaruan, penanda DATA BASI (lebih dari 24 jam), pernyataan batasan | M | 1 | Penanda muncul otomatis; batasan selalu tampil di halaman peta |
| F5 | **Halaman metode dan data.** Cara kerja, precision/recall per tahun, kalibrasi, sumber dan atribusi, keterbatasan | M | 1 | Metrik per tahun termasuk tahun El Niño; sumber beserta atribusi |
| F6 | **Jejak versi.** Versi model, versi data, waktu pembuatan | M | 1 | Terlihat di tampilan hasil dan ekspor |
| F7 | **Peringkat dan daftar wilayah.** Wilayah teratas; filter pulau, provinsi, "di atas gambut" | S | 2 | Konsisten dengan data peta; filter dapat digabung |
| F8 | **Tampilan tabel.** Alternatif peta untuk sel berisiko tinggi | S | 2 | Isi setara peta; dapat diurutkan |
| F9 | **Perkiraan area terdampak.** Rentang luas, porsi hutan/gambut/lahan lain | S | 2 | Selalu rentang dengan penanda ketidakpastian; ada dasar perhitungan; backtest tersedia; tanpa istilah "hutan hilang" |
| F10 | **Lapisan konteks.** Gambut, tutupan lahan, batas wilayah | S | 2 | Dapat dinyalakan/dimatikan; sumber dan tahun tercantum |
| F11 | **Riwayat dan tren.** Pola musiman, perbandingan tahun El Niño | C | 3 | Data 2012 sampai sekarang |
| F12 | **Ekspor data dan ringkasan harian.** CSV/GeoJSON dan ringkasan cetak | C | 3 | Memuat stempel waktu dan catatan batasan |

Di luar semester ini: notifikasi, umpan balik verifikasi lapangan, API publik, dan manajemen akses.

### Tentang perkiraan dampak

Ide awal "berapa luas hutan yang akan hilang" diubah menjadi **perkiraan luas area terdampak** dalam bentuk rentang (mis. "120-340 ha"), dengan rincian porsi hutan, gambut, dan lahan lain. Alasannya: (1) model tidak dapat memastikan terjadinya kebakaran, (2) satelit tidak membedakan area yang hilang dan area yang hanya terbakar, dan (3) satu angka pasti akan menyesatkan. Pendekatan: untuk tiap klaster kejadian historis (bagian 6.3), hubungkan hotspot dengan luas area terbakar historis, lalu gunakan model kuantil (mis. persentil 10, 50, 90) untuk rentang. **F9 bergantung pada ketersediaan data area terbakar historis (BA\_MODIS/BA\_VIIRS atau sumber lain) yang belum diperiksa.** Bila data tidak layak, F9 diturunkan menjadi estimasi kasar berbasis rata-rata historis per tipe lahan, tetap sebagai rentang.

## 8. Kebutuhan model dan analitik

- **Tugas**: klasifikasi biner per sel per hari untuk tiga horizon (6.2).
- **Keluaran**: probabilitas terkalibrasi, dikonversi menjadi 4 level (6.4).
- **Pembanding wajib**: persistensi, klimatologi, regresi logistik.
- **Metode utama**: gradient boosting (LightGBM atau XGBoost). Kalibrasi memakai isotonic atau Platt scaling.
- **Fitur** (tersedia pada hari t): riwayat hotspot (1, 3, 7, 14, 30 hari), cuaca dan kekeringan, indeks iklim (Nino3.4, DMI), gambut, tutupan lahan, tipologi wilayah dari clustering, serta musim.
- **Evaluasi**: pembagian berdasarkan waktu, rolling-origin per tahun; **metrik utama precision dan recall**, dilengkapi PR-AUC dan kurva kalibrasi; dilaporkan terpisah untuk tahun El Niño, tahun sepi, musim kemarau (Jul-Nov), dan per pulau.
- **Penjelasan**: faktor pendorong per sel (SHAP) diterjemahkan ke kalimat awam.
- **Fallback**: bila data cuaca terlambat, gunakan model berbasis riwayat dan tampilkan penanda "tanpa data cuaca terkini", atau tandai hasil basi.

### Catatan penting: data cuaca operasional

ERA5 memiliki jeda beberapa hari dan bukan prakiraan. Untuk risiko 1-3 hari ke depan sistem membutuhkan **data prakiraan** dengan variabel sepadan. Keputusan `[ISI]`: model dilatih dengan data historis yang sepadan dan dijalankan dengan sumber prakiraan (kandidat: Open-Meteo, GFS, atau data BMKG bila dapat diakses). Perbedaan antara data latih dan data operasional dicatat sebagai risiko dan diuji lewat evaluasi tambahan.

## 9. Kebutuhan data

| Data | Sumber | Fungsi | Status |
| --- | --- | --- | --- |
| Hotspot | NASA FIRMS (VIIRS SNPP dan NOAA-20; SP dan NRT) | Label, riwayat, hotspot aktual | Ada (2012-Sep 2026); NRT harian |
| Cuaca dan kekeringan | ERA5 (latih); sumber prakiraan `[ISI]` (operasional) | Fitur pemicu | Sedang dikumpulkan |
| Indeks iklim | NOAA Nino3.4, DMI | Sinyal skala besar | Sedang dikumpulkan |
| Gambut | GFW/instansi | Kerentanan lahan, filter | Sedang dikumpulkan |
| Tutupan lahan dan hutan | WorldCover, Hansen | Konteks dan dampak | Sedang dikumpulkan |
| Batas wilayah | geoBoundaries, GADM | Agregasi dan peringkat | Sebagian ada |
| Area terbakar historis | BA\_MODIS, BA\_VIIRS atau lainnya | Dasar estimasi dampak | **Belum diperiksa** |

Lisensi dan atribusi tiap sumber diperiksa sebelum rilis.

## 10. Arsitektur dan tech stack

| Lapisan | Pilihan | Keterangan |
| --- | --- | --- |
| Frontend | React.js + Vite + Tailwind CSS, MapLibre GL | Antarmuka bahasa Indonesia; mengikuti design system "Command Grade" |
| Backend | FastAPI (Python) | Menyajikan data risiko, hotspot, meta, dan perkiraan dampak |
| Basis data | Supabase (PostgreSQL, dapat dengan PostGIS) | Menyimpan hasil prediksi, hotspot, metadata, dan versi |
| Pipeline ML | Python (pandas, LightGBM/XGBoost, scikit-learn) | Berjalan terjadwal harian |

**Alur harian:** ambil hotspot NRT dan cuaca prakiraan, bangun fitur, prediksi tiga horizon, kalibrasi, petakan ke level, simpan ke Supabase beserta `meta`, lalu FastAPI menyajikan ke frontend. Penjadwalan: `[ISI: GitHub Actions / cron / lainnya]`. Hosting: `[ISI]`.

**Catatan perubahan:** kode frontend yang sudah ada memakai Next.js. Keputusan beralih ke React + Vite perlu dicatat, dan komponen yang dapat dipakai ulang (token desain, komponen peta, pemilih hari) dipindahkan.

### Kontrak data (usulan)

- `meta`: `generated_at` (ISO, WIB), `data_hotspot_latest_at`, `model_version`, `data_version`, `stale_after_hours`.
- Risiko per hari (`d0` sampai `d3`): fitur poligon dengan `cell_id`, `level` (1-4), `score` (0-1), `province`, `island`, `drivers` (maksimal 3 kalimat), `peat_pct`.
- Hotspot 72 jam: fitur titik dengan `time_local`, `confidence` (l/n/h), `frp`.
- Perkiraan dampak (fase 2): `cell_id` atau wilayah, `area_low`, `area_mid`, `area_high`, porsi per tipe lahan.

Pada tahap awal frontend boleh memakai file statis atau endpoint tiruan dengan data contoh yang jelas ditandai sampai data nyata tersedia.

## 11. Kebutuhan non-fungsional

- **Kesegaran**: pembaruan minimal sekali per hari; penanda basi bila lebih dari 24 jam.
- **Ketersediaan**: bila pipeline gagal, tampilan memuat hasil terakhir yang berhasil dengan penanda.
- **Kinerja**: peta dan panel detail dimuat dalam waktu wajar `[ISI: target waktu muat]`.
- **Keterlacakan**: setiap hasil membawa versi model dan data.
- **Keamanan**: kunci API (mis. FIRMS MAP\_KEY, kunci Supabase layanan) tidak disimpan di repositori; memakai variabel lingkungan.
- **Aksesibilitas dan bahasa**: bahasa Indonesia; level selalu memiliki teks dan bentuk, tidak hanya warna; tersedia alternatif non-peta; target sentuh minimal 44 px.
- **Atribusi**: seluruh sumber data diberi atribusi.

## 12. Metrik keberhasilan

Target awal dirumuskan dari acuan persistensi (presisi 62%, recall 31%) dan akan ditinjau setelah baseline model selesai.

| Kategori | Metrik | Target awal \[H\] |
| --- | --- | --- |
| Model | Recall pada presisi minimal 60%, horizon Besok | Lebih tinggi dari persistensi (31%); target awal `[ISI, usulan 45-50%]` |
| Model | Precision dan recall untuk Lusa dan Tulat | Dilaporkan jujur; boleh menurun seiring horizon |
| Model | PR-AUC dibanding persistensi, klimatologi, regresi logistik | Lebih baik dari ketiganya pada tahun uji |
| Model | Kalibrasi | Frekuensi nyata tiap level berada dalam rentang probabilitasnya |
| Dampak (F9) | Cakupan rentang terhadap area terbakar historis | `[ISI persentase]` pada backtest |
| Sistem | Persentase hari dengan data tidak basi | `[ISI]` |
| Akademik | Demo akhir berjalan end-to-end | Pipeline harian, peta, detail sel, halaman metode |

## 13. Cakupan dan jadwal semester

| Fase | Isi | Kriteria keluar |
| --- | --- | --- |
| 0. Riset dan model | Preprocessing, fitur, clustering, baseline, model, backtest, kalibrasi, ambang level | Model mengalahkan pembanding; ambang level disepakati dengan dosen |
| 1. MVP | F1-F6 | Pipeline harian stabil; hasil dapat ditelusuri; demo kepada dosen |
| 2. Pendalaman | F7-F10 | Perkiraan dampak lolos backtest atau diturunkan ke versi kasar |
| 3. Tambahan | F11, F12 | Hanya bila waktu tersisa |

Jadwal per fase dan pembagian tugas anggota: `[ISI]`.

## 14. Risiko dan asumsi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Hotspot dianggap kebakaran terkonfirmasi | Keputusan keliru | Bahasa "risiko", pernyataan batasan permanen, halaman metode |
| Data cuaca operasional berbeda dari data latih | Kinerja nyata lebih rendah dari backtest | Variabel sepadan, uji dengan data prakiraan, pemantauan |
| Data area terbakar tidak tersedia | F9 tidak dapat dibuktikan | Turunkan ke estimasi kasar berbentuk rentang; catat sebagai keterbatasan |
| Hanya sekitar 15 musim kemarau | Model menghafal tahun | Rolling-origin, fitur sedikit, ablation |
| Ambang level tidak mencerminkan kebutuhan | Peta kurang berguna | Kalibrasi, validasi dengan dosen, ambang bulat dan konsisten |
| Peringatan palsu atau terlewat | Sumber daya terbuang atau kejadian terlewat | Evaluasi per tahun dan musim, pelaporan jujur |
| Waktu semester terbatas | Fitur tidak selesai | Prioritas M/S/C dan pemotongan fase |
| Ketersediaan API sumber data | Pipeline terhenti | Cadangan, penanda basi, simpan hasil terakhir |

**Asumsi:** BNPB diperankan sebagai pemangku; resolusi 0,25 derajat cukup untuk keputusan tingkat provinsi dan kabupaten; sumber prakiraan cuaca dengan variabel sepadan tersedia gratis; akses sistem terbuka tanpa login pada semester ini.

## 15. Pertanyaan terbuka

1. Sumber prakiraan cuaca apa yang dipakai untuk operasional?
2. Apakah data area terbakar historis tersedia dan berlisensi untuk dipakai?
3. Apakah dosen menerima klasifikasi berlabel teramati sebagai pendekatan utama, dengan clustering sebagai pendukung?
4. Apakah ambang 10%, 25%, 50% dipertahankan setelah validasi?
5. Di mana pipeline dijadwalkan dan sistem dihosting?
6. Apakah frontend Next.js yang sudah ada dilanjutkan atau dipindahkan penuh ke React + Vite?

## 16. Lampiran: ringkasan temuan EDA

- 3.941.038 deteksi, 20 Jan 2012-30 Sep 2026; tanpa nilai kosong; hanya di dalam Indonesia.
- Puncak tahunan: 2015 (875 ribu), 2014 (552 ribu), 2019 (436 ribu), 2026 sampai September (418 ribu), 2023 (250 ribu).
- 3.267 sel aktif; 50% hotspot dari 290 sel, 80% dari 828 sel, 95% dari 1.541 sel.
- Laju dasar label "ada hotspot dalam 1-3 hari": 9,9% (3,4% Desember sampai 23,7% September). Persistensi: presisi 62%, recall 31%.
- Tidak ada tren jangka panjang yang signifikan; variasi antar tahun dipengaruhi kondisi iklim.
- Tanggal UTC berbeda dari tanggal lokal pada 34% baris, sehingga label memakai tanggal lokal (waktu surya).

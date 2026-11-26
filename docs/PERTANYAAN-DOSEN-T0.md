# Pertanyaan untuk Dosen Pembimbing — Level Wilayah (T0)

*Berkas kerja. Ringkas, siap dikirim/diserahkan. Rujukan: `docs/DECISIONS.md` bagian
"Keputusan terbuka T0".*

## Konteks singkat

Dosen meminta peta dan tab wilayah prioritas menampilkan sampai **kabupaten/kota**, bukan
hanya provinsi. Kami menemukan bahwa PRD sendiri sudah menyebut kabupaten di dua tempat
(user story U1 dan asumsi §12), tetapi §3 menetapkan non-tujuan "resolusi lebih halus dari
0,25 derajat".

Kami membaca itu sebagai: yang dibatasi adalah **resolusi model**, bukan **granularitas
tampilan**. Model tetap memprediksi per sel 0,25° (± 25 km); kabupaten/kota adalah agregasi
sel-sel tersebut. Dengan pembacaan ini tidak ada janji metodologis yang dilanggar. Mohon
konfirmasi bila pembacaan ini keliru.

## Tiga pertanyaan

**1. Level administratif sampai mana?**
Kami usulkan berhenti di **kabupaten/kota (ADM2)**. Alasannya: batas kecamatan (ADM3) tidak
seragam kualitasnya, dan sel 25 km tidak bermakna pada skala kecamatan. Apakah cukup di ADM2?

**2. Kabupaten ditampilkan sebagai apa?**
- (a) **Risiko agregat kabupaten** — rata-rata berbobot luas dari sel di dalamnya, selalu
  disertai jumlah sel dan persentase cakupan wilayah. *(usulan kami)*
- (b) **Prediksi risiko kabupaten** — model dilatih/diprediksi ulang per kabupaten.

Kami menolak (b) karena melanggar non-tujuan §3 dan karena data per kabupaten terlalu tipis
untuk dievaluasi secara jujur. Mohon konfirmasi pilihan (a).

**3. "Risiko luas jika tidak ditangani" diukur dengan apa?**
- (a) **Hektar area terdampak**, disajikan sebagai **rentang** (mis. 1.875–3.125 ha).
- (b) **Jumlah hotspot** yang diperkirakan muncul.

Kami usulkan (a), karena itu yang secara harfiah diminta ("risiko luas"). Perlu diketahui:
1 sel ≈ 625 km² = 62.500 ha, sehingga luas wajib dihitung memakai fraksi cakupan kabupaten
terhadap tiap sel. Tanpa itu, satu kabupaten bisa tercatat memiliki luas terdampak yang
melampaui luas wilayahnya sendiri.

## Yang kami butuhkan

Keputusan atas ketiga butir di atas. Setelah itu kami dapat menetapkan sumber batas wilayah,
membuat crosswalk sel↔kabupaten, dan menetapkan kontrak data sebelum menyentuh antarmuka.

## Catatan

Rekomendasi naratif akan dibuat oleh LLM yang **hanya menarasikan** angka hasil hitungan
deterministik (jumlah sel, cakupan, rentang luas). LLM tidak diberi wewenang menghitung atau
memunculkan angka baru, agar setiap angka di antarmuka dapat ditelusuri kembali ke sel asalnya.

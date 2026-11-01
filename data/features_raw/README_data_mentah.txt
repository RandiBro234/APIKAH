DATA MENTAH CRAWLER — TIDAK DISIMPAN DI GIT
===========================================

4.135 berkas | 16,91 GB | 14 berkas >100 MB (batas GitHub)

AmbIL DARI DRIVE
----------------
  >>> ISI LINK FOLDER DRIVE DI SINI <<<

  copernicus.zip  7,16 GB  531 berkas  era5land/{instant,accum}, cems_fire
  nasa.zip        4,07 GB  2.992 berkas  mcd64a1
  static.zip      5,68 GB  612 berkas  hansen, worldcover, dem, osm, boundaries, peatlands

  Checksum zip: SHA256SUMS.txt (folder Drive yang sama)

CARA PASANG
-----------
1. Unduh zip yang perlu saja:
     analisis/pemodelan cuaca  -> copernicus.zip
     fitur lahan/statis        -> static.zip
     burned area (belum diolah)-> nasa.zip

2. Ekstrak ke folder ini (data/features_raw/). Hasilnya harus:

     data/features_raw/copernicus/era5land/instant/*.nc
     data/features_raw/copernicus/era5land/accum/*.nc
     data/features_raw/copernicus/cems_fire/*.nc
     data/features_raw/nasa/mcd64a1/*.hdf
     data/features_raw/static/{hansen,worldcover,dem,osm,boundaries,peatlands}/

   Jangan ubah nama folder; kode mencari path persis itu.

3. Opsional tapi disarankan setelah unduh besar:

     cd hotspot_crawler
     python verify_data.py

   Harus keluar:

     ok       : 4135
     mismatch : 0
     missing  : 0
     SEMUA COCOK dengan manifest.

   Kalau ada mismatch/missing, unduh ulang berkas yang disebut.

CATATAN
-------
- Jangan unggah ulang isi static/boundaries/ (GADM) ke tempat publik.
- Atribusi & lisensi data turunan: data/NOTICE.md.
- Daftar checksum per berkas: data/MANIFEST_raw.csv.
- File ini satu-satunya isi features_raw yang ikut Git; sisanya diabaikan.

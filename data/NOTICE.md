# Atribusi dan lisensi data

Terakhir diperiksa: 2026-11-01.

Repo ini mendistribusikan tabel turunan (Parquet) dari dua layanan Copernicus.
Keduanya memakai **CC-BY 4.0** sejak 2 Juli 2025 (sebelumnya "Licence to use
Copernicus Products"). CC-BY mengizinkan reproduksi, distribusi, komunikasi
publik, serta adaptasi/modifikasi, **dengan syarat atribusi**.

## 1. ERA5-Land (Cuaca)

Dipakai oleh: `features_processed/era5_daily/`, `features_processed/features_daily/`,
`features_processed/training/` (kolom cuaca).

- Sumber: Copernicus Climate Change Service (C3S) Climate Data Store.
- Lisensi: CC-BY 4.0 — <https://cds.climate.copernicus.eu/licences>
- Sitasi:
  Muñoz Sabater, J. (2019): *ERA5-Land hourly data from 1950 to present*.
  Copernicus Climate Change Service (C3S) Climate Data Store (CDS).
  DOI: <https://doi.org/10.24381/cds.e2161bac>
- Atribusi wajib:
  > Contains modified Copernicus Climate Change Service information 2023.
  > Neither the European Commission nor ECMWF is responsible for any use that
  > may be made of the Copernicus information or data it contains.

## 2. CEMS Fire Danger Indices (Indeks bahaya api)

Dipakai oleh: `features_processed/fire_daily/`, `features_processed/training/`
(kolom indeks api).

- Sumber: Copernicus Emergency Management Service (CEMS) via CEMS Early Warning
  Data Store (EWDS); dikelola EC-JRC, dihitung ECMWF.
- Lisensi: CC-BY 4.0 — <https://ewds.climate.copernicus.eu/licences/cc-by> dan
  <https://ewds.climate.copernicus.eu/licences/terms-of-use-cems>
- Sitasi:
  Copernicus Climate Change Service, Climate Data Store (2019):
  *Fire danger indices historical data from the Copernicus Emergency Management
  Service*. DOI: <https://doi.org/10.24381/cds.0e89c522>
- Atribusi wajib:
  > Contains modified Copernicus Emergency Management Service information 2023.

## 3. Catatan modifikasi

Tabel di repo ini bukan produk asli Copernicus. Perubahannya:

- ERA5-Land: agregasi harian dari data per jam, konversi satuan (K→°C, m→mm),
  perhitungan RH/VPD, lalu agregasi spasial ke grid 0,25° (sel 0,25°).
- CEMS Fire: agregasi harian dan pemetaan ke grid 0,25° yang sama.
- `features_daily/`: fitur turunan (jendela hujan bergerak, SPI empiris, kalender,
  dan indeks iklim NOAA) dari tabel cuaca di atas.
- `training/`: gabungan cuaca + indeks api + fitur turunan + label hotspot.

Karena itu atribusi memakai frasa **"Contains modified ..."**, bukan
"Generated using ...".

## 4. Cakupan data yang di-track

Hanya sebagian kecil keluaran pipeline yang disimpan di Git, sebagai contoh
hasil untuk validasi:

| Folder | Bulan tersedia |
|---|---|
| `era5_daily/` | 2023-07, 2023-08 |
| `fire_daily/` | 2023-07 |
| `features_daily/` | 2023-07, 2023-08 |
| `training/` | 2023-07, 2023-08 |

Data lengkap 2012-01–2026-09 tidak disimpan di Git; bangun ulang dari
`data/features_raw/` dengan perintah di `docs/pipeline/README.md`.

## 5. Data yang tidak tercakup notice ini

- Label hotspot (VIIRS) di `hotspot_indonesia/` dan `hotspot_raw/` berasal dari
  sumber lain (NASA FIRMS) dan dikelola tim label; lihat riwayat repo.
- Batas wilayah GADM di `features_raw/static/boundaries/` **tidak** ikut
  didistribusikan (GADM melarang redistribusi); hanya dipakai lokal.
- MCD64A1 (NASA) hanya disimpan lokal sebagai data mentah dan tidak di-track.

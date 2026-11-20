# Kontrak API APIKAH v1

Status: proposal Fase 0. Belum ada data produksi.

## Konvensi

- Base path: `/v1`
- Format sukses: `application/json` atau `application/geo+json` untuk peta.
- Format error: `{"detail": "pesan"}` dengan status 4xx/5xx.
- Waktu memakai ISO 8601 dengan zona `Asia/Jakarta` (WIB) untuk field yang ditampilkan ke pengguna. Pada Fase 0 semua `time_local` disajikan dalam WIB; pemetaan WITA/WIT menyusul bila frontend membutuhkannya.
- `horizon` menerima:
  - `d0`, `d1`, `d2`, `d3` (kompatibel frontend saat ini)
  - `h7`, `h14`, `h21` (horizon panjang)
  - bilangan bulat `0` sampai `21`
- `d0` adalah observasi hotspot aktual, bukan prediksi. Layer risiko untuk `d0` mengembalikan koleksi kosong; hotspot aktual ada di `/v1/hotspots`.
- Semua endpoint membaca `model_runs` terbaru yang berstatus `success`, kecuali dinyatakan lain.

## Endpoint

### `GET /health`

Liveness. Tidak menyentuh database.

```json
{"status": "ok", "service": "apikah-api"}
```

### `GET /v1/meta`

Metadata run terbaru.

```json
{
  "generated_at": "2026-11-20T07:15:00+07:00",
  "data_hotspot_latest_at": "2026-11-20T05:00:00+07:00",
  "model_version": "v2026.11.0",
  "data_version": "2026-11-20",
  "stale_after_hours": 24,
  "is_sample": false,
  "status": "success",
  "horizons": [1, 2, 3, 7, 14, 21]
}
```

Status:
- `200` ada run.
- `404` belum ada run.
- `503` database belum dikonfigurasi.

### `GET /v1/risk/{horizon}`

GeoJSON `FeatureCollection<Polygon>` berisi sel risiko untuk horizon terpilih.

Parameter:
- `horizon` wajib.
- `province` opsional, filter nama provinsi.
- `level` opsional, filter level minimum (1-4).

Properti tiap fitur:

```json
{
  "cell_id": 50029,
  "level": 4,
  "score": 0.62,
  "province": "Riau",
  "island": "Sumatra",
  "drivers": ["...", "...", "..."],
  "peat_pct": 88,
  "horizon_days": 1,
  "target_date": "2026-11-21"
}
```

Status:
- `200` sukses (boleh koleksi kosong bila tidak ada sel).
- `400` horizon tidak valid.
- `404` run belum ada.
- `503` database belum dikonfigurasi.

Header:
- `ETag` dari `run_id` + horizon.
- `Cache-Control: public, max-age=300, stale-while-revalidate=600`.

### `GET /v1/hotspots`

Hotspot aktual 72 jam terakhir sebagai GeoJSON `FeatureCollection<Point>`.

Parameter:
- `hours` opsional, default `72`, rentang 1-168.

Properti:

```json
{
  "time_local": "2026-11-20T13:40:00+07:00",
  "confidence": "h",
  "frp": 12.4
}
```

Status: `200`, `400`, `503`.

### `GET /v1/cells/{cell_id}`

Detail satu sel.

Parameter:
- `cell_id` wajib.
- `horizon` opsional; bila diisi, hanya horizon itu yang dikembalikan.

Respons:

```json
{
  "cell_id": 50029,
  "lat_c": 0.625,
  "lon_c": 101.375,
  "province": "Riau",
  "island": "Sumatra",
  "peat_pct": 88,
  "predictions": [
    {"horizon_days": 1, "target_date": "2026-11-21", "score": 0.62, "level": 4, "drivers": ["..."]}
  ],
  "hotspots_7d": [
    {"time_local": "2026-11-18T14:00:00+07:00", "confidence": "n", "frp": 8.1}
  ]
}
```

Status: `200`, `404`, `503`.

### `GET /v1/regions`

Peringkat wilayah untuk horizon terpilih.

Parameter:
- `level` wajib: `province` atau `kabupaten`.
- `horizon` opsional, default `1`.
- `limit` opsional, default `20`, maksimum `100`.

Respons:

```json
{
  "date": "2026-11-20",
  "horizon_days": 1,
  "level": "province",
  "regions": [
    {
      "name": "Riau",
      "max_level": 4,
      "max_score": 0.71,
      "high_count": 42,
      "very_high_count": 11,
      "cell_count": 120
    }
  ]
}
```

Status: `200`, `400`, `503`.

### `GET /v1/history`

Riwayat prediksi/observasi per sel.

Parameter:
- `cell_id` wajib.
- `from` dan `to` opsional, format `YYYY-MM-DD`, default 30 hari terakhir.
- `horizon` opsional.

Catatan Fase 0: arsip historis berada di R2 (Parquet/GeoJSON), bukan di database. Endpoint mengembalikan `501` sampai lapisan arsip diimplementasikan.

### `GET /v1/metrics`

Metrik verifikasi harian.

Parameter:
- `days` opsional, default `30`, maksimum `365`.
- `horizon` opsional.

Respons:

```json
{
  "metrics": [
    {
      "date": "2026-11-19",
      "horizon_days": 1,
      "precision": 0.64,
      "recall": 0.41,
      "f1": 0.50,
      "pr_auc": 0.38,
      "base_rate": 0.12,
      "model_version": "v2026.11.0"
    }
  ]
}
```

Status: `200`, `503`.

## Kompatibilitas frontend

Frontend saat ini memakai `d0`-`d3`. Untuk sementara:

- `d0` -> `/v1/hotspots` untuk layer aktual.
- `d1`-`d3` -> `/v1/risk/d1` sampai `/v1/risk/d3`.
- Horizon 7/14/21 ditambahkan setelah tim ML memutuskan label.

Adapter frontend disarankan berada di `frontend/src/lib/map-data.ts`, dengan fallback ke file statis terakhir bila API gagal.

## Keamanan

- Hanya `GET`.
- CORS dibatasi ke origin frontend.
- Tidak ada data sensitif di endpoint publik.
- Kunci layanan hanya di sisi server.

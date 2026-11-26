# Backend APIKAH

Status: Fase 0. Skeleton API, kontrak data, dan skema database. Belum ada data produksi dan belum ada kode lama yang diubah.

Rencana lengkap ada di `docs/backend/RENCANA_BACKEND.md` (di-ignore Git).

## Struktur

```text
backend/
  app/
    main.py                 # entrypoint FastAPI
    api/routes/             # health, meta, risk, hotspots, cells, regions, history, metrics
    core/                   # config dan koneksi database
    models/tables.py        # model SQLAlchemy
    schemas/risk.py         # skema respons Pydantic
    repositories/queries.py # query database
  contracts/
    feature_contract.json   # kontrak fitur, grid, target, anti-bocor
    api_contract.md         # kontrak endpoint
  migrations/001_init.sql   # skema Postgres/Supabase
  pipeline/run_daily.py     # skeleton pipeline harian (dry-run)
  tests/test_contract.py    # tes kontrak (stdlib)
  Dockerfile
  render.yaml
  requirements.txt
```

## Menjalankan lokal

```powershell
cd backend
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://..."
uvicorn app.main:app --reload
```

Tanpa `DATABASE_URL`, endpoint `/health` tetap hidup; endpoint data mengembalikan `503`.

## Endpoint

- `GET /health`
- `GET /v1/meta`
- `GET /v1/risk/{horizon}` (`d0`-`d3`, `h1`-`h21`, atau angka)
- `GET /v1/hotspots?hours=72`
- `GET /v1/cells/{cell_id}?horizon=`
- `GET /v1/regions?level=province&horizon=1`
- `GET /v1/history` (501 sampai arsip R2 diimplementasikan)
- `GET /v1/metrics?days=30`

Detail ada di `contracts/api_contract.md`.

## Tes

```powershell
python -m unittest discover -s backend/tests -v
python backend/pipeline/run_daily.py --dry-run
```

## Environment

| Variabel | Wajib | Keterangan |
|---|---|---|
| `DATABASE_URL` | untuk endpoint data | Postgres/Supabase |
| `SUPABASE_URL` | belum dipakai | disiapkan untuk Storage |
| `SUPABASE_SERVICE_KEY` | belum dipakai | jangan diekspos ke klien |
| `R2_PUBLIC_BASE_URL` | belum dipakai | arsip GeoJSON/Parquet |
| `CORS_ORIGINS` | tidak | default `http://localhost:5173` |
| `STALE_AFTER_HOURS` | tidak | default `24` |

## Deploy

- API: Render free web service, `render.yaml`.
- Pipeline harian: `.github/workflows/daily.yml` (saat ini dry-run).
- Database: Supabase Postgres, jalankan `migrations/001_init.sql`.
- Arsip: Cloudflare R2.

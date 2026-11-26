-- APIKAH backend schema v1 (Postgres / Supabase)
-- Fase 0. Belum dijalankan otomatis; jalankan manual lewat Supabase SQL editor
-- atau `psql "$DATABASE_URL" -f backend/migrations/001_init.sql`.

create table if not exists model_runs (
    run_id          text primary key,
    generated_at    timestamptz not null,
    data_version    text not null,
    model_version   text not null,
    status          text not null default 'success'
                    check (status in ('running', 'success', 'failed')),
    horizons        integer[] not null default '{}',
    metrics         jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now()
);

create table if not exists cell_registry (
    cell_id         bigint primary key,
    lat_c           double precision not null,
    lon_c           double precision not null,
    province        text,
    island          text,
    peat_pct        double precision,
    is_land         boolean not null default true,
    updated_at      timestamptz not null default now()
);

create table if not exists predictions_latest (
    run_id          text not null references model_runs(run_id) on delete cascade,
    target_date     date not null,
    horizon_days    integer not null check (horizon_days between 0 and 31),
    cell_id         bigint not null,
    lat_c           double precision not null,
    lon_c           double precision not null,
    score           double precision not null check (score >= 0 and score <= 1),
    level           smallint not null check (level between 1 and 4),
    province        text,
    island          text,
    peat_pct        double precision,
    drivers         jsonb not null default '[]'::jsonb,
    created_at      timestamptz not null default now(),
    primary key (run_id, horizon_days, cell_id)
);

create index if not exists idx_predictions_latest_horizon_level
    on predictions_latest (horizon_days, level);

create index if not exists idx_predictions_latest_province
    on predictions_latest (province, horizon_days);

create index if not exists idx_predictions_latest_target_date
    on predictions_latest (target_date);

create table if not exists hotspots_recent (
    id              bigserial primary key,
    observed_at     timestamptz not null,
    lat             double precision not null,
    lon             double precision not null,
    cell_id         bigint,
    confidence      text check (confidence in ('l', 'n', 'h')),
    frp             double precision,
    satellite       text,
    source          text not null default 'FIRMS_NRT',
    created_at      timestamptz not null default now()
);

create index if not exists idx_hotspots_recent_observed_at
    on hotspots_recent (observed_at desc);

create index if not exists idx_hotspots_recent_cell_id
    on hotspots_recent (cell_id, observed_at desc);

create table if not exists region_daily (
    date            date not null,
    level           text not null check (level in ('province', 'kabupaten')),
    region_name     text not null,
    horizon_days    integer not null,
    max_level       smallint not null check (max_level between 1 and 4),
    max_score       double precision not null,
    high_count      integer not null default 0,
    very_high_count integer not null default 0,
    cell_count      integer not null default 0,
    model_version   text,
    primary key (date, level, region_name, horizon_days)
);

create index if not exists idx_region_daily_lookup
    on region_daily (date desc, level, horizon_days);

create table if not exists metrics_daily (
    date            date not null,
    horizon_days    integer not null,
    model_version   text not null,
    precision       double precision,
    recall          double precision,
    f1              double precision,
    pr_auc          double precision,
    base_rate       double precision,
    n_positive      integer,
    n_predicted     integer,
    created_at      timestamptz not null default now(),
    primary key (date, horizon_days, model_version)
);

create index if not exists idx_metrics_daily_lookup
    on metrics_daily (date desc, horizon_days);

-- Retensi: predictions_latest hanya menyimpan run terbaru.
-- Arsip harian disimpan di R2 sebagai GeoJSON/Parquet.
-- region_daily dan metrics_daily boleh disimpan lebih lama karena kecil.

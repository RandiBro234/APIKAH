"""Konfigurasi backend dari environment.

Tidak ada nilai rahasia yang disimpan di repo. Semua kunci dibaca dari
environment variable (Render, GitHub Actions, atau file .env lokal).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _normalize_database_url(value: str) -> str:
    """Pakai driver psycopg 3 untuk URL Supabase/Render biasa."""
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    supabase_url: str
    supabase_service_key: str
    r2_public_base_url: str
    cors_origins: tuple[str, ...]
    stale_after_hours: int
    api_title: str = "APIKAH API"
    api_version: str = "0.1.0"


def load_settings() -> Settings:
    return Settings(
        database_url=_normalize_database_url(os.getenv("DATABASE_URL", "")),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        r2_public_base_url=os.getenv("R2_PUBLIC_BASE_URL", ""),
        cors_origins=_csv(os.getenv("CORS_ORIGINS", "http://localhost:5173")),
        stale_after_hours=int(os.getenv("STALE_AFTER_HOURS", "24")),
    )


settings = load_settings()

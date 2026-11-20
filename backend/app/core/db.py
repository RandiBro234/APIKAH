"""Koneksi database dan dependency FastAPI."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

engine = (
    create_engine(settings.database_url, pool_pre_ping=True)
    if settings.database_url
    else None
)
SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, autocommit=False)
    if engine is not None
    else None
)


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database belum dikonfigurasi")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

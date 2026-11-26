"""Entrypoint FastAPI APIKAH."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import cells, health, history, hotspots, meta, metrics, regions, risk
from .core.config import settings

app = FastAPI(title=settings.api_title, version=settings.api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)

for router in (
    meta.router,
    risk.router,
    hotspots.router,
    cells.router,
    regions.router,
    history.router,
    metrics.router,
):
    app.include_router(router, prefix="/v1")

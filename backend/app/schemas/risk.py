"""Skema respons API."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal[1, 2, 3, 4]


class HealthResponse(BaseModel):
    status: str
    service: str


class MetaResponse(BaseModel):
    generated_at: str
    data_hotspot_latest_at: str | None
    model_version: str
    data_version: str
    stale_after_hours: int
    is_sample: bool
    status: str
    horizons: list[int]


class RiskProperties(BaseModel):
    cell_id: int
    level: RiskLevel
    score: float = Field(ge=0.0, le=1.0)
    province: str | None
    island: str | None
    drivers: list[str]
    peat_pct: float | None
    horizon_days: int
    target_date: date


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class RiskFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int
    properties: RiskProperties
    geometry: PolygonGeometry


class RiskFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[RiskFeature]


class HotspotProperties(BaseModel):
    time_local: str
    confidence: Literal["l", "n", "h"] | None
    frp: float | None


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float]


class HotspotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: HotspotProperties
    geometry: PointGeometry


class HotspotFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[HotspotFeature]


class CellPrediction(BaseModel):
    horizon_days: int
    target_date: date
    score: float
    level: RiskLevel
    drivers: list[str]


class CellHotspot(BaseModel):
    time_local: str
    confidence: Literal["l", "n", "h"] | None
    frp: float | None


class CellDetail(BaseModel):
    cell_id: int
    lat_c: float
    lon_c: float
    province: str | None
    island: str | None
    peat_pct: float | None
    predictions: list[CellPrediction]
    hotspots_7d: list[CellHotspot]


class RegionRecord(BaseModel):
    name: str
    max_level: RiskLevel
    max_score: float
    high_count: int
    very_high_count: int
    cell_count: int


class RegionResponse(BaseModel):
    date: date
    horizon_days: int
    level: Literal["province", "kabupaten"]
    regions: list[RegionRecord]


class MetricRecord(BaseModel):
    date: date
    horizon_days: int
    precision: float | None
    recall: float | None
    f1: float | None
    pr_auc: float | None
    base_rate: float | None
    model_version: str


class MetricsResponse(BaseModel):
    metrics: list[MetricRecord]

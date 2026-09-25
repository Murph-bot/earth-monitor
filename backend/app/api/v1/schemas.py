"""API response/request models — the OpenAPI contract.

These models are what the generated typed client (packages/shared) will be
built from; field names here are public API. GeoJSON geometries travel as
plain dicts (parsed from ST_AsGeoJSON) — the contract is GeoJSON, not WKB.
"""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


# --- sensors ---------------------------------------------------------------


class SensorOut(BaseModel):
    id: str
    name: str
    kind: str
    provider: str
    resolution_m: float | None
    revisit_days: float | None
    enabled: bool


class CollectionOut(BaseModel):
    id: str
    catalog: str
    stac_url: str
    processing_level: str


class BandOut(BaseModel):
    name: str
    asset_key: str
    kind: str
    resolution_m: float | None
    scale: float
    dn_offset: float


class SensorDetail(SensorOut):
    license_text: str
    collections: list[CollectionOut]
    bands: list[BandOut]


# --- aois ------------------------------------------------------------------


class AoiCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    geojson: dict[str, Any]
    is_public: bool = False

    @field_validator("geojson")
    @classmethod
    def _is_area(cls, g: dict[str, Any]) -> dict[str, Any]:
        if g.get("type") not in ("Polygon", "MultiPolygon") or not g.get("coordinates"):
            raise ValueError("geojson must be a Polygon or MultiPolygon with coordinates")
        return g


class AoiUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_public: bool | None = None


class Bbox(BaseModel):
    minx: float
    miny: float
    maxx: float
    maxy: float


class AoiOut(BaseModel):
    id: uuid.UUID
    name: str
    is_public: bool
    area_m2: float
    bbox: Bbox
    created_at: datetime


class SensorStateOut(BaseModel):
    sensor_id: str
    last_checked_at: datetime | None
    last_scene_at: datetime | None


class AoiDetail(AoiOut):
    geom: dict[str, Any]
    sensor_state: list[SensorStateOut]


# --- scenes ----------------------------------------------------------------


class SceneSummary(BaseModel):
    id: int
    scene_key: str
    sensor_id: str
    collection_id: str
    acquired_at: datetime
    cloud_cover: float | None
    coverage: float  # fraction of the AOI this scene covers (0,1]


class SceneDetail(BaseModel):
    id: int
    scene_key: str
    sensor_id: str
    collection_id: str
    acquired_at: datetime
    cloud_cover: float | None
    epsg: int | None
    footprint: dict[str, Any]
    bbox: Bbox
    assets: dict[str, Any]
    properties: dict[str, Any]


# --- metrics ---------------------------------------------------------------


class MetricPoint(BaseModel):
    date: date
    acquired_at: datetime
    scene_id: int
    value: float
    valid_pixel_pct: float


class MetricSeries(BaseModel):
    metric_name: str
    sensor_id: str
    unit: str
    points: list[MetricPoint]


class MetricsResponse(BaseModel):
    aoi_id: uuid.UUID
    series: list[MetricSeries]

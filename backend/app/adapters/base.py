"""The sensor adapter seam — the abstraction that survives provider churn.

ADR-0001 made multi-catalog access load-bearing; this module is where it
lives. An adapter knows three things about its sensor:

  search        — find scenes over an AOI (STAC metadata only, no pixels)
  read          — fetch pixel windows clipped to the AOI (windowed COG reads)
  quality_mask  — judge pixels (sensor-specific: SCL, QA_PIXEL, orbit rules)

Everything downstream (metrics, ingestion, API) works against these types
and never touches a catalog.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
from affine import Affine
from numpy.typing import NDArray

type GeoJSONGeom = dict[str, Any]


class AdapterError(Exception):
    """Adapter failures: catalog unreachable, malformed item, unreadable asset."""


@dataclass(frozen=True)
class BandSpec:
    """One readable band or quality layer of a sensor.

    `name` is what analysis modules request; `asset_key` is what the
    catalog's STAC items call it. scale/dn_offset convert stored DN to physical
    units (S2 DN→reflectance; Landsat ST DN→kelvin); a STAC item's
    raster:bands extension may override them per scene.
    """

    name: str
    asset_key: str
    description: str
    resolution_m: float
    kind: Literal["reflectance", "thermal", "quality", "sar"]
    scale: float = 1.0
    dn_offset: float = 0.0  # "offset" is a reserved SQL word — column matches this name


@dataclass(frozen=True)
class SceneMeta:
    """Metadata handle for one acquisition. Cheap to list — no pixels."""

    scene_id: str
    sensor_id: str
    collection: str
    catalog: str
    acquired_at: datetime
    bbox: tuple[float, float, float, float]
    geometry: GeoJSONGeom
    cloud_cover: float | None  # catalog-reported %, NOT our mask
    epsg: int | None
    assets: dict[str, str]  # asset_key -> href
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BandWindow:
    """One band clipped to an AOI, on that band's native grid."""

    array: NDArray[np.generic]
    transform: Affine
    epsg: int


@dataclass(frozen=True)
class SceneWindow:
    """All requested bands of one scene, clipped to one AOI.

    Bands may differ in shape/CRS (S2 mixes 10/20/60 m grids); consumers must
    align via `quality_mask`, which returns a mask on a reference band's grid.
    An empty `bands` dict means the scene does not overlap the AOI's data area.
    """

    scene: SceneMeta
    aoi: GeoJSONGeom
    bands: dict[str, BandWindow]


class SensorAdapter(ABC):
    sensor_id: str
    catalog: str
    collections: tuple[str, ...]
    # band the quality_mask needs in the window (None = no quality band;
    # mask then means "inside the AOI polygon" only)
    mask_band: str | None = None

    @abstractmethod
    def search(
        self,
        aoi: GeoJSONGeom,
        start: date,
        end: date,
        *,
        max_cloud_cover: float | None = None,
        limit: int | None = None,
    ) -> list[SceneMeta]:
        """Find scenes intersecting `aoi` in [start, end].

        An empty list is a valid answer (no acquisitions) — never an error.
        API failures retry with backoff, then raise AdapterError.
        """

    @abstractmethod
    def read(
        self,
        scene: SceneMeta,
        aoi: GeoJSONGeom,
        bands: Sequence[str],
    ) -> SceneWindow:
        """Windowed read of `bands` clipped to `aoi`, each on its native grid.

        The AOI arrives in EPSG:4326 and is reprojected per scene — this is
        what makes one polygon work across UTM zones and tile boundaries.
        """

    @abstractmethod
    def quality_mask(self, window: SceneWindow) -> BandWindow:
        """Boolean mask (True = valid pixel) on the finest science band's grid."""

    @abstractmethod
    def band_registry(self) -> list[BandSpec]:
        """Ground truth for what this sensor can read."""

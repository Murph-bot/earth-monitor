"""Landsat 8/9 adapter — STUB, planned for Phase 5 expansion.

Catalog: Planetary Computer `landsat-c2-l2` (SAS-signed HTTPS; the canonical
`usgs-landsat` S3 bucket is requester-pays — banned per ADR-0001). Fallback:
USGS LandsatLook STAC.

Masking: `qa_pixel` bitfield (fill/dilated-cloud/cirrus/cloud/shadow/snow).
Thermal: `lwir11` (ST_B10) DN → kelvin via the item's raster scale/offset —
never hardcode; Landsat L2 uses scale 0.00341802, offset 149.0.
"""

from collections.abc import Sequence
from datetime import date

from app.adapters.base import (
    BandSpec,
    BandWindow,
    GeoJSONGeom,
    SceneMeta,
    SceneWindow,
    SensorAdapter,
)

BANDS: list[BandSpec] = [
    BandSpec("red", "red", "OLI B04", 30, "reflectance", scale=2.75e-5, offset=-0.2),
    BandSpec("nir", "nir08", "OLI B05", 30, "reflectance", scale=2.75e-5, offset=-0.2),
    BandSpec("swir16", "swir16", "OLI B06", 30, "reflectance", scale=2.75e-5, offset=-0.2),
    BandSpec(
        "lwir", "lwir11", "TIRS B10 surface temp", 100, "thermal", scale=0.00341802, offset=149.0
    ),
    BandSpec("qa_pixel", "qa_pixel", "USGS QA bitfield", 30, "quality"),
]


class LandsatAdapter(SensorAdapter):
    sensor_id = "landsat-8-9"
    catalog = "planetary-computer"
    collections = ("landsat-c2-l2",)

    def band_registry(self) -> list[BandSpec]:
        return list(BANDS)

    def search(self, aoi: GeoJSONGeom, start: date, end: date, **kw: object) -> list[SceneMeta]:
        raise NotImplementedError("Phase 5: MPC landsat-c2-l2 search + SAS signing")

    def read(self, scene: SceneMeta, aoi: GeoJSONGeom, bands: Sequence[str]) -> SceneWindow:
        raise NotImplementedError("Phase 5: windowed reads on SAS-signed hrefs")

    def quality_mask(self, window: SceneWindow) -> BandWindow:
        raise NotImplementedError("Phase 5: QA_PIXEL bit decode")

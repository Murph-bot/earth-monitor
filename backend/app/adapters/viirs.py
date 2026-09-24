"""VIIRS adapter — STUB, planned for Phase 5 expansion (MODIS's successor).

Catalog: NASA Earthdata Cloud (LP DAAC), e.g. VNP09GA daily surface
reflectance at ~500 m/1 km; auth via Earthdata login. MODIS collections exist
for historical continuity but Aqua/Terra are decommissioning 2026-27 — do not
build forward-looking features on them.

Role in the system: daily regional context and fire alerts, not AOI-scale
measurement (375-750 m pixels).
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
    BandSpec("red", "SurfReflect_I1", "I1 640nm", 375, "reflectance"),
    BandSpec("nir", "SurfReflect_I2", "I2 865nm", 375, "reflectance"),
    BandSpec("qf", "SurfReflect_QF2", "quality flags", 375, "quality"),
]


class ViirsAdapter(SensorAdapter):
    sensor_id = "viirs"
    catalog = "nasa-earthdata"
    collections = ("VNP09GA",)

    def band_registry(self) -> list[BandSpec]:
        return list(BANDS)

    def search(self, aoi: GeoJSONGeom, start: date, end: date, **kw: object) -> list[SceneMeta]:
        raise NotImplementedError("Phase 5: CMR-STAC search with EDL auth")

    def read(self, scene: SceneMeta, aoi: GeoJSONGeom, bands: Sequence[str]) -> SceneWindow:
        raise NotImplementedError("Phase 5: LPCLOUD COG reads with EDL token")

    def quality_mask(self, window: SceneWindow) -> BandWindow:
        raise NotImplementedError("Phase 5: QF bit decode")

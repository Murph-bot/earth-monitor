"""Sentinel-1 SAR adapter — STUB, planned for Phase 5 expansion.

Search: Earth Search `sentinel-1-grd` (anonymous reads verified) or CDSE.
Pixels: analysis-ready RTC γ⁰ — ASF HyP3 on-demand (primary, funded/stable)
or MPC `sentinel-1-rtc` (opportunistic, unmaintained). We never self-process
GRD→RTC; terrain correction is a solved problem we rent for free.

Bands: vv, vh (C-band IW). Metrics use backscatter change (dB), not indices.
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
    BandSpec("vv", "vv", "VV polarization γ⁰", 10, "sar"),
    BandSpec("vh", "vh", "VH polarization γ⁰", 10, "sar"),
]


class Sentinel1Adapter(SensorAdapter):
    sensor_id = "sentinel-1"
    catalog = "earth-search"
    collections = ("sentinel-1-grd",)

    def band_registry(self) -> list[BandSpec]:
        return list(BANDS)

    def search(self, aoi: GeoJSONGeom, start: date, end: date, **kw: object) -> list[SceneMeta]:
        raise NotImplementedError("Phase 5: GRD search; RTC scenes via HyP3/MPC")

    def read(self, scene: SceneMeta, aoi: GeoJSONGeom, bands: Sequence[str]) -> SceneWindow:
        raise NotImplementedError("Phase 5: reads RTC COGs; orbit direction is metadata")

    def quality_mask(self, window: SceneWindow) -> BandWindow:
        raise NotImplementedError("Phase 5: border-noise + range-valid masking")

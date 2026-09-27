"""Live Planetary Computer verification — real STAC search, anonymous SAS
signing, real COG windowed read, real surface temperature.
Skipped by default (network); run with:
    EM_INTEGRATION=1 uv run pytest tests/adapters/test_landsat_live.py -v
"""

import os
from datetime import date

import pytest

from app.adapters.landsat import LandsatAdapter
from app.analysis.indices import SurfaceTemperature

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("EM_INTEGRATION") != "1",
        reason="live catalog test; set EM_INTEGRATION=1",
    ),
]

# farmland in the Thessaly plain; 2026-09-01 was a 0.07 % cloud Landsat 9 pass
AOI = {
    "type": "Polygon",
    "coordinates": [
        [[22.60, 39.50], [22.64, 39.50], [22.64, 39.53], [22.60, 39.53], [22.60, 39.50]]
    ],
}


def test_search_read_and_temperature() -> None:
    adapter = LandsatAdapter()
    scenes = adapter.search(AOI, date(2026, 8, 30), date(2026, 9, 2))
    assert scenes, "expected a Landsat pass over Thessaly around 2026-09-01"
    assert all(s.scene_id.startswith(("LC08", "LC09")) for s in scenes)

    scene = min(scenes, key=lambda s: s.cloud_cover or 100)
    window = adapter.read(scene, AOI, ["lwir", "qa_pixel"])
    assert {"lwir", "qa_pixel"} <= set(window.bands)
    celsius = SurfaceTemperature().compute(window, adapter.quality_mask(window))
    assert celsius is not None and 10 < celsius < 70, celsius

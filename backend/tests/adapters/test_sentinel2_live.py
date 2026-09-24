"""Live Earth Search verification — real STAC search + real COG windowed read.

Skipped by default (network); run with:
    EM_INTEGRATION=1 uv run pytest tests/adapters/test_sentinel2_live.py -v
"""

import os
from datetime import date

import numpy as np
import pytest

from app.adapters.sentinel2 import Sentinel2Adapter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("EM_INTEGRATION") != "1",
        reason="live catalog test; set EM_INTEGRATION=1",
    ),
]

# ~2 km box over farmland in the Thessaly plain, Greece (UTM 34N country).
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [22.70, 40.55],
            [22.72, 40.55],
            [22.72, 40.57],
            [22.70, 40.57],
            [22.70, 40.55],
        ]
    ],
}


def test_search_and_read_real_scene() -> None:
    adapter = Sentinel2Adapter()
    scenes = adapter.search(AOI, date(2026, 9, 1), date(2026, 9, 24), max_cloud_cover=30)
    assert scenes, "expected ≥1 Sentinel-2 scene over Thessaly in Sept 2026"
    assert all(s.collection == "sentinel-2-c1-l2a" for s in scenes)

    scene = scenes[0]
    window = adapter.read(scene, AOI, bands=["red", "nir", "scl"])
    assert {"red", "nir", "scl"} <= set(window.bands), "scene assets missing bands"

    red = window.bands["red"]
    assert red.array.ndim == 2 and red.array.size > 0
    assert red.epsg in (32634, 32635)  # Greece straddles UTM 34N/35N

    mask = adapter.quality_mask(window)
    assert mask.array.shape == red.array.shape
    assert mask.array.dtype == bool

    valid_pct = float(np.mean(mask.array))
    assert 0.0 <= valid_pct <= 1.0
    print(
        f"\nscene={scene.scene_id} cloud={scene.cloud_cover}% "
        f"window={red.array.shape} valid={valid_pct:.1%}"
    )

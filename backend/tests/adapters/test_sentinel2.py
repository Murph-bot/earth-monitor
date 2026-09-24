"""Sentinel-2 adapter unit tests — no network.

The two things worth testing here: SCL class → validity mapping (domain
knowledge, easy to get wrong) and 20 m→10 m mask alignment (the subtle part —
a cloudy SCL cell must kill the four finer cells it covers).
"""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest
from affine import Affine

from app.adapters.base import AdapterError, BandWindow, SceneMeta, SceneWindow
from app.adapters.registry import all_adapters, get_adapter
from app.adapters.sentinel2 import BANDS, VALID_SCL_CLASSES, Sentinel2Adapter

X0, Y0 = 500000.0, 4100000.0  # arbitrary UTM origin

_SCENE = SceneMeta(
    scene_id="S2B_T34SGH_20260920",
    sensor_id="sentinel-2",
    collection="sentinel-2-c1-l2a",
    catalog="earth-search",
    acquired_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
    bbox=(23.0, 39.0, 24.0, 40.0),
    geometry={"type": "Polygon", "coordinates": []},
    cloud_cover=12.5,
    epsg=32634,
    assets={"red": "https://example/red.tif", "scl": "https://example/scl.tif"},
)


def _window(array: np.ndarray, pixel: float) -> BandWindow:
    return BandWindow(
        array=array,
        transform=Affine(pixel, 0, X0, 0, -pixel, Y0),
        epsg=32634,
    )


def _scene_window(scl: np.ndarray, scl_px: float, science_px: float) -> SceneWindow:
    science_shape = (
        int(scl.shape[0] * scl_px / science_px),
        int(scl.shape[1] * scl_px / science_px),
    )
    return SceneWindow(
        scene=_SCENE,
        aoi={"type": "Polygon", "coordinates": []},
        bands={
            "red": _window(np.zeros(science_shape, dtype=np.uint16), science_px),
            "scl": _window(scl, scl_px),
        },
    )


def test_scl_valid_classes() -> None:
    # 4 veg, 5 bare, 6 water, 7 unclassified are valid; 0/3/8/9/10/11 are not
    scl = np.array([[0, 3, 4], [5, 6, 7], [8, 9, 10]], dtype=np.uint8)
    adapter = Sentinel2Adapter()
    mask = adapter.quality_mask(_scene_window(scl, scl_px=10, science_px=10))

    expected = np.array([[False, False, True], [True, True, True], [False, False, False]])
    np.testing.assert_array_equal(mask.array, expected)
    assert VALID_SCL_CLASSES == frozenset({4, 5, 6, 7})


def test_mask_aligns_20m_scl_to_10m_grid() -> None:
    # 2x2 SCL at 20 m over the same extent as 4x4 red at 10 m
    scl = np.array([[4, 8], [5, 9]], dtype=np.uint8)  # valid, cloud / valid, cloud
    adapter = Sentinel2Adapter()
    mask = adapter.quality_mask(_scene_window(scl, scl_px=20, science_px=10))

    # each SCL cell covers a 2x2 block on the 10 m grid
    expected = np.array(
        [
            [True, True, False, False],
            [True, True, False, False],
            [True, True, False, False],
            [True, True, False, False],
        ]
    )
    np.testing.assert_array_equal(mask.array, expected)
    assert mask.transform.a == pytest.approx(10.0)


def test_quality_mask_requires_scl() -> None:
    window = SceneWindow(
        scene=_SCENE,
        aoi={},
        bands={"red": _window(np.zeros((2, 2)), 10)},
    )
    with pytest.raises(AdapterError, match="scl"):
        Sentinel2Adapter().quality_mask(window)


def test_to_scene_parses_stac_item() -> None:
    item: dict[str, Any] = {
        "id": "S2B_T34SGH_20260920T090559",
        "collection": "sentinel-2-c1-l2a",
        "bbox": [23.0, 39.0, 24.0, 40.0],
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "properties": {
            "datetime": "2026-09-20T09:05:59.024Z",
            "eo:cloud_cover": 12.5,
            "proj:epsg": 32634,
        },
        "assets": {
            "red": {"href": "https://example/red.tif"},
            "no_href_asset": {},  # must be dropped
        },
    }
    scene = Sentinel2Adapter._to_scene(item)

    assert scene.scene_id == "S2B_T34SGH_20260920T090559"
    assert scene.acquired_at.year == 2026
    assert scene.cloud_cover == 12.5
    assert scene.epsg == 32634
    assert scene.assets == {"red": "https://example/red.tif"}


def test_registry() -> None:
    assert isinstance(get_adapter("sentinel-2"), Sentinel2Adapter)
    assert "sentinel-2" in all_adapters()
    with pytest.raises(KeyError, match="modis"):
        get_adapter("modis")


def test_band_registry_covers_pipeline_bands() -> None:
    names = {b.name for b in BANDS}
    assert {"red", "nir", "scl"} <= names  # NDVI + mask minimum

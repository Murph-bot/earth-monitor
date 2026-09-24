"""Unit tests for spectral index modules — synthetic windows, no DB/COG."""

import numpy as np
import pytest
from affine import Affine

from app.adapters.base import BandWindow, GeoJSONGeom, SceneMeta, SceneWindow
from app.analysis.base import AnalysisError
from app.analysis.indices import Ndvi, Ndwi

AOI: GeoJSONGeom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
T = Affine(10, 0, 0, 0, -10, 0)


def _scene() -> SceneMeta:
    from datetime import UTC, datetime

    return SceneMeta(
        scene_id="S",
        sensor_id="sentinel-2",
        collection="sentinel-2-c1-l2a",
        catalog="earth-search",
        acquired_at=datetime(2026, 9, 24, tzinfo=UTC),
        bbox=(0, 0, 1, 1),
        geometry=AOI,
        cloud_cover=None,
        epsg=32634,
        assets={},
    )


def _window(bands: dict[str, np.ndarray]) -> SceneWindow:
    return SceneWindow(
        scene=_scene(),
        aoi=AOI,
        bands={n: BandWindow(array=a, transform=T, epsg=32634) for n, a in bands.items()},
    )


def _mask(arr: np.ndarray) -> BandWindow:
    return BandWindow(array=arr.astype(bool), transform=T, epsg=32634)


def test_ndvi_mean_over_valid_pixels() -> None:
    # red=0.2, nir=0.6 everywhere -> ndvi = 0.5; one pixel invalid
    bands = {
        "red": np.full((2, 2), 0.2, dtype=np.float32),
        "nir": np.full((2, 2), 0.6, dtype=np.float32),
    }
    mask = _mask(np.array([[1, 1], [1, 0]]))
    assert Ndvi().compute(_window(bands), mask) == pytest.approx(0.5)


def test_ndwi_mcfeeters() -> None:
    bands = {
        "green": np.full((2, 2), 0.1, dtype=np.float32),
        "nir": np.full((2, 2), 0.6, dtype=np.float32),
    }
    mask = _mask(np.ones((2, 2)))
    assert Ndwi().compute(_window(bands), mask) == pytest.approx(-0.5 / 0.7)


def test_all_invalid_returns_none() -> None:
    bands = {
        "red": np.full((2, 2), 0.2),
        "nir": np.full((2, 2), 0.6),
    }
    assert Ndvi().compute(_window(bands), _mask(np.zeros((2, 2)))) is None


def test_missing_band_returns_none() -> None:
    bands = {"red": np.full((2, 2), 0.2)}  # nir absent (asset missing)
    assert Ndvi().compute(_window(bands), _mask(np.ones((2, 2)))) is None


def test_negative_reflectance_excluded() -> None:
    # DN-offset artifacts push edge pixels below zero; a denominator near zero
    # would explode the ratio. Non-physical pixels are dropped from the mean.
    bands = {
        "red": np.array([[0.2, -0.05], [-0.05, 0.2]], dtype=np.float32),
        "nir": np.array([[0.6, 0.06], [0.06, 0.6]], dtype=np.float32),
    }
    mask = _mask(np.ones((2, 2)))
    assert Ndvi().compute(_window(bands), mask) == pytest.approx(0.5)


def test_grid_mismatch_raises() -> None:
    bands = {
        "red": np.full((4, 4), 0.2),  # 10 m
        "nir": np.full((2, 2), 0.6),  # module asked for mixed grids — a bug
    }
    with pytest.raises(AnalysisError):
        Ndvi().compute(_window(bands), _mask(np.ones((4, 4))))

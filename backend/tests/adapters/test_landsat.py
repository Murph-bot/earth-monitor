"""Landsat 8/9 adapter unit tests — no network.

Worth testing: the QA_PIXEL bit decode (domain knowledge, easy to get
wrong), STAC item parsing from Planetary Computer, and the surface
temperature module's kelvin → °C masked mean.
"""

from datetime import UTC, datetime

import numpy as np
import pytest
from affine import Affine

from app.adapters.base import BandWindow, SceneMeta, SceneWindow
from app.adapters.landsat import LandsatAdapter
from app.adapters.registry import get_adapter
from app.analysis.indices import SurfaceTemperature
from app.analysis.registry import modules_for

T = Affine(30, 0, 500000.0, 0, -30, 4400000.0)

_SCENE = SceneMeta(
    scene_id="LC09_L2SP_183033_20260901_02_T1",
    sensor_id="landsat-8-9",
    collection="landsat-c2-l2",
    catalog="planetary-computer",
    acquired_at=datetime(2026, 9, 1, 9, 4, tzinfo=UTC),
    bbox=(22.0, 39.0, 23.0, 40.0),
    geometry={"type": "Polygon", "coordinates": []},
    cloud_cover=0.07,
    epsg=32634,
    assets={},
)

CLEAR, WATER = 1 << 6, 1 << 7
FILL, DILATED, CIRRUS, CLOUD, SHADOW, SNOW = (1 << b for b in range(6))


def _window(**bands: np.ndarray) -> SceneWindow:
    return SceneWindow(
        scene=_SCENE,
        aoi={"type": "Polygon", "coordinates": []},
        bands={k: BandWindow(v, T, 32634) for k, v in bands.items()},
    )


def test_qa_pixel_masks_fill_cloud_shadow_snow() -> None:
    qa = np.array(
        [[CLEAR, CLEAR | WATER, FILL, DILATED], [CIRRUS, CLOUD, SHADOW, SNOW]], dtype=np.uint16
    )
    lwir = np.full(qa.shape, 300.0, dtype=np.float32)
    mask = LandsatAdapter().quality_mask(_window(lwir=lwir, qa_pixel=qa))
    assert mask.array.tolist() == [[True, True, False, False], [False, False, False, False]]


def test_surface_temperature_is_masked_mean_in_celsius() -> None:
    lwir = np.array([[300.0, 310.0], [273.15, 999.0]], dtype=np.float32)
    mask = BandWindow(np.array([[True, True], [True, False]]), T, 32634)
    value = SurfaceTemperature().compute(_window(lwir=lwir), mask)
    assert value == pytest.approx((26.85 + 36.85 + 0.0) / 3, abs=1e-4)


def test_surface_temperature_none_when_fully_masked() -> None:
    lwir = np.full((2, 2), 300.0, dtype=np.float32)
    mask = BandWindow(np.zeros((2, 2), dtype=bool), T, 32634)
    assert SurfaceTemperature().compute(_window(lwir=lwir), mask) is None


def test_to_scene_parses_planetary_computer_item() -> None:
    item = {
        "id": "LC09_L2SP_183033_20260901_02_T1",
        "collection": "landsat-c2-l2",
        "bbox": [21.9, 38.9, 24.6, 40.9],
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[21.9, 38.9], [24.6, 38.9], [24.6, 40.9], [21.9, 38.9]]],
        },
        "properties": {
            "datetime": "2026-09-01T09:04:12.5Z",
            "eo:cloud_cover": 0.07,
            "proj:code": "EPSG:32634",
            "platform": "landsat-9",
        },
        "assets": {"lwir11": {"href": "https://landsateuwest.blob.core.windows.net/x/ST_B10.TIF"}},
    }
    scene = LandsatAdapter._to_scene(item)
    assert scene.sensor_id == "landsat-8-9"
    assert scene.catalog == "planetary-computer"
    assert scene.epsg == 32634
    assert scene.cloud_cover == 0.07
    assert scene.acquired_at == datetime(2026, 9, 1, 9, 4, 12, 500000, tzinfo=UTC)
    assert scene.assets["lwir11"].endswith("ST_B10.TIF")


def test_landsat_registered_with_only_temperature() -> None:
    assert get_adapter("landsat-8-9").mask_band == "qa_pixel"
    assert [m.metric_name for m in modules_for("landsat-8-9")] == ["lst_mean"]
    assert "lst_mean" not in [m.metric_name for m in modules_for("sentinel-2")]


class _Resp:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, str]:
        return self._payload


def test_signing_many_hrefs_costs_one_token_request(monkeypatch: pytest.MonkeyPatch) -> None:
    # Planetary Computer rate-limits its SAS endpoint (429 observed signing per
    # href); a sweep must reuse one collection token until it nears expiry
    from app.adapters import landsat

    calls: list[str] = []

    def fake_get(url: str, **kw: object) -> _Resp:
        calls.append(url)
        return _Resp({"token": "sv=1&sig=abc", "msft:expiry": "2099-01-01T00:00:00Z"})

    monkeypatch.setattr(landsat.requests, "get", fake_get)
    monkeypatch.setattr(landsat, "_token_cache", {})
    hrefs = [f"https://landsateuwest.blob.core.windows.net/c/{i}.TIF" for i in range(20)]
    signed = [landsat._sign(h) for h in hrefs]

    assert len(calls) == 1
    assert signed[3] == "https://landsateuwest.blob.core.windows.net/c/3.TIF?sv=1&sig=abc"

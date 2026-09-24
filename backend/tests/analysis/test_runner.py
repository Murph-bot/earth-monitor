"""Analysis runner integration — fake pixels through the real DB path.

FakeReadAdapter subclasses Sentinel2Adapter so quality_mask is the real SCL
logic; only search/read are faked (no network).
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import numpy as np
import psycopg
import pytest
from affine import Affine
from rasterio.warp import transform_bounds

from app.adapters.base import BandWindow, GeoJSONGeom, SceneMeta, SceneWindow
from app.adapters.sentinel2 import Sentinel2Adapter
from app.analysis.runner import analyze_pending
from app.ingest.pipeline import ingest_sensor

AOI: GeoJSONGeom = {
    "type": "Polygon",
    "coordinates": [[[22.7, 40.55], [22.72, 40.55], [22.72, 40.57], [22.7, 40.57], [22.7, 40.55]]],
}
COVERING: GeoJSONGeom = {
    "type": "Polygon",
    "coordinates": [[[22.6, 40.5], [22.8, 40.5], [22.8, 40.6], [22.6, 40.6], [22.6, 40.5]]],
}
# 4x4 px at 10 m anchored 200 m inside the AOI's UTM-34N bounds — corner-
# anchoring lands pixels exactly on the polygon edge, which pixel-center
# rasterization excludes. The window must sit fully inside the polygon.
_MINX, _, _, _MAXY = transform_bounds("EPSG:4326", "EPSG:32634", 22.7, 40.55, 22.72, 40.57)
T = Affine(10, 0, _MINX + 200, 0, -10, _MAXY - 200)


def _meta(scene_id: str) -> SceneMeta:
    return SceneMeta(
        scene_id=scene_id,
        sensor_id="sentinel-2",
        collection="sentinel-2-c1-l2a",
        catalog="earth-search",
        acquired_at=datetime(2026, 9, 24, 9, 30, tzinfo=UTC),
        bbox=(22.6, 40.5, 22.8, 40.6),
        geometry=COVERING,
        cloud_cover=3.0,
        epsg=32634,
        assets={},
        properties={},
    )


def _window(scene: SceneMeta, aoi: GeoJSONGeom, scl_class: int = 4) -> SceneWindow:
    """4x4 synthetic window: red=0.2, green=0.1, nir=0.6 (physical units —
    the fake emulates post-scaling adapter output)."""
    bands = {
        "red": BandWindow(np.full((4, 4), 0.2, dtype=np.float32), T, 32634),
        "green": BandWindow(np.full((4, 4), 0.1, dtype=np.float32), T, 32634),
        "nir": BandWindow(np.full((4, 4), 0.6, dtype=np.float32), T, 32634),
        "scl": BandWindow(np.full((4, 4), scl_class, dtype=np.uint8), T, 32634),
    }
    return SceneWindow(scene=scene, aoi=aoi, bands=bands)


class FakeReadAdapter(Sentinel2Adapter):
    def __init__(self, metas: list[SceneMeta], scl_class: int = 4) -> None:
        self._metas = metas
        self._scl = scl_class

    def search(self, aoi, start, end, **kw):  # type: ignore[no-untyped-def]
        return list(self._metas)

    def read(self, scene: SceneMeta, aoi: GeoJSONGeom, bands: Sequence[str]) -> SceneWindow:
        w = _window(scene, aoi, self._scl)
        return SceneWindow(
            scene=scene, aoi=aoi, bands={b: w.bands[b] for b in bands if b in w.bands}
        )


@pytest.fixture
def aoi_id(clean: psycopg.Connection) -> str:
    user_id = clean.execute(
        "INSERT INTO users (email) VALUES (%s) RETURNING id", (f"{uuid.uuid4()}@t.dev",)
    ).fetchone()[0]
    return str(
        clean.execute(
            """INSERT INTO aois (user_id, name, geom, area_m2)
               VALUES (%s, 'analysis test', ST_Multi(ST_GeomFromGeoJSON(%s)),
                       ST_Area(ST_GeomFromGeoJSON(%s)::geography))
               RETURNING id""",
            (user_id, json.dumps(AOI), json.dumps(AOI)),
        ).fetchone()[0]
    )


def test_ingest_writes_metrics(db: psycopg.Connection, aoi_id: str) -> None:
    stats = ingest_sensor(db, FakeReadAdapter([_meta("S1")]), backfill_days=30, overlap_hours=48)
    assert stats.metrics_written == 2  # ndvi_mean + ndwi_mean

    rows = dict(
        db.execute("SELECT metric_name, value FROM metrics WHERE aoi_id = %s", (aoi_id,)).fetchall()
    )
    assert rows["ndvi_mean"] == pytest.approx(0.5)
    assert rows["ndwi_mean"] == pytest.approx(-0.5 / 0.7)
    pct = db.execute(
        "SELECT valid_pixel_pct FROM metrics WHERE aoi_id = %s LIMIT 1", (aoi_id,)
    ).fetchone()[0]
    assert pct == pytest.approx(1.0)

    run = db.execute(
        "SELECT metrics_written FROM ingestion_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert run[0] == 2


def test_analysis_self_heals(db: psycopg.Connection, aoi_id: str) -> None:
    adapter = FakeReadAdapter([_meta("S1")])
    ingest_sensor(db, adapter, backfill_days=30, overlap_hours=48, analyze=False)
    assert db.execute("SELECT count(*) FROM metrics").fetchone()[0] == 0

    # catalog-only sweep left pairs pending; the next sweep heals them
    assert analyze_pending(db, adapter) == 2
    assert analyze_pending(db, adapter) == 0  # converged


def test_partial_mask_valid_pct(db: psycopg.Connection, aoi_id: str) -> None:
    adapter = FakeReadAdapter([_meta("S1")], scl_class=4)
    # half the SCL pixels cloudy -> valid_pixel_pct = 0.5, metrics still written
    orig = adapter.read

    def half_masked(scene, aoi, bands):  # type: ignore[no-untyped-def]
        w = orig(scene, aoi, bands)
        scl = w.bands["scl"].array.copy()
        scl[:2, :] = 8  # cloud medium probability
        w.bands["scl"] = BandWindow(scl, T, 32634)
        return w

    adapter.read = half_masked  # type: ignore[method-assign]
    ingest_sensor(db, adapter, backfill_days=30, overlap_hours=48)
    pct = db.execute(
        "SELECT valid_pixel_pct FROM metrics WHERE aoi_id = %s AND metric_name='ndvi_mean'",
        (aoi_id,),
    ).fetchone()[0]
    assert pct == pytest.approx(0.5)

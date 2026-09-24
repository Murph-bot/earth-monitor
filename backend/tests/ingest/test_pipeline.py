"""Ingestion pipeline tests — FakeAdapter + real Postgres+PostGIS.

The `db` fixture connection is never committed (autocommit=False), so the
pipeline's `conn.transaction()` blocks run as savepoints and roll back —
the same code that commits in production stays isolated in tests. The
session conn is shared, so `clean` wipes ingest-touched tables per test.
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest

from app.adapters.base import (
    AdapterError,
    BandSpec,
    BandWindow,
    GeoJSONGeom,
    SceneMeta,
    SceneWindow,
    SensorAdapter,
)
from app.config import get_settings
from app.ingest.pipeline import ingest_sensor
from app.ingest.scheduler import due_sensors, poll_interval_hours

AOI: GeoJSONGeom = {
    "type": "Polygon",
    "coordinates": [[[22.7, 40.55], [22.72, 40.55], [22.72, 40.57], [22.7, 40.57], [22.7, 40.55]]],
}
COVERING: GeoJSONGeom = {
    "type": "Polygon",
    "coordinates": [[[22.6, 40.5], [22.8, 40.5], [22.8, 40.6], [22.6, 40.6], [22.6, 40.5]]],
}
FAR_AWAY: GeoJSONGeom = {
    "type": "Polygon",
    "coordinates": [[[10.0, 10.0], [10.1, 10.0], [10.1, 10.1], [10.0, 10.1], [10.0, 10.0]]],
}


def _meta(scene_id: str, geom: GeoJSONGeom, **kw: Any) -> SceneMeta:
    return SceneMeta(
        scene_id=scene_id,
        sensor_id="sentinel-2",
        collection="sentinel-2-c1-l2a",
        catalog="earth-search",
        acquired_at=datetime(2026, 9, 24, 9, 30, tzinfo=UTC),
        bbox=(0.0, 0.0, 1.0, 1.0),
        geometry=geom,
        cloud_cover=kw.get("cloud_cover", 3.4),
        epsg=32634,
        assets={"red": "https://example.com/red.tif"},
        properties={},
    )


class FakeAdapter(SensorAdapter):
    sensor_id = "sentinel-2"
    catalog = "test"
    collections = ("sentinel-2-c1-l2a",)

    def __init__(self, metas: list[SceneMeta] | None = None, boom: bool = False) -> None:
        self._metas = metas or []
        self._boom = boom
        self.searched_windows: list[tuple[object, object]] = []

    def search(self, aoi: GeoJSONGeom, start: object, end: object, **kw: Any) -> list[SceneMeta]:
        if self._boom:
            raise AdapterError("catalog exploded")
        self.searched_windows.append((start, end))
        return list(self._metas)

    def read(self, scene: SceneMeta, aoi: GeoJSONGeom, bands: Sequence[str]) -> SceneWindow:
        raise NotImplementedError

    def quality_mask(self, window: SceneWindow) -> BandWindow:
        raise NotImplementedError

    def band_registry(self) -> list[BandSpec]:
        return []


@pytest.fixture
def clean(db: psycopg.Connection) -> psycopg.Connection:
    for table in (
        "scene_aois",
        "metrics",
        "scenes",
        "aoi_sensor_state",
        "aois",
        "users",
        "ingestion_runs",
    ):
        db.execute(f"DELETE FROM {table}")
    return db


@pytest.fixture
def aoi_id(clean: psycopg.Connection) -> str:
    user_id = clean.execute(
        "INSERT INTO users (email) VALUES (%s) RETURNING id", (f"{uuid.uuid4()}@t.dev",)
    ).fetchone()[0]
    return str(
        clean.execute(
            """INSERT INTO aois (user_id, name, geom, area_m2)
               VALUES (%s, 'ingest test', ST_Multi(ST_GeomFromGeoJSON(%s)),
                       ST_Area(ST_GeomFromGeoJSON(%s)::geography))
               RETURNING id""",
            (user_id, json.dumps(AOI), json.dumps(AOI)),
        ).fetchone()[0]
    )


def test_ingest_populates_scenes_coverage_and_state(db: psycopg.Connection, aoi_id: str) -> None:
    adapter = FakeAdapter([_meta("SCENE_A", COVERING), _meta("SCENE_B", FAR_AWAY)])
    stats = ingest_sensor(db, adapter, backfill_days=30, overlap_hours=48)

    assert stats.aois_checked == 1 and stats.scenes_found == 2 and stats.scenes_inserted == 2
    assert adapter.searched_windows  # backfill window used (no watermark yet)

    rows = db.execute(
        """SELECT s.scene_key, sa.coverage FROM scene_aois sa
           JOIN scenes s ON s.id = sa.scene_id WHERE sa.aoi_id = %s""",
        (aoi_id,),
    ).fetchall()
    assert dict(rows) == {"SCENE_A": pytest.approx(1.0, abs=0.01)}  # FAR_AWAY has no row

    state = db.execute(
        "SELECT last_checked_at IS NOT NULL, last_scene_at FROM aoi_sensor_state "
        "WHERE aoi_id = %s AND sensor_id = 'sentinel-2'",
        (aoi_id,),
    ).fetchone()
    assert state == (True, datetime(2026, 9, 24, 9, 30, tzinfo=UTC))

    run = db.execute(
        "SELECT status, scenes_found, scenes_inserted FROM ingestion_runs "
        "WHERE sensor_id = 'sentinel-2' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert run == ("success", 2, 2)


def test_ingest_is_idempotent(db: psycopg.Connection, aoi_id: str) -> None:
    adapter = FakeAdapter([_meta("SCENE_A", COVERING)])
    ingest_sensor(db, adapter, backfill_days=30, overlap_hours=48)
    stats = ingest_sensor(db, adapter, backfill_days=30, overlap_hours=48)

    assert stats.scenes_found == 1 and stats.scenes_inserted == 0
    count = db.execute("SELECT count(*) FROM scenes WHERE scene_key = 'SCENE_A'").fetchone()[0]
    assert count == 1


def test_ingest_failure_marks_run_failed(db: psycopg.Connection, aoi_id: str) -> None:
    with pytest.raises(AdapterError):
        ingest_sensor(db, FakeAdapter(boom=True), backfill_days=30, overlap_hours=48)

    run = db.execute("SELECT status, error FROM ingestion_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert run[0] == "failed" and "catalog exploded" in run[1]


def test_due_sensors(clean: psycopg.Connection) -> None:
    assert due_sensors(clean, get_settings()) == ["sentinel-2"]

    clean.execute(
        "INSERT INTO ingestion_runs (sensor_id, status, finished_at) "
        "VALUES ('sentinel-2', 'success', now())"
    )
    assert due_sensors(clean, get_settings()) == []  # fresh success → not due


def test_poll_interval_hours() -> None:
    s = get_settings()
    assert poll_interval_hours(5.0, s) == 60.0  # half the revisit cycle
    assert poll_interval_hours(0.1, s) == s.ingest_min_interval_hours  # floor
    override = get_settings().model_copy(update={"ingest_interval_hours": 1.0})
    assert poll_interval_hours(5.0, override) == 1.0

"""Alert evaluation — threshold + baseline rules firing in-app
notifications, dedup on re-analysis, and the quality/sensor gates.

Drives the evaluator directly on the test conn (no rasterio needed).
"""

import json
import uuid
from datetime import UTC, date, datetime

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.alerts.evaluate import evaluate_metric

AOI_GEOM = {
    "type": "Polygon",
    "coordinates": [[[22.7, 40.55], [22.72, 40.55], [22.72, 40.57], [22.7, 40.57], [22.7, 40.55]]],
}
COVERING = {
    "type": "Polygon",
    "coordinates": [[[22.6, 40.5], [22.8, 40.5], [22.8, 40.6], [22.6, 40.6], [22.6, 40.5]]],
}


@pytest.fixture
def aoi_scene(clean: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID, int]:
    """(user_id, aoi_id, scene_id) — the minimum rows evaluation needs."""
    uid: uuid.UUID = clean.execute(
        "INSERT INTO users (email) VALUES ('alerts@test') RETURNING id"
    ).fetchone()[0]
    aoi: uuid.UUID = clean.execute(
        """INSERT INTO aois (user_id, name, geom, area_m2)
           VALUES (%s, 'alerts field', ST_Multi(ST_GeomFromGeoJSON(%s)), 1e6)
           RETURNING id""",
        (uid, json.dumps(AOI_GEOM)),
    ).fetchone()[0]
    sid = int(
        clean.execute(
            """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at,
                                   footprint, assets)
               VALUES ('sentinel-2-c1-l2a', 'sentinel-2', 'ALERT_SCENE', %s,
                       ST_Multi(ST_GeomFromGeoJSON(%s)), '{}')
               RETURNING id""",
            (datetime(2026, 9, 24, 9, 30, tzinfo=UTC), json.dumps(COVERING)),
        ).fetchone()[0]
    )
    return uid, aoi, sid


def _rule(
    db: psycopg.Connection, aoi: uuid.UUID, uid: uuid.UUID, params: dict, **kw: object
) -> int:
    return int(
        db.execute(
            """INSERT INTO alert_rules
                   (aoi_id, user_id, metric_name, rule_type, params,
                    sensor_id, min_valid_pixel_pct, enabled)
               VALUES (%s, %s, 'ndvi_mean', %s, %s, %s, %s, %s) RETURNING id""",
            (
                aoi,
                uid,
                kw.get("rule_type", "threshold"),
                Jsonb(params),
                kw.get("sensor_id"),
                kw.get("min_valid_pixel_pct", 0.5),
                kw.get("enabled", True),
            ),
        ).fetchone()[0]
    )


def _eval(
    clean: psycopg.Connection, aoi: uuid.UUID, sid: int, value: float, pct: float = 0.9
) -> int:
    return evaluate_metric(
        clean,
        aoi_id=aoi,
        scene_id=sid,
        sensor_id="sentinel-2",
        metric_name="ndvi_mean",
        value=value,
        valid_pixel_pct=pct,
        date=date(2026, 9, 24),
    )


def _notifications(clean: psycopg.Connection) -> list[tuple]:
    return clean.execute("SELECT title, channel, status, payload FROM notifications").fetchall()


def test_threshold_fires_and_dedups(clean: psycopg.Connection, aoi_scene: tuple) -> None:
    uid, aoi, sid = aoi_scene
    _rule(clean, aoi, uid, {"op": "lt", "value": 0.3})

    assert _eval(clean, aoi, sid, value=0.2) == 1
    rows = _notifications(clean)
    assert len(rows) == 1
    title, channel, status, payload = rows[0]
    assert "ndvi_mean" in title and "alerts field" in title
    assert channel == "in_app" and status == "queued"
    assert payload["value"] == 0.2 and payload["aoi_id"] == str(aoi)

    # re-analysis of the same scene must not re-notify
    assert _eval(clean, aoi, sid, value=0.2) == 0
    assert len(_notifications(clean)) == 1


def test_threshold_no_fire(clean: psycopg.Connection, aoi_scene: tuple) -> None:
    uid, aoi, sid = aoi_scene
    _rule(clean, aoi, uid, {"op": "lt", "value": 0.3})
    assert _eval(clean, aoi, sid, value=0.5) == 0
    assert _notifications(clean) == []


def test_gates_min_valid_disabled_sensor(clean: psycopg.Connection, aoi_scene: tuple) -> None:
    uid, aoi, sid = aoi_scene
    _rule(clean, aoi, uid, {"op": "lt", "value": 0.3}, min_valid_pixel_pct=0.8)
    # 60% valid < 80% floor -> suppressed
    assert _eval(clean, aoi, sid, value=0.2, pct=0.6) == 0
    assert _eval(clean, aoi, sid, value=0.2, pct=0.9) == 1

    rid = _rule(clean, aoi, uid, {"op": "lt", "value": 0.3}, enabled=False)
    assert _eval(clean, aoi, sid, value=0.2) == 0  # disabled rule silent
    clean.execute("UPDATE alert_rules SET enabled = true WHERE id = %s", (rid,))
    # a rule that never fired for this scene fires once enabled…
    assert _eval(clean, aoi, sid, value=0.2) == 1
    assert _eval(clean, aoi, sid, value=0.2) == 0  # …then dedups per scene

    # sensor-scoped rule: sentinel-1 rule doesn't fire on sentinel-2 metrics
    _rule(clean, aoi, uid, {"op": "gt", "value": 0.0}, sensor_id="sentinel-1")
    assert _eval(clean, aoi, sid, value=0.9) == 0


def test_baseline_deviation(clean: psycopg.Connection, aoi_scene: tuple) -> None:
    uid, aoi, sid = aoi_scene
    _rule(clean, aoi, uid, {"days": 90, "pct": 0.15}, rule_type="baseline_deviation")
    # history: four stable scenes around 0.30
    for i in range(4):
        other = clean.execute(
            """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at,
                                   footprint, assets)
               VALUES ('sentinel-2-c1-l2a', 'sentinel-2', %s, %s,
                       ST_Multi(ST_GeomFromGeoJSON(%s)), '{}') RETURNING id""",
            (f"HIST_{i}", datetime(2026, 9, 1 + i, tzinfo=UTC), json.dumps(COVERING)),
        ).fetchone()[0]
        clean.execute(
            """INSERT INTO metrics (aoi_id, scene_id, sensor_id, date, metric_name,
                                    value, unit, valid_pixel_pct)
               VALUES (%s, %s, 'sentinel-2', %s, 'ndvi_mean', 0.30, 'index', 0.95)""",
            (aoi, other, date(2026, 9, 1 + i)),
        )
    # 0.15 is 50% below the 0.30 baseline -> fires; 0.28 is ~7% -> quiet
    assert _eval(clean, aoi, sid, value=0.28) == 0
    assert _eval(clean, aoi, sid, value=0.15) == 1
    assert "baseline" in _notifications(clean)[0][0]


def test_baseline_needs_history(clean: psycopg.Connection, aoi_scene: tuple) -> None:
    uid, aoi, sid = aoi_scene
    _rule(clean, aoi, uid, {"days": 90, "pct": 0.15}, rule_type="baseline_deviation")
    assert _eval(clean, aoi, sid, value=0.05) == 0  # no history -> no fire
    assert _notifications(clean) == []

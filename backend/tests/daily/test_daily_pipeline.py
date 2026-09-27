"""Daily ingest (rain, UV) on the real test DB with fake grid sources."""

import json
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

import numpy as np
import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.daily.grid import cell_window
from app.daily.pipeline import RAIN, UV, ingest_daily

FIELD = {
    "type": "Polygon",
    "coordinates": [
        [[22.55, 39.45], [22.75, 39.45], [22.75, 39.60], [22.55, 39.60], [22.55, 39.45]]
    ],
}
TODAY = date(2026, 9, 28)


@pytest.fixture
def field(clean: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    uid = clean.execute("INSERT INTO users (email) VALUES ('rain@test') RETURNING id").fetchone()[0]
    aoi = clean.execute(
        """INSERT INTO aois (user_id, name, geom, area_m2)
           VALUES (%s, 'rain field', ST_Multi(ST_GeomFromGeoJSON(%s)), 1e6) RETURNING id""",
        (uid, json.dumps(FIELD)),
    ).fetchone()[0]
    return uid, aoi


class FakeSource:
    """Every day rains 3 mm over the field except 2026-09-25 (12 mm);
    the most recent day is not published yet."""

    def __init__(self) -> None:
        self.days: list[date] = []

    def __call__(self, day: date) -> np.ndarray | None:
        self.days.append(day)
        if day == date(2026, 9, 27):
            return None
        grid = np.zeros((RAIN.grid.rows, RAIN.grid.cols), dtype=np.float32)
        rows, cols = cell_window(RAIN.grid, (22.55, 39.45, 22.75, 39.60))
        grid[rows, cols] = 12.0 if day == date(2026, 9, 25) else 3.0
        return grid


def _rain(conn: psycopg.Connection) -> dict[date, float]:
    return dict(
        conn.execute(
            "SELECT date, value FROM daily_metrics WHERE metric_name = 'rain_mm'"
        ).fetchall()
    )


def test_backfills_each_missing_day_once(clean: psycopg.Connection, field: tuple) -> None:
    source = FakeSource()
    written = ingest_daily(clean, replace(RAIN, fetch=source), today=TODAY, backfill_days=5)

    rain = _rain(clean)
    assert written == 4
    assert sorted(rain) == [date(2026, 9, d) for d in (23, 24, 25, 26)]
    assert rain[date(2026, 9, 25)] == pytest.approx(12.0)
    assert rain[date(2026, 9, 24)] == pytest.approx(3.0)

    # next sweep: only the unpublished day is tried again
    source.days.clear()
    assert ingest_daily(clean, replace(RAIN, fetch=source), today=TODAY, backfill_days=5) == 0
    assert source.days == [date(2026, 9, 27)]


def test_downpour_rule_fires_once_per_day(clean: psycopg.Connection, field: tuple) -> None:
    uid, aoi = field
    clean.execute(
        """INSERT INTO alert_rules (aoi_id, user_id, metric_name, rule_type, params, created_at)
           VALUES (%s, %s, 'rain_mm', 'threshold', %s, %s)""",
        (aoi, uid, Jsonb({"op": "gt", "value": 10}), datetime(2026, 9, 1, tzinfo=UTC)),
    )
    ingest_daily(clean, replace(RAIN, fetch=FakeSource()), today=TODAY, backfill_days=5)
    clean.execute("DELETE FROM daily_metrics")  # re-analysis must not notify twice
    ingest_daily(clean, replace(RAIN, fetch=FakeSource()), today=TODAY, backfill_days=5)

    rows = clean.execute("SELECT title, metric_date FROM notifications").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == date(2026, 9, 25)
    assert "rain_mm above 10" in rows[0][0]


def _uv_day(day: date) -> np.ndarray:
    uvi = np.full((UV.grid.rows, UV.grid.cols), 3.0, dtype=np.float32)
    rows, cols = cell_window(UV.grid, (22.55, 39.45, 22.75, 39.60))
    uvi[rows, cols] = 9.5 if day == date(2026, 9, 26) else 5.0
    return uvi


def test_uv_index_lands_and_high_uv_rule_fires(clean: psycopg.Connection, field: tuple) -> None:
    uid, aoi = field
    clean.execute(
        """INSERT INTO alert_rules (aoi_id, user_id, metric_name, rule_type, params, created_at)
           VALUES (%s, %s, 'uv_index', 'threshold', %s, %s)""",
        (aoi, uid, Jsonb({"op": "gte", "value": 8}), datetime(2026, 9, 1, tzinfo=UTC)),
    )
    ingest_daily(clean, replace(UV, fetch=_uv_day), today=TODAY, backfill_days=3)

    rows = clean.execute(
        "SELECT date, value, unit, source FROM daily_metrics ORDER BY date"
    ).fetchall()
    assert [(d, pytest.approx(v), u, s) for d, v, u, s in rows] == [
        (date(2026, 9, 25), 5.0, "UVI", "temis-uv"),
        (date(2026, 9, 26), 9.5, "UVI", "temis-uv"),
        (date(2026, 9, 27), 5.0, "UVI", "temis-uv"),
    ]
    notes = clean.execute("SELECT title, metric_date FROM notifications").fetchall()
    assert [d for _, d in notes] == [date(2026, 9, 26)]
    assert "uv_index at or above 8" in notes[0][0]

"""Daily gridded sources -> daily_metrics, then alert rules.

Idempotent by construction: a sweep computes which (AOI, day) pairs lack a
value inside the backfill window, downloads each such day's grid once, and
upserts. An unpublished day stays missing and is retried next sweep.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import psycopg
import structlog

from app.alerts.evaluate import evaluate_metric
from app.daily import pdir_now, temis
from app.daily.grid import Bbox, Grid, aoi_mean

log = structlog.get_logger()


@dataclass(frozen=True)
class DailySource:
    id: str  # sensors.id
    metric_name: str
    unit: str
    grid: Grid
    fetch: Callable[[date], np.ndarray | None]


RAIN = DailySource("pdir-now", "rain_mm", "mm", pdir_now.GRID, pdir_now.fetch_daily)
UV = DailySource("temis-uv", "uv_index", "UVI", temis.GRID, temis.fetch_daily)
DAILY_SOURCES = (RAIN, UV)


def ingest_daily(
    conn: psycopg.Connection, source: DailySource, *, today: date, backfill_days: int
) -> int:
    """Fill the source's missing days for every AOI; returns rows written.
    Today is excluded: its daily value is not complete yet."""
    days = [today - timedelta(days=k) for k in range(backfill_days, 0, -1)]
    missing = conn.execute(
        """SELECT d::date, a.id,
                  ST_XMin(a.bbox), ST_YMin(a.bbox), ST_XMax(a.bbox), ST_YMax(a.bbox)
           FROM aois a CROSS JOIN unnest(%s::date[]) AS d
           WHERE NOT EXISTS (
               SELECT 1 FROM daily_metrics m
               WHERE m.aoi_id = a.id AND m.date = d
                 AND m.metric_name = %s AND m.source = %s)
           ORDER BY d""",
        (days, source.metric_name, source.id),
    ).fetchall()
    by_day: dict[date, list[tuple[object, Bbox]]] = defaultdict(list)
    for day, aoi_id, minx, miny, maxx, maxy in missing:
        by_day[day].append((aoi_id, (minx, miny, maxx, maxy)))

    written = 0
    for day, aois in by_day.items():
        values = source.fetch(day)
        if values is None:
            continue
        for aoi_id, bbox in aois:
            value = aoi_mean(source.grid, values, bbox)
            if value is None:
                continue
            with conn.transaction():
                conn.execute(
                    """INSERT INTO daily_metrics (aoi_id, date, metric_name, source, value, unit)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (aoi_id, metric_name, source, date)
                       DO UPDATE SET value = EXCLUDED.value""",
                    (aoi_id, day, source.metric_name, source.id, value, source.unit),
                )
                evaluate_metric(
                    conn,
                    aoi_id=aoi_id,
                    scene_id=None,
                    sensor_id=source.id,
                    metric_name=source.metric_name,
                    value=value,
                    valid_pixel_pct=1.0,
                    date=day,
                )
            written += 1
    log.info("daily_done", source=source.id, days_missing=len(by_day), rows_written=written)
    return written

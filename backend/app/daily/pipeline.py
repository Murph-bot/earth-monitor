"""Daily gridded sources -> daily_metrics, then alert rules.

Idempotent by construction: a sweep computes which (AOI, day) pairs lack a
value inside the backfill window, downloads each such day's grid once, and
upserts. An unpublished day stays missing and is retried next sweep.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import psycopg
import structlog

from app.alerts.evaluate import evaluate_metric
from app.daily import pdir_now

log = structlog.get_logger()

RAIN_SOURCE = "pdir-now"
RAIN_METRIC = "rain_mm"


def ingest_rain(
    conn: psycopg.Connection,
    *,
    today: date,
    backfill_days: int,
    fetch: Callable[[date], np.ndarray | None] = pdir_now.fetch_daily,
) -> int:
    """Fill missing daily rainfall for every AOI; returns rows written.
    Today is excluded: its daily total is not complete yet."""
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
        (days, RAIN_METRIC, RAIN_SOURCE),
    ).fetchall()
    by_day: dict[date, list[tuple[object, pdir_now.Bbox]]] = defaultdict(list)
    for day, aoi_id, minx, miny, maxx, maxy in missing:
        by_day[day].append((aoi_id, (minx, miny, maxx, maxy)))

    written = 0
    for day, aois in by_day.items():
        grid = fetch(day)
        if grid is None:
            continue
        for aoi_id, bbox in aois:
            mm = pdir_now.aoi_rain_mm(grid, bbox)
            if mm is None:
                continue
            with conn.transaction():
                conn.execute(
                    """INSERT INTO daily_metrics (aoi_id, date, metric_name, source, value, unit)
                       VALUES (%s, %s, %s, %s, %s, 'mm')
                       ON CONFLICT (aoi_id, metric_name, source, date)
                       DO UPDATE SET value = EXCLUDED.value""",
                    (aoi_id, day, RAIN_METRIC, RAIN_SOURCE, mm),
                )
                evaluate_metric(
                    conn,
                    aoi_id=aoi_id,
                    scene_id=None,
                    sensor_id=RAIN_SOURCE,
                    metric_name=RAIN_METRIC,
                    value=mm,
                    valid_pixel_pct=1.0,
                    date=day,
                )
            written += 1
    log.info("rain_done", days_missing=len(by_day), rows_written=written)
    return written

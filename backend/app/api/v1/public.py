"""Public, unauthenticated read faces — the logged-out landing page.

Everything here is an aggregate over data the system already holds (metrics,
daily rainfall, ingested scenes); nothing is invented. When there is no data
for a window the field is null and the client says so — never a placeholder
number. Results are cached in process (the free tier runs one instance) and
marked cacheable in HTTP.
"""

import threading
import time
from datetime import UTC, date, datetime

import psycopg
from fastapi import APIRouter, Response

from app.api.deps import DbConn
from app.api.v1.schemas import (
    GreennessSummary,
    RainSummary,
    SceneCountSummary,
    ThessalySummary,
)
from app.config import get_settings

router = APIRouter()

# Thessaly, lon/lat (minx, miny, maxx, maxy): the plain plus Pelion/Pindus rims
THESSALY_BBOX = (21.3, 39.0, 23.6, 40.2)
WINDOW_DAYS = 7
CLEAR_MAX_CLOUD_PCT = 20.0
MIN_VALID_PIXEL_PCT = 0.5  # same default floor alert rules use
MIN_RAIN_DAYS = 5  # an area's 7-day rain total needs at least 5 of 7 daily values

_ENVELOPE = "ST_MakeEnvelope(%s, %s, %s, %s, 4326)"

_cache_lock = threading.Lock()
_cache: tuple[float, ThessalySummary] | None = None


def clear_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def _greenness(db: psycopg.Connection, today: date) -> GreennessSummary:
    row = db.execute(
        f"""SELECT avg(m.value) FILTER (WHERE m.date > %s::date - 7),
                   avg(m.value) FILTER (WHERE m.date <= %s::date - 7),
                   count(DISTINCT m.aoi_id)
            FROM metrics m JOIN aois a ON a.id = m.aoi_id
            WHERE m.metric_name = 'ndvi_mean' AND m.valid_pixel_pct >= %s
              AND m.date > %s::date - 14
              AND ST_Intersects(a.geom, {_ENVELOPE})""",
        (today, today, MIN_VALID_PIXEL_PCT, today, *THESSALY_BBOX),
    ).fetchone()
    assert row is not None
    this_week = None if row[0] is None else float(row[0])
    last_week = None if row[1] is None else float(row[1])
    delta = None if this_week is None or last_week is None else this_week - last_week
    return GreennessSummary(mean=this_week, previous_mean=last_week, delta=delta, areas=int(row[2]))


def _rain(db: psycopg.Connection, today: date) -> RainSummary:
    row = db.execute(
        f"""SELECT avg(t.total), count(*)
            FROM (SELECT d.aoi_id, sum(d.value) AS total
                  FROM daily_metrics d JOIN aois a ON a.id = d.aoi_id
                  WHERE d.metric_name = 'rain_mm' AND d.date > %s::date - 7
                    AND ST_Intersects(a.geom, {_ENVELOPE})
                  GROUP BY d.aoi_id
                  HAVING count(*) >= %s) t""",
        (today, *THESSALY_BBOX, MIN_RAIN_DAYS),
    ).fetchone()
    assert row is not None
    return RainSummary(mean_mm=None if row[0] is None else float(row[0]), areas=int(row[1]))


def _scenes(db: psycopg.Connection, now: datetime) -> SceneCountSummary:
    row = db.execute(
        f"""SELECT count(*) FILTER (WHERE cloud_cover <= %s),
                   count(*) FILTER (WHERE cloud_cover > %s OR cloud_cover IS NULL),
                   max(acquired_at)
            FROM scenes
            WHERE acquired_at >= %s::timestamptz - make_interval(days => %s)
              AND ST_Intersects(footprint, {_ENVELOPE})""",
        (CLEAR_MAX_CLOUD_PCT, CLEAR_MAX_CLOUD_PCT, now, WINDOW_DAYS, *THESSALY_BBOX),
    ).fetchone()
    assert row is not None
    return SceneCountSummary(clear=int(row[0]), cloudy=int(row[1]), latest_scene_at=row[2])


def compute_summary(db: psycopg.Connection, now: datetime | None = None) -> ThessalySummary:
    now = now or datetime.now(UTC)
    today = now.date()
    return ThessalySummary(
        region="thessaly",
        bounds=list(THESSALY_BBOX),
        window_days=WINDOW_DAYS,
        clear_max_cloud_pct=CLEAR_MAX_CLOUD_PCT,
        generated_at=now,
        greenness=_greenness(db, today),
        rain=_rain(db, today),
        scenes=_scenes(db, now),
    )


@router.get("/public/region/thessaly/summary")
def thessaly_summary(db: DbConn, response: Response) -> ThessalySummary:
    """This week's Thessaly numbers for the landing page: mean greenness (NDVI)
    vs the week before, mean 7-day rain, and clear vs cloudy scenes. Aggregated
    over monitored areas inside the region; null where there is no data."""
    global _cache
    ttl = get_settings().public_summary_ttl_seconds
    response.headers["Cache-Control"] = f"public, max-age={min(ttl, 300)}"
    with _cache_lock:
        if _cache is not None and time.monotonic() - _cache[0] < ttl:
            return _cache[1]
    summary = compute_summary(db)
    with _cache_lock:
        _cache = (time.monotonic(), summary)
    return summary

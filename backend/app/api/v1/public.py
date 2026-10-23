"""Public, unauthenticated read faces — the logged-out landing page.

Everything here is an aggregate over data the system already holds (metrics,
daily rainfall, ingested scenes) inside a registered region's box (see
app.regions); nothing is invented. When there is no data for a window the
field is null — never a placeholder number. Results are cached in process per
region (the free tier runs one instance) and marked cacheable in HTTP.
"""

import threading
import time
from datetime import UTC, date, datetime

import psycopg
from fastapi import APIRouter, HTTPException, Response

from app.api.deps import DbConn
from app.api.v1.schemas import (
    GreennessSummary,
    RainSummary,
    RegionSummary,
    SceneCountSummary,
)
from app.config import get_settings
from app.regions import REGIONS, BBox, Region, get_region

router = APIRouter()

WINDOW_DAYS = 7
CLEAR_MAX_CLOUD_PCT = 20.0
MIN_VALID_PIXEL_PCT = 0.5  # same default floor alert rules use
MIN_RAIN_DAYS = 5  # an area's 7-day rain total needs at least 5 of 7 daily values

_ENVELOPE = "ST_MakeEnvelope(%s, %s, %s, %s, 4326)"

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, RegionSummary]] = {}


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _greenness(db: psycopg.Connection, today: date, bbox: BBox) -> GreennessSummary:
    row = db.execute(
        f"""SELECT avg(m.value) FILTER (WHERE m.date > %s::date - 7),
                   avg(m.value) FILTER (WHERE m.date <= %s::date - 7),
                   count(DISTINCT m.aoi_id)
            FROM metrics m JOIN aois a ON a.id = m.aoi_id
            WHERE m.metric_name = 'ndvi_mean' AND m.valid_pixel_pct >= %s
              AND m.date > %s::date - 14
              AND ST_Intersects(a.geom, {_ENVELOPE})""",
        (today, today, MIN_VALID_PIXEL_PCT, today, *bbox),
    ).fetchone()
    assert row is not None
    this_week = None if row[0] is None else float(row[0])
    last_week = None if row[1] is None else float(row[1])
    delta = None if this_week is None or last_week is None else this_week - last_week
    return GreennessSummary(mean=this_week, previous_mean=last_week, delta=delta, areas=int(row[2]))


def _rain(db: psycopg.Connection, today: date, bbox: BBox) -> RainSummary:
    row = db.execute(
        f"""SELECT avg(t.total), count(*)
            FROM (SELECT d.aoi_id, sum(d.value) AS total
                  FROM daily_metrics d JOIN aois a ON a.id = d.aoi_id
                  WHERE d.metric_name = 'rain_mm' AND d.date > %s::date - 7
                    AND ST_Intersects(a.geom, {_ENVELOPE})
                  GROUP BY d.aoi_id
                  HAVING count(*) >= %s) t""",
        (today, *bbox, MIN_RAIN_DAYS),
    ).fetchone()
    assert row is not None
    return RainSummary(mean_mm=None if row[0] is None else float(row[0]), areas=int(row[1]))


def _scenes(db: psycopg.Connection, now: datetime, bbox: BBox) -> SceneCountSummary:
    row = db.execute(
        f"""SELECT count(*) FILTER (WHERE cloud_cover <= %s),
                   count(*) FILTER (WHERE cloud_cover > %s OR cloud_cover IS NULL),
                   max(acquired_at)
            FROM scenes
            WHERE acquired_at >= %s::timestamptz - make_interval(days => %s)
              AND ST_Intersects(footprint, {_ENVELOPE})""",
        (CLEAR_MAX_CLOUD_PCT, CLEAR_MAX_CLOUD_PCT, now, WINDOW_DAYS, *bbox),
    ).fetchone()
    assert row is not None
    return SceneCountSummary(clear=int(row[0]), cloudy=int(row[1]), latest_scene_at=row[2])


def compute_summary(
    db: psycopg.Connection, region: Region, now: datetime | None = None
) -> RegionSummary:
    now = now or datetime.now(UTC)
    today = now.date()
    return RegionSummary(
        region=region.slug,
        name=region.name,
        bounds=list(region.bbox),
        window_days=WINDOW_DAYS,
        clear_max_cloud_pct=CLEAR_MAX_CLOUD_PCT,
        generated_at=now,
        greenness=_greenness(db, today, region.bbox),
        rain=_rain(db, today, region.bbox),
        scenes=_scenes(db, now, region.bbox),
    )


@router.get("/public/regions")
def list_regions() -> list[dict[str, object]]:
    """Registered public regions (slug, name, bounds)."""
    return [{"slug": r.slug, "name": r.name, "bounds": list(r.bbox)} for r in REGIONS.values()]


@router.get("/public/region/{slug}/summary")
def region_summary(slug: str, db: DbConn, response: Response) -> RegionSummary:
    """This week's numbers for a public region: mean greenness (NDVI) vs the
    week before, mean 7-day rain, and clear vs cloudy scenes. Aggregated over
    monitored areas inside the region; null where there is no data."""
    region = get_region(slug)
    if region is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown region '{slug}'",
            headers={"x-error-code": "REGION_NOT_FOUND"},
        )
    ttl = get_settings().public_summary_ttl_seconds
    response.headers["Cache-Control"] = f"public, max-age={min(ttl, 300)}"
    with _cache_lock:
        hit = _cache.get(slug)
        if hit is not None and time.monotonic() - hit[0] < ttl:
            return hit[1]
    summary = compute_summary(db, region)
    with _cache_lock:
        _cache[slug] = (time.monotonic(), summary)
    return summary

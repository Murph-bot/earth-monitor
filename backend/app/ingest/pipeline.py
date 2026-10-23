"""Ingestion pipeline — one sensor's catalog sweep.

Per (AOI, sensor): search the catalog since the last check (with an overlap
margin for late-arriving items), upsert scenes on their natural key, refresh
the materialized scene_aois coverage join, and advance the watermark. Every
step is idempotent — re-running the same window converges, never duplicates.

TRANSACTION MODEL: this module never calls conn.commit(). Write groups are
wrapped in `conn.transaction()` blocks, which are real transactions when the
connection is autocommit=True (production) and savepoints when a caller has
an open transaction (tests) — the same code commits in prod and rolls back
in the test fixture.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import psycopg
import structlog
from psycopg.types.json import Jsonb

from app.adapters.base import GeoJSONGeom, SceneMeta, SensorAdapter
from app.analysis.runner import analyze_pending

log = structlog.get_logger()


@dataclass(frozen=True)
class RunStats:
    sensor_id: str
    aois_checked: int = 0
    scenes_found: int = 0
    scenes_inserted: int = 0
    metrics_written: int = 0
    scene_ids: list[int] = field(default_factory=list)


def _upsert_scene(conn: psycopg.Connection, meta: SceneMeta) -> tuple[int, bool]:
    """Insert or refresh one scene; returns (id, was_inserted).

    Natural key (collection_id, scene_key) is the idempotency anchor —
    re-ingesting the same catalog window hits ON CONFLICT and updates
    metadata instead of duplicating. xmax = 0 distinguishes the two paths.
    """
    row = conn.execute(
        """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at,
                               cloud_cover, epsg, footprint, assets, properties)
           VALUES (%s, %s, %s, %s, %s, %s,
                   ST_Multi(ST_GeomFromGeoJSON(%s)), %s, %s)
           ON CONFLICT (collection_id, scene_key) DO UPDATE SET
               acquired_at = EXCLUDED.acquired_at,
               cloud_cover = EXCLUDED.cloud_cover,
               epsg        = EXCLUDED.epsg,
               footprint   = EXCLUDED.footprint,
               assets      = EXCLUDED.assets,
               properties  = EXCLUDED.properties
           RETURNING id, (xmax = 0) AS inserted""",
        (
            meta.collection,
            meta.sensor_id,
            meta.scene_id,
            meta.acquired_at,
            meta.cloud_cover,
            meta.epsg,
            json.dumps(meta.geometry),
            Jsonb(meta.assets),
            Jsonb(meta.properties),
        ),
    ).fetchone()
    assert row is not None  # RETURNING always yields a row
    return int(row[0]), bool(row[1])


def _refresh_coverage(conn: psycopg.Connection, scene_id: int) -> int:
    """Materialize this scene's coverage against ALL aois — a scene found via
    one AOI's search may also cover others. LEAST() guards the CHECK (<=1)
    against geography-rounding overshoot; NULLIF guards empty geoms."""
    cur = conn.execute(
        """INSERT INTO scene_aois (scene_id, aoi_id, coverage)
           SELECT s.id, a.id,
                  LEAST(
                    ST_Area(ST_Intersection(s.footprint::geography, a.geom::geography))
                    / NULLIF(ST_Area(a.geom::geography), 0),
                    1.0
                  )::real
           FROM scenes s, aois a
           WHERE s.id = %s AND ST_Intersects(s.footprint, a.geom)
           ON CONFLICT (scene_id, aoi_id) DO UPDATE SET coverage = EXCLUDED.coverage""",
        (scene_id,),
    )
    return cur.rowcount


def _update_watermark(
    conn: psycopg.Connection, aoi_id: str, sensor_id: str, last_scene_at: datetime | None
) -> None:
    conn.execute(
        """INSERT INTO aoi_sensor_state (aoi_id, sensor_id, last_checked_at, last_scene_at)
           VALUES (%s, %s, now(), %s)
           ON CONFLICT (aoi_id, sensor_id) DO UPDATE SET
               last_checked_at = EXCLUDED.last_checked_at,
               last_scene_at = GREATEST(EXCLUDED.last_scene_at, aoi_sensor_state.last_scene_at)""",
        (aoi_id, sensor_id, last_scene_at),
    )


def _aois_with_watermarks(
    conn: psycopg.Connection, sensor_id: str, aoi_id: str | None = None
) -> list[tuple[str, GeoJSONGeom, datetime | None]]:
    rows = conn.execute(
        """SELECT a.id, ST_AsGeoJSON(a.geom), s.last_checked_at
           FROM aois a
           LEFT JOIN aoi_sensor_state s
                  ON s.aoi_id = a.id AND s.sensor_id = %s
           WHERE %s::uuid IS NULL OR a.id = %s::uuid""",
        (sensor_id, aoi_id, aoi_id),
    ).fetchall()
    return [(str(r[0]), json.loads(r[1]), r[2]) for r in rows]


class CatalogGapError(Exception):
    """The catalog has scenes over an AOI that the database does not."""


def _aoi_geom(conn: psycopg.Connection, aoi_id: str) -> GeoJSONGeom:
    row = conn.execute("SELECT ST_AsGeoJSON(geom) FROM aois WHERE id = %s", (aoi_id,)).fetchone()
    if row is None:
        raise KeyError(f"no aoi '{aoi_id}'")
    geom: GeoJSONGeom = json.loads(row[0])
    return geom


def _store_scenes(conn: psycopg.Connection, metas: list[SceneMeta]) -> tuple[int, list[int]]:
    inserted = 0
    scene_ids: list[int] = []
    for meta in metas:
        scene_id, is_new = _upsert_scene(conn, meta)
        inserted += int(is_new)
        scene_ids.append(scene_id)
        _refresh_coverage(conn, scene_id)
    return inserted, scene_ids


def ingest_sensor(
    conn: psycopg.Connection,
    adapter: SensorAdapter,
    *,
    backfill_days: int,
    overlap_hours: int,
    analyze: bool = True,
    aoi_id: str | None = None,
) -> RunStats:
    """Run one catalog sweep for `adapter`'s sensor. Writes an ingestion_runs
    audit row; on adapter/DB failure the row is marked failed and the error
    re-raised (the scheduler isolates per-sensor failures).

    With `aoi_id`, only that AOI is searched and its watermark is ignored: the
    window is always the last `backfill_days` (a user-requested backfill)."""
    sensor_id = adapter.sensor_id
    overlap_hours = max(overlap_hours, adapter.publish_lag_hours)
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO ingestion_runs (sensor_id) VALUES (%s) RETURNING id", (sensor_id,)
        ).fetchone()
        assert row is not None  # RETURNING always yields a row
        run_id = int(row[0])

    aois_checked = found = inserted = metrics_written = 0
    scene_ids: list[int] = []
    try:
        now = datetime.now(UTC)
        for row_aoi_id, geom, last_checked in _aois_with_watermarks(conn, sensor_id, aoi_id):
            start: date = (
                (last_checked - timedelta(hours=overlap_hours)).date()
                if last_checked and aoi_id is None
                else (now - timedelta(days=backfill_days)).date()
            )
            metas = adapter.search(geom, start, now.date())
            aois_checked += 1
            found += len(metas)
            with conn.transaction():
                n_new, ids = _store_scenes(conn, metas)
                inserted += n_new
                scene_ids.extend(ids)
                _update_watermark(
                    conn, row_aoi_id, sensor_id, max((m.acquired_at for m in metas), default=None)
                )
        if analyze:
            # pixel reads happen here — outside the metadata transactions
            metrics_written = analyze_pending(conn, adapter)
    except Exception as exc:
        with conn.transaction():
            conn.execute(
                """UPDATE ingestion_runs SET finished_at = now(), status = 'failed',
                       error = %s, scenes_found = %s, scenes_inserted = %s,
                       metrics_written = %s
                   WHERE id = %s""",
                (str(exc)[:2000], found, inserted, metrics_written, run_id),
            )
        log.error("ingest_failed", sensor_id=sensor_id, run_id=run_id, error=str(exc))
        raise

    with conn.transaction():
        conn.execute(
            """UPDATE ingestion_runs SET finished_at = now(), status = 'success',
                   scenes_found = %s, scenes_inserted = %s, metrics_written = %s
               WHERE id = %s""",
            (found, inserted, metrics_written, run_id),
        )
    log.info(
        "ingest_ok",
        sensor_id=sensor_id,
        run_id=run_id,
        aois=aois_checked,
        found=found,
        inserted=inserted,
        metrics=metrics_written,
    )
    return RunStats(sensor_id, aois_checked, found, inserted, metrics_written, scene_ids)


def stale_sensors(
    conn: psycopg.Connection, adapters: list[SensorAdapter], *, now: datetime | None = None
) -> list[str]:
    """Sensors whose newest stored scene is older than their stale_after_days
    (or that have none). A green run that saved nothing for weeks is a stall."""
    now = now or datetime.now(UTC)
    stale: list[str] = []
    for adapter in adapters:
        if adapter.stale_after_days <= 0:
            continue
        row = conn.execute(
            "SELECT max(acquired_at) FROM scenes WHERE sensor_id = %s", (adapter.sensor_id,)
        ).fetchone()
        newest = row[0] if row else None
        if newest is None or now - newest > timedelta(days=adapter.stale_after_days):
            log.warning("sensor_stale", sensor_id=adapter.sensor_id, newest_scene=str(newest))
            stale.append(adapter.sensor_id)
    return stale


def backfill_aoi(
    conn: psycopg.Connection,
    adapter: SensorAdapter,
    aoi_id: str,
    start: date,
    end: date,
    *,
    analyze: bool = True,
) -> RunStats:
    """Re-search one AOI over an explicit [start, end] window and upsert what
    the catalog has. Idempotent (natural-key upserts) and leaves the sweep
    watermark alone, so it is safe to run alongside the cron."""
    geom = _aoi_geom(conn, aoi_id)
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO ingestion_runs (sensor_id) VALUES (%s) RETURNING id",
            (adapter.sensor_id,),
        ).fetchone()
        assert row is not None
        run_id = int(row[0])
    metrics_written = 0
    try:
        metas = adapter.search(geom, start, end)
        with conn.transaction():
            inserted, scene_ids = _store_scenes(conn, metas)
        if analyze:
            metrics_written = analyze_pending(conn, adapter)
    except Exception as exc:
        with conn.transaction():
            conn.execute(
                """UPDATE ingestion_runs SET finished_at = now(), status = 'failed', error = %s
                   WHERE id = %s""",
                (f"backfill {aoi_id} {start}..{end}: {exc}"[:2000], run_id),
            )
        raise
    with conn.transaction():
        conn.execute(
            """UPDATE ingestion_runs SET finished_at = now(), status = 'success',
                   scenes_found = %s, scenes_inserted = %s, metrics_written = %s
               WHERE id = %s""",
            (len(metas), inserted, metrics_written, run_id),
        )
    log.info(
        "backfill_ok",
        sensor_id=adapter.sensor_id,
        aoi_id=aoi_id,
        start=str(start),
        end=str(end),
        found=len(metas),
        inserted=inserted,
    )
    return RunStats(adapter.sensor_id, 1, len(metas), inserted, metrics_written, scene_ids)


def missing_scenes(
    conn: psycopg.Connection,
    adapter: SensorAdapter,
    *,
    lookback_days: int = 7,
    now: datetime | None = None,
) -> dict[str, list[str]]:
    """Independent audit of the sweep: re-ask the catalog what it has over each
    AOI in the last `lookback_days` and return {aoi_id: [scene ids]} for
    items with no stored scene_aois row. Empty dict = nothing missed.

    This catches every way a green sweep can silently save nothing (window
    drift, watermark races, filter bugs) because it does not share the
    sweep's window arithmetic."""
    now = now or datetime.now(UTC)
    start = (now - timedelta(days=lookback_days)).date()
    gaps: dict[str, list[str]] = {}
    aois_checked = items_checked = items_stored = 0
    for aoi_id, geom, _ in _aois_with_watermarks(conn, adapter.sensor_id):
        metas = adapter.search(geom, start, now.date())
        aois_checked += 1
        if not metas:
            continue
        stored = {
            r[0]
            for r in conn.execute(
                """SELECT s.scene_key FROM scenes s
                   JOIN scene_aois sa ON sa.scene_id = s.id
                   WHERE sa.aoi_id = %s AND s.sensor_id = %s AND s.scene_key = ANY(%s)""",
                (aoi_id, adapter.sensor_id, [m.scene_id for m in metas]),
            ).fetchall()
        }
        # a catalog footprint can touch the AOI by intersects yet produce no
        # coverage row only if it is absent from `scenes` — so absence = miss
        missing = sorted(m.scene_id for m in metas if m.scene_id not in stored)
        items_checked += len(metas)
        items_stored += len(metas) - len(missing)
        if missing:
            log.error("catalog_gap", sensor_id=adapter.sensor_id, aoi_id=aoi_id, missing=missing)
            gaps[aoi_id] = missing
    if not gaps:
        log.info(
            "catalog_audit_ok",
            sensor_id=adapter.sensor_id,
            lookback_days=lookback_days,
            aois_checked=aois_checked,
            catalog_items_checked=items_checked,
            stored=items_stored,
            missing=0,
        )
    return gaps

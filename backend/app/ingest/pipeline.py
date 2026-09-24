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

log = structlog.get_logger()


@dataclass(frozen=True)
class RunStats:
    sensor_id: str
    aois_checked: int = 0
    scenes_found: int = 0
    scenes_inserted: int = 0
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
    conn: psycopg.Connection, sensor_id: str
) -> list[tuple[str, GeoJSONGeom, datetime | None]]:
    rows = conn.execute(
        """SELECT a.id, ST_AsGeoJSON(a.geom), s.last_checked_at
           FROM aois a
           LEFT JOIN aoi_sensor_state s
                  ON s.aoi_id = a.id AND s.sensor_id = %s""",
        (sensor_id,),
    ).fetchall()
    return [(str(r[0]), json.loads(r[1]), r[2]) for r in rows]


def ingest_sensor(
    conn: psycopg.Connection,
    adapter: SensorAdapter,
    *,
    backfill_days: int,
    overlap_hours: int,
) -> RunStats:
    """Run one catalog sweep for `adapter`'s sensor. Writes an ingestion_runs
    audit row; on adapter/DB failure the row is marked failed and the error
    re-raised (the scheduler isolates per-sensor failures)."""
    sensor_id = adapter.sensor_id
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO ingestion_runs (sensor_id) VALUES (%s) RETURNING id", (sensor_id,)
        ).fetchone()
        assert row is not None  # RETURNING always yields a row
        run_id = int(row[0])

    aois_checked = found = inserted = 0
    scene_ids: list[int] = []
    try:
        now = datetime.now(UTC)
        for aoi_id, geom, last_checked in _aois_with_watermarks(conn, sensor_id):
            start: date = (
                (last_checked - timedelta(hours=overlap_hours)).date()
                if last_checked
                else (now - timedelta(days=backfill_days)).date()
            )
            metas = adapter.search(geom, start, now.date())
            aois_checked += 1
            found += len(metas)
            with conn.transaction():
                for meta in metas:
                    scene_id, is_new = _upsert_scene(conn, meta)
                    inserted += int(is_new)
                    scene_ids.append(scene_id)
                    _refresh_coverage(conn, scene_id)
                _update_watermark(
                    conn, aoi_id, sensor_id, max((m.acquired_at for m in metas), default=None)
                )
    except Exception as exc:
        with conn.transaction():
            conn.execute(
                """UPDATE ingestion_runs SET finished_at = now(), status = 'failed',
                       error = %s, scenes_found = %s, scenes_inserted = %s
                   WHERE id = %s""",
                (str(exc)[:2000], found, inserted, run_id),
            )
        log.error("ingest_failed", sensor_id=sensor_id, run_id=run_id, error=str(exc))
        raise

    with conn.transaction():
        conn.execute(
            """UPDATE ingestion_runs SET finished_at = now(), status = 'success',
                   scenes_found = %s, scenes_inserted = %s
               WHERE id = %s""",
            (found, inserted, run_id),
        )
    log.info(
        "ingest_ok",
        sensor_id=sensor_id,
        run_id=run_id,
        aois=aois_checked,
        found=found,
        inserted=inserted,
    )
    return RunStats(sensor_id, aois_checked, found, inserted, scene_ids)

"""Scheduler — decides when each sensor's pipeline runs.

Per-sensor cadence = half the sensor's stated revisit cycle (polling AT the
cycle adds up to a full cycle of lag when timing is unlucky; half keeps
freshness tight while staying cheap — searches are metadata-only). Floored
by `ingest_min_interval_hours`; `ingest_interval_hours` overrides globally
(useful in dev).

Runs sensors sequentially: one operator, a handful of AOIs — no concurrency
needed, and sequential failures isolate cleanly.
"""

import signal
import time
from datetime import UTC, datetime, timedelta

import psycopg
import structlog

from app.adapters.registry import all_adapters, get_adapter
from app.config import Settings
from app.ingest.pipeline import ingest_sensor

log = structlog.get_logger()


def poll_interval_hours(revisit_days: float | None, settings: Settings) -> float:
    if settings.ingest_interval_hours is not None:
        return settings.ingest_interval_hours
    return max(float(revisit_days or 1.0) * 12.0, settings.ingest_min_interval_hours)


def due_sensors(conn: psycopg.Connection, settings: Settings) -> list[str]:
    """Enabled, adapter-backed sensors whose last successful run is older
    than their poll interval (or that have never run)."""
    backed = set(all_adapters())
    rows = conn.execute(
        """SELECT s.id, s.revisit_days, MAX(r.finished_at) AS last_ok
           FROM sensors s
           LEFT JOIN ingestion_runs r
                  ON r.sensor_id = s.id AND r.status = 'success'
           WHERE s.enabled
           GROUP BY s.id, s.revisit_days"""
    ).fetchall()
    now = datetime.now(UTC)
    due = []
    for sensor_id, revisit_days, last_ok in rows:
        if sensor_id not in backed:
            continue
        interval = timedelta(hours=poll_interval_hours(revisit_days, settings))
        if last_ok is None or now - last_ok >= interval:
            due.append(sensor_id)
    return due


def run_due(conn: psycopg.Connection, settings: Settings, *, force: bool = False) -> None:
    sensors = (
        [s for s in all_adapters() if _is_enabled(conn, s)]
        if force
        else due_sensors(conn, settings)
    )
    for sensor_id in sensors:
        try:
            ingest_sensor(
                conn,
                get_adapter(sensor_id),
                backfill_days=settings.ingest_backfill_days,
                overlap_hours=settings.ingest_overlap_hours,
            )
        except Exception:
            # per-sensor isolation: a failed adapter doesn't stop the sweep
            log.exception("sensor_sweep_failed", sensor_id=sensor_id)


def _is_enabled(conn: psycopg.Connection, sensor_id: str) -> bool:
    row = conn.execute("SELECT enabled FROM sensors WHERE id = %s", (sensor_id,)).fetchone()
    return bool(row and row[0])


def serve(conn: psycopg.Connection, settings: Settings) -> None:
    """Poll loop: wake every `tick`, run whatever is due, sleep again.
    SIGINT/SIGTERM stop after the current sensor finishes."""
    stopped = False

    def _stop(signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True
        log.info("ingest_stopping", signal=signum)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info("ingest_started", tick_seconds=settings.ingest_tick_seconds)
    while not stopped:
        run_due(conn, settings)
        for _ in range(settings.ingest_tick_seconds):
            if stopped:
                break
            time.sleep(1)
    log.info("ingest_stopped")

"""On-demand backfill for one AOI: the last 90 days of every enabled sensor
plus daily rainfall.

Triggered by POST /v1/aois/{id}/backfill and by AOI creation, so a new area
isn't empty until the next scheduled sweep. Runs after the HTTP response
(FastAPI background task) on its own pooled connection. Idempotent — scenes
upsert on their natural key and analysis only fills what is missing — so a
repeat is harmless; the in-process claim set just stops duplicate work.
"""

import threading
from datetime import UTC, datetime

import psycopg
import structlog

from app.adapters.registry import all_adapters
from app.config import get_settings
from app.daily.pipeline import RAIN_SOURCE, ingest_rain
from app.ingest.pipeline import ingest_sensor
from app.ingest.scheduler import _is_enabled

log = structlog.get_logger()

BACKFILL_DAYS = 90

_lock = threading.Lock()
_running: set[str] = set()


def is_running(aoi_id: str) -> bool:
    with _lock:
        return aoi_id in _running


def claim(aoi_id: str) -> bool:
    with _lock:
        if aoi_id in _running:
            return False
        _running.add(aoi_id)
        return True


def release(aoi_id: str) -> None:
    with _lock:
        _running.discard(aoi_id)


def backfill_aoi(conn: psycopg.Connection, aoi_id: str, *, days: int = BACKFILL_DAYS) -> None:
    """Per-sensor failures are logged and isolated, like the scheduled sweep."""
    settings = get_settings()
    for sensor_id, adapter in all_adapters().items():
        if not _is_enabled(conn, sensor_id):
            continue
        try:
            ingest_sensor(
                conn,
                adapter,
                backfill_days=days,
                overlap_hours=settings.ingest_overlap_hours,
                analyze=settings.ingest_analyze,
                aoi_id=aoi_id,
            )
        except Exception:
            log.exception("backfill_sensor_failed", sensor_id=sensor_id, aoi_id=aoi_id)
    if _is_enabled(conn, RAIN_SOURCE):
        try:
            ingest_rain(conn, today=datetime.now(UTC).date(), backfill_days=days, aoi_id=aoi_id)
        except Exception:
            log.exception("backfill_rain_failed", aoi_id=aoi_id)

"""Entry point.

  python -m app.ingest                 poll loop
  python -m app.ingest --once          one sweep of all enabled adapter-backed
                                       sensors, then an independent catalog
                                       audit; exits 1 if any sweep raised, a
                                       sensor is stale, or the catalog has
                                       recent scenes the DB lacks
  python -m app.ingest --backfill AOI_ID --since YYYY-MM-DD [--until YYYY-MM-DD]
                       [--sensor SENSOR_ID]
                                       re-search one AOI over an explicit
                                       window and upsert (idempotent; leaves
                                       the sweep watermark alone)

Owns its own connection with autocommit=True so pipeline transaction blocks
are real commits (see ingest.pipeline's transaction model note).
"""

import argparse
import sys
from datetime import UTC, date, datetime

import psycopg
import structlog

from app.adapters.registry import all_adapters, get_adapter
from app.config import get_settings
from app.ingest.pipeline import backfill_aoi, missing_scenes, stale_sensors
from app.ingest.scheduler import _is_enabled, run_due, serve
from app.logging import configure_logging
from app.regions import ensure_region_aois

log = structlog.get_logger()

AUDIT_LOOKBACK_DAYS = 7


def _once(conn: psycopg.Connection) -> int:
    settings = get_settings()
    ensure_region_aois(conn)  # public regions' sample fields (idempotent)
    failed = run_due(conn, settings, force=True)
    enabled = [a for sid, a in all_adapters().items() if _is_enabled(conn, sid)]
    stale = stale_sensors(conn, enabled)
    gaps: dict[str, dict[str, list[str]]] = {}
    for adapter in enabled:
        if adapter.sensor_id in failed:
            continue  # already red; the catalog is likely unreachable
        try:
            found = missing_scenes(conn, adapter, lookback_days=AUDIT_LOOKBACK_DAYS)
        except Exception:
            log.exception("catalog_audit_failed", sensor_id=adapter.sensor_id)
            failed.append(adapter.sensor_id)
            continue
        if found:
            gaps[adapter.sensor_id] = found
    if failed or stale or gaps:
        log.error("sweep_unhealthy", failed=failed, stale=stale, gaps=gaps)
        return 1
    return 0


def _backfill(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until) if args.until else datetime.now(UTC).date()
    sensors = [args.sensor] if args.sensor else list(all_adapters())
    for sensor_id in sensors:
        stats = backfill_aoi(
            conn,
            get_adapter(sensor_id),
            args.backfill,
            since,
            until,
            analyze=get_settings().ingest_analyze,
        )
        print(
            f"{sensor_id}: found={stats.scenes_found} inserted={stats.scenes_inserted} "
            f"metrics={stats.metrics_written}"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.ingest")
    parser.add_argument("--once", action="store_true", help="single sweep + audit, then exit")
    parser.add_argument("--backfill", metavar="AOI_ID", help="backfill one AOI, then exit")
    parser.add_argument("--since", help="backfill window start (YYYY-MM-DD, inclusive)")
    parser.add_argument("--until", help="backfill window end (YYYY-MM-DD, default today)")
    parser.add_argument("--sensor", help="backfill only this sensor id (default: all)")
    args = parser.parse_args()
    if args.backfill and not args.since:
        parser.error("--backfill requires --since")

    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        if args.backfill:
            sys.exit(_backfill(conn, args))
        elif args.once:
            sys.exit(_once(conn))
        else:
            ensure_region_aois(conn)
            serve(conn, settings)


if __name__ == "__main__":
    main()

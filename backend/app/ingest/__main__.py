"""Entry point: `python -m app.ingest` runs the poll loop; `--once` runs a
single sweep of all enabled adapter-backed sensors (cron/manual use).

Owns its own connection with autocommit=True so pipeline transaction blocks
are real commits (see ingest.pipeline's transaction model note).
"""

import argparse
import sys

import psycopg

from app.adapters.registry import all_adapters
from app.config import get_settings
from app.ingest.pipeline import stale_sensors
from app.ingest.scheduler import _is_enabled, run_due, serve
from app.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.ingest")
    parser.add_argument("--once", action="store_true", help="single sweep, then exit")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        if args.once:
            run_due(conn, settings, force=True)
            enabled = [a for sid, a in all_adapters().items() if _is_enabled(conn, sid)]
            if stale_sensors(conn, enabled):
                sys.exit(1)  # make a silent stall visible as a red CI run
        else:
            serve(conn, settings)


if __name__ == "__main__":
    main()

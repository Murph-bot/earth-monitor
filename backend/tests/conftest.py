"""Shared test fixtures — real Postgres+PostGIS via docker compose.

Requires the db service: `docker compose up -d db`. Uses a separate
`earth_monitor_test` database; the `db` connection is never committed —
all writes roll back on close, so dev data is untouched.

The fixture is session-scoped: migrations run once per test session.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest

from app.config import get_settings

ADMIN_URL = "postgresql://postgres:postgres@localhost:5432/postgres"
TEST_URL = "postgresql://postgres:postgres@localhost:5432/earth_monitor_test"


@pytest.fixture(scope="session")
def db() -> Iterator[psycopg.Connection]:
    try:
        psycopg.connect(ADMIN_URL, connect_timeout=2).close()
    except psycopg.OperationalError:
        pytest.skip("docker compose up -d db first")

    os.environ["EM_DATABASE_URL"] = TEST_URL
    get_settings.cache_clear()

    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'earth_monitor_test'"
        ).fetchone()
        if not exists:
            admin.execute("CREATE DATABASE earth_monitor_test")

    from app.db.migrate import migrate

    migrate()

    conn = psycopg.connect(TEST_URL)  # never committed — rolls back on close
    yield conn
    conn.close()

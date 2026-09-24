"""Schema migrations — numbered SQL files applied in order, tracked in
`schema_migrations`. Run: `uv run python -m app.db.migrate`.

ClientCursor (simple query protocol) is required because each .sql file
contains multiple statements — psycopg's default extended protocol sends
them as prepared statements, which PostgreSQL rejects.
"""

import re
from pathlib import Path

import psycopg

from app.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATION_RE = re.compile(r"^(\d{4})_.*\.sql$")


def applied_versions(conn: psycopg.Connection) -> set[int]:
    # to_regclass returns NULL instead of raising — a failed SELECT would
    # poison the implicit transaction (psycopg3 autocommit-off semantics).
    row = conn.execute("SELECT to_regclass('schema_migrations')").fetchone()
    if not row or not row[0]:
        return set()
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def pending() -> list[tuple[int, Path]]:
    out = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = MIGRATION_RE.match(path.name)
        if m:
            out.append((int(m.group(1)), path))
    return out


def migrate() -> list[int]:
    """Apply pending migrations; returns versions applied this call."""
    applied: list[int] = []
    with psycopg.connect(get_settings().database_url, cursor_factory=psycopg.ClientCursor) as conn:
        done = applied_versions(conn)
        for version, path in pending():
            if version in done:
                continue
            sql = path.read_text()
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                    (version, path.name),
                )
            applied.append(version)
    return applied


if __name__ == "__main__":
    versions = migrate()
    print(f"applied {len(versions)} migration(s): {versions or 'none'}")

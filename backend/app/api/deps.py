"""Request-scoped dependencies: pooled DB connection, current user.

get_db yields a pooled autocommit connection — conn.transaction() blocks
are real commits here, savepoints under the test override (same model as
the ingest pipeline).

get_current_user is a PRE-AUTH STUB: it resolves/creates the user named by
EM_DEV_USER_EMAIL. Phase 8 replaces the internals of this dependency —
endpoints never see the difference.
"""

import uuid
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Request
from psycopg_pool import ConnectionPool

from app.config import get_settings


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.pool  # type: ignore[no-any-return]


def get_db(request: Request) -> Iterator[psycopg.Connection]:
    with _pool(request).connection() as conn:
        yield conn


DbConn = Annotated[psycopg.Connection, Depends(get_db)]


def get_current_user(db: DbConn) -> uuid.UUID:
    email = get_settings().dev_user_email
    with db.transaction():
        db.execute(
            """INSERT INTO users (email) VALUES (%s)
               ON CONFLICT (email) DO NOTHING""",
            (email,),
        )
        row = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    assert row is not None
    return row[0]  # type: ignore[no-any-return]


CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]

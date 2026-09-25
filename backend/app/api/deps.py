"""Request-scoped dependencies: pooled DB connection, current user.

get_db yields a pooled autocommit connection — conn.transaction() blocks
are real commits here, savepoints under the test override (same model as
the ingest pipeline).

get_current_user: `Authorization: Bearer <jwt>` wins — decoded and the
user must still exist and not be soft-deleted. With no header at all, the
EM_DEV_USER_EMAIL fallback keeps local dev frictionless; set it empty in
prod and every endpoint requires a real token.
"""

import uuid
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Request
from psycopg_pool import ConnectionPool

from app.api.errors import unauthorized
from app.config import get_settings
from app.security import decode_token


def _pool(request: Request) -> ConnectionPool:
    return request.app.state.pool  # type: ignore[no-any-return]


def get_db(request: Request) -> Iterator[psycopg.Connection]:
    with _pool(request).connection() as conn:
        yield conn


DbConn = Annotated[psycopg.Connection, Depends(get_db)]


def _dev_user(db: psycopg.Connection) -> uuid.UUID:
    email = get_settings().dev_user_email
    assert email is not None
    with db.transaction():
        db.execute(
            """INSERT INTO users (email) VALUES (%s)
               ON CONFLICT (email) DO NOTHING""",
            (email,),
        )
        row = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    assert row is not None
    return row[0]  # type: ignore[no-any-return]


def get_current_user(request: Request, db: DbConn) -> uuid.UUID:
    auth = request.headers.get("authorization")
    if auth is None:
        if get_settings().dev_user_email:
            return _dev_user(db)
        raise unauthorized()
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized("expected 'Authorization: Bearer <token>'")
    user_id = decode_token(token)
    if user_id is None:
        raise unauthorized("invalid or expired token")
    row = db.execute(
        "SELECT id FROM users WHERE id = %s AND deleted_at IS NULL", (user_id,)
    ).fetchone()
    if row is None:
        raise unauthorized("account not found")
    return user_id


CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]

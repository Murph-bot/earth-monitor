"""Auth endpoints — register, login, me.

Login failure is deliberately opaque: same 401 INVALID_CREDENTIALS for
unknown email and wrong password, and a dummy hash keeps the verify cost
paid either way so timing doesn't leak which emails exist.
"""

import uuid
from typing import cast

from fastapi import APIRouter, HTTPException
from psycopg import errors as pg_errors

from app.api.deps import CurrentUser, DbConn
from app.api.errors import unauthorized
from app.api.v1.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import hash_password, issue_token, verify_password

router = APIRouter()

_dummy: str | None = None


def _dummy_hash() -> str:
    """Timing parity: verifying a real-strength hash for unknown emails costs
    the same as a real verify, so login timing can't leak account existence."""
    global _dummy
    if _dummy is None:
        _dummy = hash_password("not-the-real-password")
    return _dummy


def _user_out(row: tuple[object, ...]) -> UserOut:
    return UserOut(
        id=cast(uuid.UUID, row[0]),
        email=cast(str, row[1]),
        display_name=cast("str | None", row[2]),
    )


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: DbConn) -> TokenOut:
    email = body.email.lower()
    try:
        with db.transaction():
            row = db.execute(
                """INSERT INTO users (email, password_hash, display_name)
                   VALUES (%s, %s, %s)
                   RETURNING id, email, display_name""",
                (email, hash_password(body.password), body.display_name),
            ).fetchone()
    except pg_errors.UniqueViolation:
        raise HTTPException(
            409, "email already registered", headers={"x-error-code": "EMAIL_TAKEN"}
        ) from None
    assert row is not None
    return TokenOut(token=issue_token(row[0]), user=_user_out(row))


@router.post("/auth/login")
def login(body: LoginIn, db: DbConn) -> TokenOut:
    row = db.execute(
        "SELECT id, email, display_name, password_hash FROM users WHERE email = %s",
        (body.email.lower(),),
    ).fetchone()
    ok = verify_password(body.password, row[3] if row and row[3] else _dummy_hash())
    if row is None or not ok:
        raise unauthorized("invalid credentials")
    return TokenOut(token=issue_token(row[0]), user=_user_out(row))


@router.get("/auth/me")
def me(user_id: CurrentUser, db: DbConn) -> UserOut:
    row = db.execute(
        "SELECT id, email, display_name FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    assert row is not None
    return _user_out(row)

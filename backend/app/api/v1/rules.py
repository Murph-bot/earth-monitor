"""Alert rule CRUD — scoped under the AOI they watch.

Ownership flows through the AOI (rules.user_id is denormalized for the
evaluator's convenience; authorization always joins back to aois).
"""

import uuid
from typing import Any

import psycopg
from fastapi import APIRouter, Query
from psycopg.types.json import Jsonb

from app.api.deps import CurrentUser, DbConn
from app.api.errors import not_found
from app.api.v1.schemas import (
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
    NotificationOut,
    Page,
)

router = APIRouter()

_COLS = """id, aoi_id, metric_name, rule_type, params, sensor_id,
           min_valid_pixel_pct, enabled, created_at"""


def _rule_out(row: tuple[Any, ...]) -> AlertRuleOut:
    return AlertRuleOut(
        id=row[0],
        aoi_id=row[1],
        metric_name=row[2],
        rule_type=row[3],
        params=row[4],
        sensor_id=row[5],
        min_valid_pixel_pct=row[6],
        enabled=row[7],
        created_at=row[8],
    )


def _own_aoi(db: psycopg.Connection, aoi_id: uuid.UUID, user_id: uuid.UUID) -> None:
    row = db.execute(
        "SELECT 1 FROM aois WHERE id = %s AND user_id = %s", (aoi_id, user_id)
    ).fetchone()
    if row is None:
        raise not_found("aoi")


def _own_rule(db: psycopg.Connection, rule_id: int, user_id: uuid.UUID) -> tuple[Any, ...]:
    row = db.execute(
        f"""SELECT {_COLS} FROM alert_rules r JOIN aois a ON a.id = r.aoi_id
            WHERE r.id = %s AND a.user_id = %s""",
        (rule_id, user_id),
    ).fetchone()
    if row is None:
        raise not_found("alert rule")
    return row


@router.post("/aois/{aoi_id}/rules", status_code=201)
def create_rule(
    aoi_id: uuid.UUID, body: AlertRuleCreate, db: DbConn, user_id: CurrentUser
) -> AlertRuleOut:
    _own_aoi(db, aoi_id, user_id)
    with db.transaction():
        row = db.execute(
            f"""INSERT INTO alert_rules
                    (aoi_id, user_id, metric_name, rule_type, params,
                     sensor_id, min_valid_pixel_pct, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_COLS}""",
            (
                aoi_id,
                user_id,
                body.metric_name,
                body.rule_type,
                Jsonb(body.params),
                body.sensor_id,
                body.min_valid_pixel_pct,
                body.enabled,
            ),
        ).fetchone()
    assert row is not None
    return _rule_out(row)


@router.get("/aois/{aoi_id}/rules")
def list_rules(aoi_id: uuid.UUID, db: DbConn, user_id: CurrentUser) -> Page[AlertRuleOut]:
    _own_aoi(db, aoi_id, user_id)
    rows = db.execute(
        f"SELECT {_COLS} FROM alert_rules WHERE aoi_id = %s ORDER BY created_at DESC",
        (aoi_id,),
    ).fetchall()
    return Page(items=[_rule_out(r) for r in rows], total=len(rows), limit=len(rows), offset=0)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: int, body: AlertRuleUpdate, db: DbConn, user_id: CurrentUser
) -> AlertRuleOut:
    _own_rule(db, rule_id, user_id)
    with db.transaction():
        if body.enabled is not None:
            db.execute("UPDATE alert_rules SET enabled = %s WHERE id = %s", (body.enabled, rule_id))
        if body.min_valid_pixel_pct is not None:
            db.execute(
                "UPDATE alert_rules SET min_valid_pixel_pct = %s WHERE id = %s",
                (body.min_valid_pixel_pct, rule_id),
            )
    return _rule_out(_own_rule(db, rule_id, user_id))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: DbConn, user_id: CurrentUser) -> None:
    _own_rule(db, rule_id, user_id)
    with db.transaction():
        db.execute("DELETE FROM alert_rules WHERE id = %s", (rule_id,))


@router.get("/notifications")
def list_notifications(
    db: DbConn,
    user_id: CurrentUser,
    unread: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[NotificationOut]:
    where = "user_id = %s" + (" AND read_at IS NULL" if unread else "")
    trow = db.execute(f"SELECT count(*) FROM notifications WHERE {where}", (user_id,)).fetchone()
    assert trow is not None
    rows = db.execute(
        f"""SELECT id, title, body, payload, channel, created_at, read_at
            FROM notifications WHERE {where}
            ORDER BY created_at DESC LIMIT %s OFFSET %s""",
        (user_id, limit, offset),
    ).fetchall()
    return Page(
        items=[
            NotificationOut(
                id=r[0],
                title=r[1],
                body=r[2],
                payload=r[3],
                channel=r[4],
                created_at=r[5],
                read_at=r[6],
            )
            for r in rows
        ],
        total=int(trow[0]),
        limit=limit,
        offset=offset,
    )


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, db: DbConn, user_id: CurrentUser) -> None:
    with db.transaction():
        cur = db.execute(
            """UPDATE notifications SET read_at = now()
               WHERE id = %s AND user_id = %s AND read_at IS NULL""",
            (notification_id, user_id),
        )
    if cur.rowcount == 0:
        raise not_found("notification")

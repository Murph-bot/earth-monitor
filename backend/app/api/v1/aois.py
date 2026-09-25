"""AOI endpoints — CRUD plus the two read faces clients actually use:
covered scenes and metric series.

Ownership is enforced by user_id on every query (404, never "exists but
not yours"). Geometry validation is delegated to PostGIS — the same
ST_GeomFromGeoJSON/ST_IsValid path ingestion trusts.
"""

import json
import uuid
from datetime import date as dt_date
from typing import Any

import psycopg
from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbConn
from app.api.errors import not_found
from app.api.v1.schemas import (
    AoiCreate,
    AoiDetail,
    AoiOut,
    AoiUpdate,
    Bbox,
    MetricPoint,
    MetricSeries,
    MetricsResponse,
    Page,
    SceneSummary,
    SensorStateOut,
)
from app.config import get_settings

router = APIRouter()

_AOI_COLS = "id, name, is_public, area_m2, created_at"


def _aoi_out(row: tuple[Any, ...]) -> AoiOut:
    return AoiOut(
        id=row[0],
        name=row[1],
        is_public=row[2],
        area_m2=row[3],
        created_at=row[4],
        bbox=Bbox(minx=row[5], miny=row[6], maxx=row[7], maxy=row[8]),
    )


def _get_aoi(
    db: psycopg.Connection, aoi_id: uuid.UUID, user_id: uuid.UUID
) -> psycopg.rows.TupleRow:
    row = db.execute(
        f"""SELECT {_AOI_COLS}, ST_XMin(bbox), ST_YMin(bbox), ST_XMax(bbox), ST_YMax(bbox)
            FROM aois WHERE id = %s AND user_id = %s""",
        (aoi_id, user_id),
    ).fetchone()
    if row is None:
        raise not_found("aoi")
    return row


@router.post("/aois", status_code=201)
def create_aoi(
    body: AoiCreate,
    db: DbConn,
    user_id: CurrentUser,
) -> AoiOut:
    geom = json.dumps(body.geojson)
    max_m2 = get_settings().max_aoi_area_km2 * 1e6
    try:
        with db.transaction():
            area = db.execute(
                "SELECT ST_Area(ST_GeomFromGeoJSON(%s)::geography)", (geom,)
            ).fetchone()
            if area is None or area[0] is None:
                raise ValueError("empty geometry")
            if float(area[0]) > max_m2:
                from fastapi import HTTPException

                raise HTTPException(
                    422,
                    f"aoi too large: {float(area[0]) / 1e6:.0f} km² "
                    f"(max {get_settings().max_aoi_area_km2:.0f} km²)",
                )
            row = db.execute(
                f"""INSERT INTO aois (user_id, name, is_public, geom, area_m2)
                    VALUES (%s, %s, %s,
                            ST_Multi(ST_GeomFromGeoJSON(%s)),
                            ST_Area(ST_GeomFromGeoJSON(%s)::geography))
                    RETURNING {_AOI_COLS},
                            ST_XMin(bbox), ST_YMin(bbox), ST_XMax(bbox), ST_YMax(bbox)""",
                (user_id, body.name, body.is_public, geom, geom),
            ).fetchone()
    except psycopg.Error as exc:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422, detail=f"invalid geometry: {exc.diag.message_primary or exc}"
        ) from exc
    assert row is not None
    return _aoi_out(row)


@router.get("/aois")
def list_aois(
    db: DbConn,
    user_id: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[AoiOut]:
    trow = db.execute("SELECT count(*) FROM aois WHERE user_id = %s", (user_id,)).fetchone()
    assert trow is not None
    total = int(trow[0])
    rows = db.execute(
        f"""SELECT {_AOI_COLS}, ST_XMin(bbox), ST_YMin(bbox), ST_XMax(bbox), ST_YMax(bbox)
            FROM aois WHERE user_id = %s ORDER BY created_at DESC
            LIMIT %s OFFSET %s""",
        (user_id, limit, offset),
    ).fetchall()
    return Page(items=[_aoi_out(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/aois/{aoi_id}")
def get_aoi(
    aoi_id: uuid.UUID,
    db: DbConn,
    user_id: CurrentUser,
) -> AoiDetail:
    row = _get_aoi(db, aoi_id, user_id)
    grow = db.execute("SELECT ST_AsGeoJSON(geom) FROM aois WHERE id = %s", (aoi_id,)).fetchone()
    assert grow is not None
    geom = grow[0]
    state = db.execute(
        """SELECT sensor_id, last_checked_at, last_scene_at
           FROM aoi_sensor_state WHERE aoi_id = %s""",
        (aoi_id,),
    ).fetchall()
    return AoiDetail(
        **_aoi_out(row).model_dump(),
        geom=json.loads(geom),
        sensor_state=[
            SensorStateOut(sensor_id=s[0], last_checked_at=s[1], last_scene_at=s[2]) for s in state
        ],
    )


@router.patch("/aois/{aoi_id}")
def update_aoi(
    aoi_id: uuid.UUID,
    body: AoiUpdate,
    db: DbConn,
    user_id: CurrentUser,
) -> AoiOut:
    _get_aoi(db, aoi_id, user_id)
    if body.name is None and body.is_public is None:
        return _aoi_out(_get_aoi(db, aoi_id, user_id))
    with db.transaction():
        if body.name is not None:
            db.execute("UPDATE aois SET name = %s WHERE id = %s", (body.name, aoi_id))
        if body.is_public is not None:
            db.execute("UPDATE aois SET is_public = %s WHERE id = %s", (body.is_public, aoi_id))
    return _aoi_out(_get_aoi(db, aoi_id, user_id))


@router.delete("/aois/{aoi_id}", status_code=204)
def delete_aoi(
    aoi_id: uuid.UUID,
    db: DbConn,
    user_id: CurrentUser,
) -> None:
    _get_aoi(db, aoi_id, user_id)
    with db.transaction():
        db.execute("DELETE FROM aois WHERE id = %s", (aoi_id,))


@router.get("/aois/{aoi_id}/scenes")
def aoi_scenes(
    aoi_id: uuid.UUID,
    db: DbConn,
    user_id: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sensor: str | None = None,
) -> Page[SceneSummary]:
    _get_aoi(db, aoi_id, user_id)
    where = "sa.aoi_id = %s" + (" AND s.sensor_id = %s" if sensor else "")
    params = (aoi_id, sensor) if sensor else (aoi_id,)
    trow = db.execute(
        f"SELECT count(*) FROM scene_aois sa JOIN scenes s ON s.id = sa.scene_id WHERE {where}",
        params,
    ).fetchone()
    assert trow is not None
    total = int(trow[0])
    rows = db.execute(
        f"""SELECT s.id, s.scene_key, s.sensor_id, s.collection_id, s.acquired_at,
                   s.cloud_cover, sa.coverage
            FROM scene_aois sa JOIN scenes s ON s.id = sa.scene_id
            WHERE {where} ORDER BY s.acquired_at DESC LIMIT %s OFFSET %s""",
        (*params, limit, offset),
    ).fetchall()
    return Page(
        items=[
            SceneSummary(
                id=r[0],
                scene_key=r[1],
                sensor_id=r[2],
                collection_id=r[3],
                acquired_at=r[4],
                cloud_cover=r[5],
                coverage=r[6],
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/aois/{aoi_id}/metrics")
def aoi_metrics(
    aoi_id: uuid.UUID,
    db: DbConn,
    user_id: CurrentUser,
    metric: str | None = None,
    sensor: str | None = None,
    date_from: dt_date | None = None,
    date_to: dt_date | None = None,
) -> MetricsResponse:
    _get_aoi(db, aoi_id, user_id)
    clauses: list[str] = ["m.aoi_id = %s"]
    params: list[object] = [aoi_id]
    if metric:
        clauses.append("m.metric_name = %s")
        params.append(metric)
    if sensor:
        clauses.append("m.sensor_id = %s")
        params.append(sensor)
    if date_from:
        clauses.append("m.date >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("m.date <= %s")
        params.append(date_to)
    rows = db.execute(
        f"""SELECT m.metric_name, m.sensor_id, m.unit, m.date, s.acquired_at,
                   m.scene_id, m.value, m.valid_pixel_pct
            FROM metrics m JOIN scenes s ON s.id = m.scene_id
            WHERE {" AND ".join(clauses)}
            ORDER BY m.metric_name, m.sensor_id, m.date""",
        tuple(params),
    ).fetchall()

    series: dict[tuple[str, str, str], list[MetricPoint]] = {}
    for name, sid, unit, d, acq, sid_, val, pct in rows:
        series.setdefault((name, sid, unit), []).append(
            MetricPoint(date=d, acquired_at=acq, scene_id=sid_, value=val, valid_pixel_pct=pct)
        )
    return MetricsResponse(
        aoi_id=aoi_id,
        series=[
            MetricSeries(metric_name=k[0], sensor_id=k[1], unit=k[2], points=v)
            for k, v in series.items()
        ],
    )

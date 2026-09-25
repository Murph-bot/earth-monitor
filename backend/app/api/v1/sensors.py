"""Sensor catalog endpoints — public reference data from the seeded tables."""

from fastapi import APIRouter

from app.api.deps import DbConn
from app.api.errors import not_found
from app.api.v1.schemas import BandOut, CollectionOut, Page, SensorDetail, SensorOut

router = APIRouter()


@router.get("/sensors")
def list_sensors(db: DbConn) -> Page[SensorOut]:
    rows = db.execute(
        """SELECT id, name, kind, provider, resolution_m, revisit_days, enabled
           FROM sensors ORDER BY id"""
    ).fetchall()
    items = [
        SensorOut(
            id=r[0],
            name=r[1],
            kind=r[2],
            provider=r[3],
            resolution_m=float(r[4]) if r[4] is not None else None,
            revisit_days=float(r[5]) if r[5] is not None else None,
            enabled=r[6],
        )
        for r in rows
    ]
    return Page(items=items, total=len(items), limit=len(items), offset=0)


@router.get("/sensors/{sensor_id}")
def get_sensor(sensor_id: str, db: DbConn) -> SensorDetail:
    row = db.execute(
        """SELECT id, name, kind, provider, resolution_m, revisit_days, enabled,
                  license_text
           FROM sensors WHERE id = %s""",
        (sensor_id,),
    ).fetchone()
    if row is None:
        raise not_found("sensor")

    collections = db.execute(
        "SELECT id, catalog, stac_url, processing_level FROM collections WHERE sensor_id = %s",
        (sensor_id,),
    ).fetchall()
    bands = db.execute(
        """SELECT name, asset_key, kind, resolution_m, scale, dn_offset
           FROM bands WHERE sensor_id = %s ORDER BY name""",
        (sensor_id,),
    ).fetchall()
    return SensorDetail(
        id=row[0],
        name=row[1],
        kind=row[2],
        provider=row[3],
        resolution_m=float(row[4]) if row[4] is not None else None,
        revisit_days=float(row[5]) if row[5] is not None else None,
        enabled=row[6],
        license_text=row[7],
        collections=[
            CollectionOut(id=c[0], catalog=c[1], stac_url=c[2], processing_level=c[3])
            for c in collections
        ],
        bands=[
            BandOut(
                name=b[0],
                asset_key=b[1],
                kind=b[2],
                resolution_m=float(b[3]) if b[3] is not None else None,
                scale=b[4],
                dn_offset=b[5],
            )
            for b in bands
        ],
    )

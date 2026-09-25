"""Dynamic map tiles from provider COGs — the TiTiler role, in-process.

GET /v1/tiles/scenes/{id}/tilejson.json  -> MapLibre source descriptor
GET /v1/tiles/scenes/{id}/{z}/{x}/{y}.png -> rendered RGB(A) tile

Scene pixels are immutable, so tiles are HTTP-cacheable for 24h and
LRU-cached in process. Band choice: ?assets=blue,green,red (defaults to
the sensor's blue/green/red bands for truecolor).
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from rio_tiler.errors import TileOutsideBounds

from app.api.deps import DbConn
from app.api.errors import not_found
from app.tiles.render import render_png

router = APIRouter()

_DEFAULT_RGB = ("blue", "green", "red")


def _scene_for_tiles(db: Any, scene_id: int) -> tuple[Any, ...]:
    row: tuple[Any, ...] | None = db.execute(
        """SELECT s.sensor_id, s.assets, s.collection_id,
                  ST_XMin(s.bbox), ST_YMin(s.bbox), ST_XMax(s.bbox), ST_YMax(s.bbox)
           FROM scenes s WHERE s.id = %s""",
        (scene_id,),
    ).fetchone()
    if row is None:
        raise not_found("scene")
    return row


def _resolve_bands(
    db: Any, sensor_id: str, names: tuple[str, ...]
) -> list[tuple[str, float, float]]:
    """name -> (asset_key, scale, dn_offset) for the sensor's bands."""
    rows = db.execute(
        """SELECT name, asset_key, scale, dn_offset FROM bands
           WHERE sensor_id = %s AND name = ANY(%s)""",
        (sensor_id, list(names)),
    ).fetchall()
    by_name = {r[0]: (r[1], float(r[2]), float(r[3])) for r in rows}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise HTTPException(422, f"unknown bands for {sensor_id}: {missing}")
    return [by_name[n] for n in names]


def _pick_hrefs(
    db: Any, sensor_id: str, assets: dict[str, Any], band_names: str | None
) -> tuple[tuple[str, ...], tuple[tuple[float, float], ...]]:
    names = tuple(band_names.split(",")) if band_names else _DEFAULT_RGB
    specs = _resolve_bands(db, sensor_id, names)
    hrefs: list[str] = []
    for asset_key, _scale, _off in specs:
        href = assets.get(asset_key)
        if href is None:
            raise HTTPException(404, f"scene lacks asset '{asset_key}'")
        hrefs.append(href)
    return tuple(hrefs), tuple((s, o) for _k, s, o in specs)


@router.get("/tiles/scenes/{scene_id}/tilejson.json")
def tilejson(scene_id: int, request: Request, db: DbConn) -> dict[str, Any]:
    sensor_id, _assets, _col, minx, miny, maxx, maxy = _scene_for_tiles(db, scene_id)
    lic = db.execute("SELECT license_text FROM sensors WHERE id = %s", (sensor_id,)).fetchone()
    base = str(request.base_url).rstrip("/")
    return {
        "tilejson": "3.0.0",
        "name": f"scene {scene_id}",
        "tiles": [f"{base}/v1/tiles/scenes/{scene_id}/{{z}}/{{x}}/{{y}}.png"],
        "bounds": [float(minx), float(miny), float(maxx), float(maxy)],
        "minzoom": 6,
        "maxzoom": 15,  # ~10 m at z15 — S2's native floor; deeper zoom upsamples
        "attribution": lic[0] if lic else "",
    }


@router.get("/tiles/scenes/{scene_id}/{z}/{x}/{y}.png")
def tile_png(
    scene_id: int,
    z: int,
    x: int,
    y: int,
    db: DbConn,
    assets: str | None = Query(None, description="comma-separated band names"),
    stretch: float = Query(0.3, gt=0, le=10, description="reflectance display max"),
) -> Response:
    if not (0 <= z <= 24 and 0 <= x < (1 << z) and 0 <= y < (1 << z)):
        raise HTTPException(422, "invalid tile address")
    sensor_id, scene_assets, _col, *_ = _scene_for_tiles(db, scene_id)
    hrefs, scale_offsets = _pick_hrefs(db, sensor_id, dict(scene_assets), assets)
    try:
        png = render_png(hrefs, scale_offsets, stretch, x, y, z)
    except TileOutsideBounds:
        raise not_found("tile (outside scene bounds)") from None
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )

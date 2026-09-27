"""Scene detail endpoint."""

import json

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbConn
from app.api.errors import not_found
from app.api.v1.schemas import Bbox, SceneDetail

router = APIRouter()

# A scene is visible to a user when it covers one of their AOIs; scenes
# are a shared catalog, so ownership lives on the AOI side.
VISIBLE_TO = """EXISTS (SELECT 1 FROM scene_aois sa JOIN aois a ON a.id = sa.aoi_id
                         WHERE sa.scene_id = s.id AND a.user_id = %s)"""


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: int, db: DbConn, user_id: CurrentUser) -> SceneDetail:
    row = db.execute(
        """SELECT id, scene_key, sensor_id, collection_id, acquired_at, cloud_cover,
                  epsg, ST_AsGeoJSON(footprint),
                  ST_XMin(bbox), ST_YMin(bbox), ST_XMax(bbox), ST_YMax(bbox),
                  assets, properties
           FROM scenes s WHERE id = %s AND """
        + VISIBLE_TO,
        (scene_id, user_id),
    ).fetchone()
    if row is None:
        raise not_found("scene")
    return SceneDetail(
        id=row[0],
        scene_key=row[1],
        sensor_id=row[2],
        collection_id=row[3],
        acquired_at=row[4],
        cloud_cover=row[5],
        epsg=row[6],
        footprint=json.loads(row[7]),
        bbox=Bbox(minx=row[8], miny=row[9], maxx=row[10], maxy=row[11]),
        assets=dict(row[12]),
        properties=dict(row[13]),
    )

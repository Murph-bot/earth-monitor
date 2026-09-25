"""API endpoint tests — TestClient over the real test DB.

get_db is overridden to yield the session `db` conn, so endpoint reads see
fixture data and endpoint writes ride savepoints (rolled back at teardown).
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from starlette.testclient import TestClient

from app.api.deps import get_db
from app.main import create_app

AOI: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [[[22.7, 40.55], [22.72, 40.55], [22.72, 40.57], [22.7, 40.57], [22.7, 40.55]]],
}
COVERING: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [[[22.6, 40.5], [22.8, 40.5], [22.8, 40.6], [22.6, 40.6], [22.6, 40.5]]],
}


@pytest.fixture
def client(clean: psycopg.Connection) -> Iterator[TestClient]:
    app = create_app()

    def _db() -> Iterator[psycopg.Connection]:
        yield clean

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def aoi_id(client: TestClient) -> str:
    r = client.post("/v1/aois", json={"name": "test field", "geojson": AOI})
    assert r.status_code == 201, r.text
    return r.json()["id"]  # type: ignore[no-any-return]


def test_health(client: TestClient) -> None:
    assert client.get("/v1/aois").status_code == 200
    assert client.get("/v1/health").json() == {"status": "ok", "db": "ok"}


def test_aoi_crud(client: TestClient, aoi_id: str) -> None:
    listing = client.get("/v1/aois").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == aoi_id
    assert listing["items"][0]["area_m2"] > 0

    detail = client.get(f"/v1/aois/{aoi_id}").json()
    assert detail["geom"]["type"] == "MultiPolygon"  # normalized at write
    assert detail["sensor_state"] == []

    r = client.patch(f"/v1/aois/{aoi_id}", json={"name": "renamed", "is_public": True})
    assert r.status_code == 200 and r.json()["name"] == "renamed" and r.json()["is_public"]

    assert client.delete(f"/v1/aois/{aoi_id}").status_code == 204
    r = client.get(f"/v1/aois/{aoi_id}")
    assert r.status_code == 404
    body = r.json()
    assert set(body["error"]) == {"code", "message"}


def test_aoi_validation(client: TestClient) -> None:
    r = client.post(
        "/v1/aois", json={"name": "pt", "geojson": {"type": "Point", "coordinates": [0, 0]}}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION"

    huge = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
    }
    r = client.post("/v1/aois", json={"name": "huge", "geojson": huge})
    assert r.status_code == 422 and "too large" in r.json()["error"]["message"]


def _insert_scene_with_coverage(db: psycopg.Connection, aoi_id: str) -> int:
    sid = db.execute(
        """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at,
                               cloud_cover, footprint, assets, properties)
           VALUES ('sentinel-2-c1-l2a', 'sentinel-2', 'SCENE_API_1', %s, 3.0,
                   ST_Multi(ST_GeomFromGeoJSON(%s)), '{"red":"https://x/red.tif"}', '{}')
           RETURNING id""",
        (datetime(2026, 9, 24, 9, 30, tzinfo=UTC), json.dumps(COVERING)),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO scene_aois (scene_id, aoi_id, coverage) VALUES (%s, %s, 0.95)",
        (sid, aoi_id),
    )
    return int(sid)


def test_aoi_scenes_and_metrics(client: TestClient, clean: psycopg.Connection, aoi_id: str) -> None:
    scene_id = _insert_scene_with_coverage(clean, aoi_id)
    clean.execute(
        """INSERT INTO metrics (aoi_id, scene_id, sensor_id, date, metric_name,
                               value, unit, valid_pixel_pct)
           VALUES (%s, %s, 'sentinel-2', '2026-09-24', 'ndvi_mean', 0.5, 'index', 0.98)""",
        (aoi_id, scene_id),
    )

    scenes = client.get(f"/v1/aois/{aoi_id}/scenes").json()
    assert scenes["total"] == 1
    assert scenes["items"][0]["coverage"] == pytest.approx(0.95)
    assert scenes["items"][0]["cloud_cover"] == pytest.approx(3.0)

    metrics = client.get(f"/v1/aois/{aoi_id}/metrics").json()
    assert len(metrics["series"]) == 1
    s = metrics["series"][0]
    assert s["metric_name"] == "ndvi_mean" and s["unit"] == "index"
    assert s["points"][0]["value"] == 0.5 and s["points"][0]["date"] == "2026-09-24"

    filtered = client.get(f"/v1/aois/{aoi_id}/metrics?metric=ndwi_mean").json()
    assert filtered["series"] == []


def test_sensors(client: TestClient) -> None:
    sensors = client.get("/v1/sensors").json()
    ids = {s["id"] for s in sensors["items"]}
    assert {"sentinel-2", "landsat-8-9", "sentinel-1", "viirs"} <= ids

    detail = client.get("/v1/sensors/sentinel-2").json()
    assert detail["license_text"] and len(detail["bands"]) == 9
    assert {c["id"] for c in detail["collections"]} == {"sentinel-2-c1-l2a", "sentinel-2"}

    assert client.get("/v1/sensors/nope").status_code == 404


def test_scene_detail(client: TestClient, clean: psycopg.Connection, aoi_id: str) -> None:
    scene_id = _insert_scene_with_coverage(clean, aoi_id)
    detail = client.get(f"/v1/scenes/{scene_id}").json()
    assert detail["scene_key"] == "SCENE_API_1"
    assert detail["footprint"]["type"] == "MultiPolygon"
    assert detail["assets"]["red"] == "https://x/red.tif"

    assert client.get("/v1/scenes/999999").status_code == 404


def test_tiles(client: TestClient, clean: psycopg.Connection, aoi_id: str) -> None:
    scene_id = _insert_scene_with_coverage(clean, aoi_id)

    tj = client.get(f"/v1/tiles/scenes/{scene_id}/tilejson.json")
    assert tj.status_code == 200
    body = tj.json()
    assert body["tiles"][0].endswith(f"/v1/tiles/scenes/{scene_id}/{{z}}/{{x}}/{{y}}.png")
    assert len(body["bounds"]) == 4

    assert client.get("/v1/tiles/scenes/999999/tilejson.json").status_code == 404
    # x=2 out of range at z=1 (max 1) -> invalid tile address
    assert client.get(f"/v1/tiles/scenes/{scene_id}/1/2/0.png").status_code == 422
    # scene assets only carry 'red' -> truecolor band hrefs missing
    r = client.get(f"/v1/tiles/scenes/{scene_id}/10/500/400.png")
    assert r.status_code == 404 and "lacks asset" in r.json()["error"]["message"]
    # unknown band names rejected before any COG read
    r = client.get(f"/v1/tiles/scenes/{scene_id}/10/500/400.png?assets=fake")
    assert r.status_code == 422 and "unknown bands" in r.json()["error"]["message"]


def test_pagination(client: TestClient, clean: psycopg.Connection, aoi_id: str) -> None:
    for i in range(3):
        clean.execute(
            """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at,
                                   footprint, assets)
               VALUES ('sentinel-2-c1-l2a', 'sentinel-2', %s, %s,
                       ST_Multi(ST_GeomFromGeoJSON(%s)), '{}')""",
            (f"P{i}", datetime(2026, 9, 20 + i, tzinfo=UTC), json.dumps(COVERING)),
        )
    rows = clean.execute("SELECT id FROM scenes WHERE scene_key LIKE 'P%' ORDER BY id").fetchall()
    for r in rows:
        clean.execute(
            "INSERT INTO scene_aois (scene_id, aoi_id, coverage) VALUES (%s, %s, 0.5)",
            (r[0], aoi_id),
        )
    page = client.get(f"/v1/aois/{aoi_id}/scenes?limit=2&offset=1").json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get(f"/v1/aois/{aoi_id}/scenes?limit=999").status_code == 422

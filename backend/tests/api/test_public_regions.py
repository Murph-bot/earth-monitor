"""Public region registry + /v1/public/region/{slug}/summary."""

import json
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from starlette.testclient import TestClient

from app.api.v1 import public
from app.regions import REGIONS, SYSTEM_EMAIL, ensure_region_aois


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    public.clear_cache()


def test_registry_has_thessaly_and_attica() -> None:
    assert set(REGIONS) == {"thessaly", "attica"}
    for r in REGIONS.values():
        x0, y0, x1, y1 = r.bbox
        sx0, sy0, sx1, sy1 = r.sample_bbox
        assert x0 < x1 and y0 < y1
        assert x0 <= sx0 < sx1 <= x1 and y0 <= sy0 < sy1 <= y1  # sample inside region
        assert (sx1 - sx0) * (sy1 - sy0) < 0.002  # sample field stays tiny (~2 km)
    assert REGIONS["attica"].bbox == (22.85, 37.55, 24.15, 38.45)
    # Athens (Syntagma) is in Attica, not Thessaly
    ax0, ay0, ax1, ay1 = REGIONS["attica"].bbox
    assert ax0 < 23.735 < ax1 and ay0 < 37.976 < ay1


@pytest.mark.parametrize("slug", ["thessaly", "attica"])
def test_summary_for_each_region(client: TestClient, slug: str) -> None:
    r = client.get(f"/v1/public/region/{slug}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["region"] == slug
    assert body["name"] == REGIONS[slug].name
    assert body["bounds"] == list(REGIONS[slug].bbox)
    assert body["greenness"]["mean"] is None  # empty DB → nulls, not placeholders
    assert body["scenes"] == {"clear": 0, "cloudy": 0, "latest_scene_at": None}
    assert "public" in r.headers["cache-control"]


def test_unknown_region_404(client: TestClient) -> None:
    r = client.get("/v1/public/region/atlantis/summary")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "REGION_NOT_FOUND"


def test_list_regions(client: TestClient) -> None:
    slugs = [r["slug"] for r in client.get("/v1/public/regions").json()]
    assert slugs == ["thessaly", "attica"]


def _scene(db: psycopg.Connection, key: str, lon: float, lat: float, cloud: float) -> None:
    fp = {
        "type": "Polygon",
        "coordinates": [
            [[lon, lat], [lon + 0.1, lat], [lon + 0.1, lat + 0.1], [lon, lat + 0.1], [lon, lat]]
        ],
    }
    db.execute(
        """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at, cloud_cover,
                               footprint, assets, properties)
           VALUES ('sentinel-2-c1-l2a', 'sentinel-2', %s, %s, %s,
                   ST_Multi(ST_GeomFromGeoJSON(%s)), '{}', '{}')""",
        (key, datetime.now(UTC) - timedelta(days=1), cloud, json.dumps(fp)),
    )


def test_summaries_are_scoped_per_region(client: TestClient, clean: psycopg.Connection) -> None:
    _scene(clean, "ATTICA_CLEAR", 23.5, 38.0, 5.0)
    _scene(clean, "THESSALY_CLOUDY", 22.5, 39.5, 80.0)
    attica = client.get("/v1/public/region/attica/summary").json()["scenes"]
    thessaly = client.get("/v1/public/region/thessaly/summary").json()["scenes"]
    assert (attica["clear"], attica["cloudy"]) == (1, 0)
    assert (thessaly["clear"], thessaly["cloudy"]) == (0, 1)


def test_ensure_region_aois_is_idempotent(clean: psycopg.Connection) -> None:
    assert sorted(ensure_region_aois(clean)) == ["attica", "thessaly"]
    assert ensure_region_aois(clean) == []
    rows = clean.execute(
        """SELECT a.name, a.is_public, a.area_m2 FROM aois a JOIN users u ON u.id = a.user_id
           WHERE u.email = %s ORDER BY a.name""",
        (SYSTEM_EMAIL,),
    ).fetchall()
    assert [r[0] for r in rows] == ["region:attica", "region:thessaly"]
    assert all(r[1] for r in rows)
    assert all(r[2] < 15e6 for r in rows)  # each sample field well under 15 km²

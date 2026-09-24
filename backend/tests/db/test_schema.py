"""Schema integration test — real Postgres+PostGIS via docker compose."""

import psycopg


def test_migrations_are_idempotent(db: psycopg.Connection) -> None:
    from app.db.migrate import migrate

    assert migrate() == []  # db fixture already migrated; second run = no-op


def test_expected_tables_exist(db: psycopg.Connection) -> None:
    rows = db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    tables = {r[0] for r in rows}
    expected = {
        "users",
        "aois",
        "sensors",
        "collections",
        "bands",
        "scenes",
        "scene_aois",
        "metrics",
        "ingestion_runs",
        "aoi_sensor_state",
        "alert_rules",
        "notifications",
        "devices",
        "schema_migrations",
    }
    assert expected <= tables


def test_spatial_roundtrip(db: psycopg.Connection) -> None:
    """Insert user → aoi → scene → metric; verify spatial join + generated cols."""
    user_id = db.execute(
        "INSERT INTO users (email) VALUES ('t@example.com') RETURNING id"
    ).fetchone()[0]

    aoi_geojson = (
        '{"type":"Polygon","coordinates":[[[22.7,40.55],[22.72,40.55],'
        "[22.72,40.57],[22.7,40.57],[22.7,40.55]]]}"
    )
    row = db.execute(
        """INSERT INTO aois (user_id, name, geom, area_m2)
           VALUES (%s, 'test field',
                   ST_Multi(ST_GeomFromGeoJSON(%s)),
                   ST_Area(ST_GeomFromGeoJSON(%s)::geography))
           RETURNING id, bbox IS NOT NULL, area_m2""",
        (user_id, aoi_geojson, aoi_geojson),
    ).fetchone()
    aoi_id, bbox_generated, area = row
    assert bbox_generated and area > 0  # ~4 km² expected

    footprint = (
        '{"type":"Polygon","coordinates":[[[22.6,40.5],[22.8,40.5],'
        "[22.8,40.6],[22.6,40.6],[22.6,40.5]]]}"
    )
    scene_id = db.execute(
        """INSERT INTO scenes (collection_id, sensor_id, scene_key, acquired_at,
                              footprint, assets)
           VALUES ('sentinel-2-c1-l2a', 'sentinel-2', 'TEST_SCENE_1', now(),
                   ST_Multi(ST_GeomFromGeoJSON(%s)), '{}')
           RETURNING id""",
        (footprint,),
    ).fetchone()[0]

    # the spatial join the ingestion pipeline will run:
    coverage = db.execute(
        """SELECT ST_Area(ST_Intersection(s.footprint::geography, a.geom::geography))
                  / ST_Area(a.geom::geography)
           FROM scenes s, aois a
           WHERE s.id = %s AND a.id = %s AND ST_Intersects(s.footprint, a.geom)""",
        (scene_id, aoi_id),
    ).fetchone()[0]
    assert coverage is not None and coverage > 0.9

    db.execute(
        """INSERT INTO metrics (aoi_id, scene_id, sensor_id, date, metric_name,
                               value, unit, valid_pixel_pct)
           VALUES (%s, %s, 'sentinel-2', CURRENT_DATE, 'ndvi_mean', 0.62,
                   'index', 0.956)""",
        (aoi_id, scene_id),
    )
    # idempotent reprocess: same (aoi, scene, metric) upserts
    row = db.execute(
        """INSERT INTO metrics (aoi_id, scene_id, sensor_id, date, metric_name,
                               value, unit, valid_pixel_pct)
           VALUES (%s, %s, 'sentinel-2', CURRENT_DATE, 'ndvi_mean', 0.63,
                   'index', 0.95)
           ON CONFLICT (aoi_id, scene_id, metric_name)
           DO UPDATE SET value = EXCLUDED.value
           RETURNING value""",
        (aoi_id, scene_id),
    ).fetchone()
    assert row[0] == 0.63


def test_seed_sensors_loaded(db: psycopg.Connection) -> None:
    count = db.execute("SELECT count(*) FROM bands WHERE sensor_id = 'sentinel-2'").fetchone()[0]
    assert count == 9

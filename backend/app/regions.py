"""Public regions — the registry behind /v1/public/region/{slug}/summary.

A region is a named lon/lat box the landing page aggregates over, plus one
small "sample" field (~2 km) that the system keeps monitored so a region has
data even before any user draws an area there. Sample fields are deliberately
tiny and sit inside a single Sentinel-2 MGRS tile, so each region costs about
two S2 scenes and one or two Landsat scenes a week (metadata + a few KB of
windowed pixel reads) — sized for the free Render + Neon tier.

Adding a region = one entry here; `ensure_region_aois` seeds its sample field
on the next ingest sweep.
"""

import json
from dataclasses import dataclass

import psycopg

type BBox = tuple[float, float, float, float]  # minx, miny, maxx, maxy (EPSG:4326)

SYSTEM_EMAIL = "regions@system.kampos"


@dataclass(frozen=True)
class Region:
    slug: str
    name: str
    bbox: BBox
    sample_bbox: BBox  # small monitored field inside `bbox`
    source: str


REGIONS: dict[str, Region] = {
    r.slug: r
    for r in [
        Region(
            slug="thessaly",
            name="Thessaly",
            # the plain plus Pelion/Pindus rims
            bbox=(21.3, 39.0, 23.6, 40.2),
            # farmland in the Thessaly plain (same box as the Landsat live test);
            # S2 tile T34SFJ only
            sample_bbox=(22.60, 39.50, 22.64, 39.53),
            source="Periphery of Thessaly, approx. extent (ELSTAT/OSM admin_level 4)",
        ),
        Region(
            slug="attica",
            name="Attica",
            # mainland Attica + Salamis/Aegina. Excludes the region's far
            # islands (Kythira, Hydra, Spetses) and the Troezen peninsula —
            # including them would triple the box for sea and few fields.
            bbox=(22.85, 37.55, 24.15, 38.45),
            # Thriasio plain farmland (Elefsina/Aspropyrgos); S2 tile T34SGH
            # only. The Mesogeia plain sits in the T34SGH/T35SKC overlap and
            # would double the scene count.
            sample_bbox=(23.55, 38.05, 23.57, 38.07),
            source="Attica Region, approx. mainland extent (OSM admin_level 4)",
        ),
    ]
}


def get_region(slug: str) -> Region | None:
    return REGIONS.get(slug)


def _polygon(b: BBox) -> dict[str, object]:
    x0, y0, x1, y1 = b
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def region_aoi_name(region: Region) -> str:
    return f"region:{region.slug}"


def ensure_region_aois(conn: psycopg.Connection) -> list[str]:
    """Idempotently create the system user and one public sample AOI per
    region; returns the slugs created this call. Existing sample AOIs are left
    untouched (an operator may have reshaped one)."""
    created: list[str] = []
    with conn.transaction():
        row = conn.execute(
            """INSERT INTO users (email, display_name) VALUES (%s, 'Kampos regions')
               ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
               RETURNING id""",
            (SYSTEM_EMAIL,),
        ).fetchone()
        assert row is not None
        user_id = row[0]
        for region in REGIONS.values():
            name = region_aoi_name(region)
            exists = conn.execute(
                "SELECT 1 FROM aois WHERE user_id = %s AND name = %s", (user_id, name)
            ).fetchone()
            if exists:
                continue
            geom = json.dumps(_polygon(region.sample_bbox))
            conn.execute(
                """INSERT INTO aois (user_id, name, is_public, geom, area_m2)
                   VALUES (%s, %s, true, ST_Multi(ST_GeomFromGeoJSON(%s)),
                           ST_Area(ST_GeomFromGeoJSON(%s)::geography))""",
                (user_id, name, geom, geom),
            )
            created.append(region.slug)
    return created

"""Analysis runner — turns cataloged scenes into metrics.

Self-healing by construction: the pending set is "(scene, aoi) pairs that
lack rows for some module", not "scenes inserted this run". A crash between
scene insert and analysis is repaired by the next sweep; a new module added
later backfills every historical scene automatically.

Pixels are read here, not in the ingest sweep — rasterio COG reads are slow
network I/O and must not sit inside the metadata transaction.
"""

import json
from dataclasses import dataclass

import numpy as np
import psycopg
import structlog
from affine import Affine
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

from app.adapters.base import AdapterError, GeoJSONGeom, SceneMeta, SensorAdapter
from app.analysis.base import AnalysisModule
from app.analysis.registry import modules_for

log = structlog.get_logger()


@dataclass(frozen=True)
class PendingPair:
    scene_id: int
    meta: SceneMeta
    aoi_id: str
    aoi_geom: GeoJSONGeom


def _pending_pairs(conn: psycopg.Connection, sensor_id: str) -> list[PendingPair]:
    """Every materialized (scene, aoi) coverage pair for the sensor."""
    rows = conn.execute(
        """SELECT s.id, s.scene_key, s.collection_id, c.catalog, s.acquired_at,
                  s.cloud_cover, s.epsg,
                  ST_XMin(s.bbox), ST_YMin(s.bbox), ST_XMax(s.bbox), ST_YMax(s.bbox),
                  ST_AsGeoJSON(s.footprint), s.assets, s.properties,
                  a.id, ST_AsGeoJSON(a.geom)
           FROM scene_aois sa
           JOIN scenes s ON s.id = sa.scene_id
           JOIN collections c ON c.id = s.collection_id
           JOIN aois a ON a.id = sa.aoi_id
           WHERE s.sensor_id = %s
           ORDER BY s.acquired_at""",
        (sensor_id,),
    ).fetchall()
    return [
        PendingPair(
            scene_id=r[0],
            meta=SceneMeta(
                scene_id=r[1],
                sensor_id=sensor_id,
                collection=r[2],
                catalog=r[3],
                acquired_at=r[4],
                bbox=(r[7], r[8], r[9], r[10]),
                geometry=json.loads(r[11]),
                cloud_cover=r[5],
                epsg=r[6],
                assets=dict(r[12]),
                properties=dict(r[13]),
            ),
            aoi_id=str(r[14]),
            aoi_geom=json.loads(r[15]),
        )
        for r in rows
    ]


def _inside_aoi(
    geom: GeoJSONGeom, shape: tuple[int, ...], transform: Affine, epsg: int
) -> np.ndarray:
    """True for pixels inside the AOI polygon on the reference grid. rio_mask
    already fills outside-polygon with nodata, but valid_pixel_pct must be
    measured against AOI pixels — not the bounding box."""
    projected = transform_geom("EPSG:4326", f"EPSG:{epsg}", geom)
    return np.asarray(
        geometry_mask([projected], out_shape=shape, transform=transform, invert=True),
        dtype=bool,
    )


def _analyze_pair(
    conn: psycopg.Connection,
    adapter: SensorAdapter,
    pair: PendingPair,
    modules: list[AnalysisModule],
) -> int:
    bands = sorted({b for m in modules for b in m.required_bands})
    if adapter.mask_band:
        bands.append(adapter.mask_band)
    window = adapter.read(pair.meta, pair.aoi_geom, bands)
    if not window.bands:
        return 0  # tile-edge scene: footprint intersects, data doesn't

    if adapter.mask_band and adapter.mask_band in window.bands:
        mask = adapter.quality_mask(window)
    else:
        # no quality layer (e.g. SAR GRD before RTC masking) — validity is
        # "inside the polygon"; pick the finest band as reference grid
        ref = min(window.bands.values(), key=lambda w: w.transform.a)
        mask = type(ref)(
            array=np.ones(ref.array.shape, dtype=bool),
            transform=ref.transform,
            epsg=ref.epsg,
        )

    inside = _inside_aoi(pair.aoi_geom, mask.array.shape, mask.transform, mask.epsg)
    n_inside = int(inside.sum())
    if n_inside == 0:
        return 0
    valid_pct = float((mask.array.astype(bool) & inside).sum() / n_inside)

    written = 0
    with conn.transaction():
        for module in modules:
            value = module.compute(window, mask)
            if value is None:
                continue
            conn.execute(
                """INSERT INTO metrics (aoi_id, scene_id, sensor_id, date,
                                        metric_name, value, unit, valid_pixel_pct)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (aoi_id, scene_id, metric_name) DO UPDATE SET
                       value = EXCLUDED.value,
                       unit = EXCLUDED.unit,
                       valid_pixel_pct = EXCLUDED.valid_pixel_pct""",
                (
                    pair.aoi_id,
                    pair.scene_id,
                    adapter.sensor_id,
                    pair.meta.acquired_at.date(),
                    module.metric_name,
                    value,
                    module.unit,
                    valid_pct,
                ),
            )
            written += 1
    return written


def analyze_pending(conn: psycopg.Connection, adapter: SensorAdapter) -> int:
    """Write metrics for every (scene, aoi) pair missing them. Returns the
    number of metric rows written."""
    modules = modules_for(adapter.sensor_id)
    if not modules:
        return 0

    written = 0
    for pair in _pending_pairs(conn, adapter.sensor_id):
        have = {
            r[0]
            for r in conn.execute(
                "SELECT metric_name FROM metrics WHERE scene_id = %s AND aoi_id = %s",
                (pair.scene_id, pair.aoi_id),
            ).fetchall()
        }
        missing = [m for m in modules if m.metric_name not in have]
        if not missing:
            continue
        try:
            written += _analyze_pair(conn, adapter, pair, missing)
        except AdapterError as exc:
            # one unreadable scene doesn't kill the sweep — it stays pending
            # and the next run retries it
            log.warning("analyze_pair_failed", scene_id=pair.scene_id, error=str(exc))
    log.info("analyze_done", sensor_id=adapter.sensor_id, metrics_written=written)
    return written

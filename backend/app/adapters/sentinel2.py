"""Sentinel-2 adapter — Earth Search `sentinel-2-c1-l2a` collection.

Why this catalog: anonymous HTTPS access, no requester-pays, and Element84
re-encoded the whole archive to true COGs (collection `sentinel-2-c1-l2a`).
CDSE is the documented fallback if Earth Search ever degrades.

Quality masking uses the SCL (Scene Classification Layer) band — per-pixel
classes produced by ESA's sen2cor, not heuristics we invent.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, datetime
from functools import partial
from typing import Any

import numpy as np
import pystac_client
from rasterio.errors import RasterioIOError

from app.adapters._cog import align_mask, read_band
from app.adapters._retry import with_retry
from app.adapters.base import (
    AdapterError,
    BandSpec,
    BandWindow,
    GeoJSONGeom,
    SceneMeta,
    SceneWindow,
    SensorAdapter,
)

logger = logging.getLogger(__name__)

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-c1-l2a"

# SCL classes we accept as ground truth. Everything else (cloud shadows,
# clouds, cirrus, snow, saturated, defective, no-data) is masked out.
VALID_SCL_CLASSES = frozenset({4, 5, 6, 7})  # vegetation, bare soil, water, unclassified

BANDS: list[BandSpec] = [
    BandSpec("blue", "blue", "B02 490nm", 10, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("green", "green", "B03 560nm", 10, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("red", "red", "B04 665nm", 10, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("rededge1", "rededge1", "B05 705nm", 20, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("nir", "nir", "B08 842nm", 10, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("nir08", "nir08", "B8A 865nm narrow", 20, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("swir16", "swir16", "B11 1610nm", 20, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("swir22", "swir22", "B12 2190nm", 20, "reflectance", scale=1e-4, dn_offset=-0.1),
    BandSpec("scl", "scl", "Scene Classification Layer", 20, "quality"),
]


class Sentinel2Adapter(SensorAdapter):
    sensor_id = "sentinel-2"
    catalog = "earth-search"
    collections = (COLLECTION,)
    mask_band = "scl"

    def band_registry(self) -> list[BandSpec]:
        return list(BANDS)

    def search(
        self,
        aoi: GeoJSONGeom,
        start: date,
        end: date,
        *,
        max_cloud_cover: float | None = None,
        limit: int | None = None,
    ) -> list[SceneMeta]:
        query: dict[str, Any] = {}
        if max_cloud_cover is not None:
            query["eo:cloud_cover"] = {"lte": max_cloud_cover}

        def _run() -> list[dict[str, Any]]:
            client = pystac_client.Client.open(STAC_URL)
            results = client.search(
                collections=[COLLECTION],
                intersects=aoi,
                datetime=f"{start.isoformat()}/{end.isoformat()}",
                query=query or None,
                limit=limit,
            )
            return [item.to_dict() for item in results.items()]

        try:
            items = with_retry(_run)
        except Exception as exc:
            raise AdapterError(f"earth-search STAC search failed: {exc}") from exc

        return [self._to_scene(d) for d in items]

    def read(
        self,
        scene: SceneMeta,
        aoi: GeoJSONGeom,
        bands: Sequence[str],
    ) -> SceneWindow:
        registry = {b.name: b for b in BANDS}
        windows: dict[str, BandWindow] = {}

        for name in bands:
            spec = registry.get(name)
            if spec is None:
                raise AdapterError(f"unknown sentinel-2 band '{name}'")
            href = scene.assets.get(spec.asset_key)
            if href is None:
                logger.warning("scene %s missing asset %s", scene.scene_id, spec.asset_key)
                continue

            try:
                window = with_retry(partial(read_band, href, aoi, spec))
            except RasterioIOError as exc:
                raise AdapterError(f"COG read failed for {spec.asset_key}: {exc}") from exc
            if window is not None:
                windows[name] = window

        return SceneWindow(scene=scene, aoi=aoi, bands=windows)

    def quality_mask(self, window: SceneWindow) -> BandWindow:
        scl = window.bands.get("scl")
        if scl is None:
            raise AdapterError("quality_mask requires the 'scl' band in the window")

        science = [w for name, w in window.bands.items() if name != "scl"]
        if not science:
            raise AdapterError("quality_mask needs a science band for the target grid")
        ref = min(science, key=lambda w: w.transform.a)  # finest grid wins

        valid = np.isin(scl.array, list(VALID_SCL_CLASSES))
        # SCL is 20 m; science bands may be 10 m
        return align_mask(valid, scl, ref)

    @staticmethod
    def _to_scene(item: dict[str, Any]) -> SceneMeta:
        props = item.get("properties", {})
        return SceneMeta(
            scene_id=item["id"],
            sensor_id="sentinel-2",
            collection=item.get("collection", COLLECTION),
            catalog="earth-search",
            acquired_at=datetime.fromisoformat(props["datetime"].replace("Z", "+00:00")),
            bbox=tuple(item["bbox"]),
            geometry=item["geometry"],
            cloud_cover=props.get("eo:cloud_cover"),
            epsg=props.get("proj:epsg"),
            assets={k: v["href"] for k, v in item.get("assets", {}).items() if "href" in v},
            properties=props,
        )

"""Landsat 8/9 adapter — Planetary Computer `landsat-c2-l2` collection.

Why this catalog: Earth Search's `landsat-c2-l2` assets live in the
requester-pays `usgs-landsat` bucket (banned per ADR-0001) and USGS
LandsatLook full-resolution assets need an ERS login. Planetary Computer
signs its Azure blob hrefs anonymously; signed URLs stay server-side, per
its terms.

Masking: `qa_pixel` bitfield (fill, dilated cloud, cirrus, cloud, shadow,
snow). Thermal: `lwir11` (ST_B10) is surface temperature in kelvin after
scale 0.00341802 / offset 149.0, delivered on the 30 m grid.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from functools import partial
from typing import Any

import numpy as np
import pystac_client
import requests
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

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
COLLECTION = "landsat-c2-l2"
PLATFORMS = ["landsat-8", "landsat-9"]  # the collection also holds Landsat 4-7

# QA_PIXEL bits 0-5: fill, dilated cloud, cirrus, cloud, cloud shadow, snow.
# Any of them set makes the pixel unusable; clear (6) and water (7) pass.
QA_REJECT = 0b111111

BANDS: list[BandSpec] = [
    BandSpec("blue", "blue", "OLI B02", 30, "reflectance", scale=2.75e-5, dn_offset=-0.2),
    BandSpec("green", "green", "OLI B03", 30, "reflectance", scale=2.75e-5, dn_offset=-0.2),
    BandSpec("red", "red", "OLI B04", 30, "reflectance", scale=2.75e-5, dn_offset=-0.2),
    BandSpec("nir", "nir08", "OLI B05", 30, "reflectance", scale=2.75e-5, dn_offset=-0.2),
    BandSpec("swir16", "swir16", "OLI B06", 30, "reflectance", scale=2.75e-5, dn_offset=-0.2),
    BandSpec(
        "lwir", "lwir11", "TIRS B10 surface temp", 100, "thermal", scale=0.00341802, dn_offset=149.0
    ),
    BandSpec("qa_pixel", "qa_pixel", "USGS QA bitfield", 30, "quality"),
]


# collection -> (SAS token, expiry). The SAS endpoint rate-limits (429s when
# signing per href), and one collection token signs every blob for ~24 h.
_token_cache: dict[str, tuple[str, datetime]] = {}
_TOKEN_MARGIN = timedelta(minutes=10)


def _sign(href: str) -> str:
    cached = _token_cache.get(COLLECTION)
    if cached is None or cached[1] - _TOKEN_MARGIN <= datetime.now(UTC):
        resp = requests.get(f"{TOKEN_URL}/{COLLECTION}", timeout=30)
        resp.raise_for_status()
        body = resp.json()
        expiry = datetime.fromisoformat(body["msft:expiry"].replace("Z", "+00:00"))
        cached = (body["token"], expiry)
        _token_cache[COLLECTION] = cached
    return f"{href}?{cached[0]}"


class LandsatAdapter(SensorAdapter):
    sensor_id = "landsat-8-9"
    catalog = "planetary-computer"
    collections = (COLLECTION,)
    mask_band = "qa_pixel"

    def readable_href(self, href: str) -> str:
        return with_retry(partial(_sign, href))

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
        query: dict[str, Any] = {"platform": {"in": PLATFORMS}}
        if max_cloud_cover is not None:
            query["eo:cloud_cover"] = {"lte": max_cloud_cover}

        def _run() -> list[dict[str, Any]]:
            client = pystac_client.Client.open(STAC_URL)
            results = client.search(
                collections=[COLLECTION],
                intersects=aoi,
                datetime=f"{start.isoformat()}/{end.isoformat()}",
                query=query,
                limit=limit,
            )
            return [item.to_dict() for item in results.items()]

        try:
            items = with_retry(_run)
        except Exception as exc:
            raise AdapterError(f"planetary-computer STAC search failed: {exc}") from exc
        return [self._to_scene(d) for d in items]

    def read(self, scene: SceneMeta, aoi: GeoJSONGeom, bands: Sequence[str]) -> SceneWindow:
        registry = {b.name: b for b in BANDS}
        windows: dict[str, BandWindow] = {}
        for name in bands:
            spec = registry.get(name)
            if spec is None:
                raise AdapterError(f"unknown landsat band '{name}'")
            href = scene.assets.get(spec.asset_key)
            if href is None:
                logger.warning("scene %s missing asset %s", scene.scene_id, spec.asset_key)
                continue
            try:
                signed = self.readable_href(href)
                window = with_retry(partial(read_band, signed, aoi, spec))
            except (RasterioIOError, requests.RequestException) as exc:
                raise AdapterError(f"COG read failed for {spec.asset_key}: {exc}") from exc
            if window is not None:
                windows[name] = window
        return SceneWindow(scene=scene, aoi=aoi, bands=windows)

    def quality_mask(self, window: SceneWindow) -> BandWindow:
        qa = window.bands.get("qa_pixel")
        if qa is None:
            raise AdapterError("quality_mask requires the 'qa_pixel' band in the window")
        science = [w for name, w in window.bands.items() if name != "qa_pixel"]
        if not science:
            raise AdapterError("quality_mask needs a science band for the target grid")
        ref = min(science, key=lambda w: w.transform.a)
        valid = (qa.array.astype(np.uint16) & QA_REJECT) == 0
        return align_mask(valid, qa, ref)

    @staticmethod
    def _to_scene(item: dict[str, Any]) -> SceneMeta:
        props = item.get("properties", {})
        epsg = props.get("proj:epsg")
        if epsg is None and str(props.get("proj:code", "")).startswith("EPSG:"):
            epsg = int(props["proj:code"].split(":")[1])
        return SceneMeta(
            scene_id=item["id"],
            sensor_id="landsat-8-9",
            collection=item.get("collection", COLLECTION),
            catalog="planetary-computer",
            acquired_at=datetime.fromisoformat(props["datetime"].replace("Z", "+00:00")),
            bbox=tuple(item["bbox"]),
            geometry=item["geometry"],
            cloud_cover=props.get("eo:cloud_cover"),
            epsg=epsg,
            assets={k: v["href"] for k, v in item.get("assets", {}).items() if "href" in v},
            properties=props,
        )

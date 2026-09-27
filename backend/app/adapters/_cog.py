"""Windowed COG reads and mask alignment shared by the optical adapters."""

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.mask import mask as rio_mask
from rasterio.warp import Resampling, reproject, transform_geom

from app.adapters.base import BandSpec, BandWindow, GeoJSONGeom


def read_band(href: str, aoi: GeoJSONGeom, spec: BandSpec) -> BandWindow | None:
    """One COG windowed read, clipped to the AOI in the dataset's CRS.

    Returns None when the AOI sits outside the scene's data footprint —
    tile edges end before the tile's bounding box does.

    Science bands are returned in PHYSICAL units (scale/dn_offset applied —
    preprocessing lives in the adapter, per the module split). Quality
    bands stay raw integers: class ids and bitfields are labels, not
    quantities. DN 0 is fill for every band we read; each sensor's quality
    band masks those pixels.
    """
    with rasterio.open(href) as ds:
        geom = transform_geom("EPSG:4326", ds.crs, aoi)
        try:
            arr, transform = rio_mask(ds, [geom], crop=True, filled=True, nodata=0)
        except ValueError:
            return None
        band = arr[0]
        if spec.kind != "quality":
            band = band.astype(np.float32) * spec.scale + spec.dn_offset
        return BandWindow(array=band, transform=transform, epsg=ds.crs.to_epsg() or 0)


def align_mask(valid: np.ndarray, source: BandWindow, ref: BandWindow) -> BandWindow:
    """Validity mask on the reference grid. Nearest-neighbor when the grids
    differ — conservative: a masked coarse cell kills every fine cell it covers."""
    if valid.shape != ref.array.shape:
        aligned = np.zeros(ref.array.shape, dtype=np.uint8)
        reproject(
            source=valid.astype(np.uint8),
            destination=aligned,
            src_transform=source.transform,
            src_crs=CRS.from_epsg(source.epsg),
            dst_transform=ref.transform,
            dst_crs=CRS.from_epsg(ref.epsg),
            resampling=Resampling.nearest,
        )
        valid = aligned.astype(bool)
    return BandWindow(array=valid, transform=ref.transform, epsg=ref.epsg)

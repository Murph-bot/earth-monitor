"""Tile rendering from provider COGs — pure function + LRU cache.

Each PNG tile is deterministic for (hrefs, z/x/y, stretch): scenes are
immutable, so the bytes are memoized in-process and marked cacheable in
HTTP. Nothing is persisted — a restart just re-reads a few range requests.
"""

import io
from functools import lru_cache

import numpy as np
from PIL import Image
from rio_tiler.io import COGReader
from rio_tiler.models import ImageData

TILE_SIZE = 256
# The "Thessaly scale" s0..s5 (ochre -> teal) from the design tokens — the
# same ramp the web legend, chips and charts use. Keep in sync with
# web/src/styles.css.
SCALE_HEX = ("#9a5c16", "#b7791f", "#d6c25a", "#8fbf5a", "#3f9e6e", "#14837d")
SCALE_RGB = np.array(
    [[int(h[i : i + 2], 16) for i in (1, 3, 5)] for h in SCALE_HEX], dtype=np.float32
)
NDVI_RANGE = (0.0, 0.8)  # legend: "Bare / dry 0.0" .. "Lush 0.8"
CACHE_TILES = 512  # ~few MB of PNGs; an LRU bound, not a quota


def _band_window(href: str, x: int, y: int, z: int) -> ImageData:
    with COGReader(href) as cog:
        img: ImageData = cog.tile(x, y, z, tilesize=TILE_SIZE)
        return img


@lru_cache(maxsize=CACHE_TILES)
def render_png(
    hrefs: tuple[str, ...],
    scale_offsets: tuple[tuple[float, float], ...],
    display_max: float,
    x: int,
    y: int,
    z: int,
) -> bytes:
    """Render an RGB(A) PNG tile from N single-band COG hrefs.

    DN -> physical via each band's scale/dn_offset (adapter semantics kept:
    stored integers become reflectance/kelvin here too), then a linear
    stretch 0..display_max -> 0..255. display_max 0.3 is the standard
    bright-daylight stretch for surface reflectance.
    """
    merged = ImageData.create_from_list([_band_window(h, x, y, z) for h in hrefs])
    arr = np.asarray(merged.data, dtype=np.float32)
    for i, (scale, offset) in enumerate(scale_offsets):
        arr[i] = arr[i] * scale + offset
    arr = np.clip(arr / display_max, 0, 1) * 255
    masked = np.ma.MaskedArray(arr.astype(np.uint8), mask=np.ma.getmaskarray(merged.array))
    return ImageData(masked).render(img_format="PNG")


def ramp_rgba(values: np.ndarray, vmin: float, vmax: float, valid: np.ndarray) -> np.ndarray:
    """Map values onto s0..s5 (linear interpolation between stops) as RGBA
    uint8; pixels where `valid` is False are fully transparent."""
    t = np.clip((values - vmin) / (vmax - vmin), 0, 1) * (len(SCALE_RGB) - 1)
    lo = np.minimum(t.astype(np.int64), len(SCALE_RGB) - 2)
    frac = (t - lo)[..., None]
    rgb = SCALE_RGB[lo] * (1 - frac) + SCALE_RGB[lo + 1] * frac
    alpha = np.where(valid, 255, 0).astype(np.uint8)
    return np.dstack([np.rint(rgb).astype(np.uint8), alpha])


@lru_cache(maxsize=CACHE_TILES)
def render_ndvi_png(
    hrefs: tuple[str, str],
    scale_offsets: tuple[tuple[float, float], tuple[float, float]],
    x: int,
    y: int,
    z: int,
) -> bytes:
    """NDVI tile in the s0..s5 ramp. `hrefs`/`scale_offsets` are (red, nir)."""
    merged = ImageData.create_from_list([_band_window(h, x, y, z) for h in hrefs])
    arr = np.asarray(merged.data, dtype=np.float32)
    red = arr[0] * scale_offsets[0][0] + scale_offsets[0][1]
    nir = arr[1] * scale_offsets[1][0] + scale_offsets[1][1]
    denom = nir + red
    valid = ~np.ma.getmaskarray(merged.array).any(axis=0) & (denom > 0)
    ndvi = np.divide(nir - red, denom, out=np.zeros_like(denom), where=denom > 0)
    buf = io.BytesIO()
    Image.fromarray(ramp_rgba(ndvi, *NDVI_RANGE, valid), "RGBA").save(buf, format="PNG")
    return buf.getvalue()

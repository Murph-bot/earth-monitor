"""Tile rendering from provider COGs — pure function + LRU cache.

Each PNG tile is deterministic for (hrefs, z/x/y, stretch): scenes are
immutable, so the bytes are memoized in-process and marked cacheable in
HTTP. Nothing is persisted — a restart just re-reads a few range requests.
"""

from functools import lru_cache

import numpy as np
from rio_tiler.io import COGReader
from rio_tiler.models import ImageData

TILE_SIZE = 256
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

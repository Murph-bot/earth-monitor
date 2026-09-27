"""PDIR-Now daily rainfall — UC Irvine CHRS, satellite-only (geostationary
infrared), anonymous HTTPS, ~4 km cells.

Grid: 3000 rows x 9000 cols of 0.04 degrees, north-up from 60 N, longitude
0-360 from 0 E, float32 little-endian mm/day, gzip, -9999 = no data. The
file is global (~15-30 MB); a sweep downloads each day once and crops it
for every AOI.
"""

import gzip
import math
from datetime import date

import numpy as np
import requests

BASE_URL = "https://persiann.eng.uci.edu/CHRSdata/PDIRNow/PDIRNowdaily"
ROWS, COLS = 3000, 9000
RES = 0.04
NORTH = 60.0
NODATA = -9999.0
_EPS = 1e-9

Bbox = tuple[float, float, float, float]  # minx, miny, maxx, maxy (lon/lat)


def cell_window(bbox: Bbox) -> tuple[slice, slice]:
    """Row/col slices of every cell the bbox touches; at least one cell."""
    minx, miny, maxx, maxy = bbox
    row0 = math.floor((NORTH - maxy) / RES + _EPS)
    row1 = max(math.ceil((NORTH - miny) / RES - _EPS), row0 + 1)
    col0 = math.floor((minx % 360) / RES + _EPS)
    col1 = max(math.ceil((maxx % 360) / RES - _EPS), col0 + 1)
    return slice(row0, row1), slice(col0, col1)


def aoi_rain_mm(grid: np.ndarray, bbox: Bbox) -> float | None:
    rows, cols = cell_window(bbox)
    cells = grid[rows, cols]
    valid = cells[cells >= 0]
    return float(valid.mean()) if valid.size else None


def fetch_daily(day: date) -> np.ndarray | None:
    """The global grid for one UTC day, or None while it is unpublished."""
    url = f"{BASE_URL}/pdirnow1d{day:%y%m%d}.bin.gz"
    resp = requests.get(url, timeout=120)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    raw = gzip.decompress(resp.content)
    return np.frombuffer(raw, dtype="<f4").reshape(ROWS, COLS)

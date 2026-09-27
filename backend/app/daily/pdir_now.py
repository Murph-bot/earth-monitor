"""PDIR-Now daily rainfall — UC Irvine CHRS, satellite-only (geostationary
infrared), anonymous HTTPS, ~4 km cells.

Grid: 3000 rows x 9000 cols of 0.04 degrees, north-up from 60 N, longitude
0-360 from 0 E, float32 little-endian mm/day, gzip, -9999 = no data. The
file is global (~15-30 MB); a sweep downloads each day once and crops it
for every AOI.
"""

import gzip
from datetime import date

import numpy as np
import requests

from app.daily.grid import Grid

BASE_URL = "https://persiann.eng.uci.edu/CHRSdata/PDIRNow/PDIRNowdaily"
GRID = Grid(res=0.04, rows=3000, cols=9000, north_up=True, lat_edge=60.0, lon_edge=0.0)


def fetch_daily(day: date) -> np.ndarray | None:
    """The global grid for one UTC day, or None while it is unpublished."""
    url = f"{BASE_URL}/pdirnow1d{day:%y%m%d}.bin.gz"
    resp = requests.get(url, timeout=120)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    raw = gzip.decompress(resp.content)
    return np.frombuffer(raw, dtype="<f4").reshape(GRID.rows, GRID.cols)

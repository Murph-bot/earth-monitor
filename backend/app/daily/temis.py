"""TEMIS clear-sky UV index — KNMI, from satellite-assimilated ozone at local
solar noon, anonymous HTTPS, 0.25 degree cells.

Clear-sky means the index a cloudless sky would give: TEMIS publishes no
global cloud-modified product. One daily HDF-4 file (~2.6 MB), UVI_field
int16 in thousandths, 720 rows x 1440 cols, south-up from 90 S, longitude
from 180 W, -1000 = no data. An unpublished day answers 403.
"""

import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import requests
from pyhdf.SD import SD, SDC

from app.daily.grid import Grid

BASE_URL = "https://d1qb6yzwaaq4he.cloudfront.net/uvradiation/v2.0"
GRID = Grid(res=0.25, rows=720, cols=1440, north_up=False, lat_edge=-90.0, lon_edge=-180.0)
SCALE = 0.001


def read_uvi(path: Path) -> np.ndarray:
    sd = SD(str(path), SDC.READ)
    try:
        raw: np.ndarray = sd.select("UVI_field").get()
    finally:
        sd.end()
    return raw.astype(np.float32) * np.float32(SCALE)


def fetch_daily(day: date) -> np.ndarray | None:
    """The global UV index grid for one UTC day, or None while unpublished."""
    resp = requests.get(f"{BASE_URL}/{day:%Y/%m}/uvief{day:%Y%m%d}.hdf", timeout=120)
    if resp.status_code in (403, 404):
        return None
    resp.raise_for_status()
    with tempfile.TemporaryDirectory() as tmp:  # the HDF-4 library reads only from paths
        path = Path(tmp) / "uvief.hdf"
        path.write_bytes(resp.content)
        return read_uvi(path)

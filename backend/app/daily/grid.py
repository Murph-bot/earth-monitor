"""Global regular lat/lon grids, cropped to an AOI bbox.

Negative cells are no-data: every daily quantity here (rain, UV index) is
non-negative, and each source's fill value is negative.
"""

import math
from dataclasses import dataclass

import numpy as np

Bbox = tuple[float, float, float, float]  # minx, miny, maxx, maxy (lon/lat)

_EPS = 1e-9


@dataclass(frozen=True)
class Grid:
    res: float
    rows: int
    cols: int
    north_up: bool
    lat_edge: float  # outer latitude edge of row 0
    lon_edge: float  # western longitude edge of column 0


def cell_window(grid: Grid, bbox: Bbox) -> tuple[slice, np.ndarray]:
    """Row slice and column indices of every cell the bbox touches, at least
    one cell. Columns wrap, so a bbox across the grid's seam reads both sides."""
    minx, miny, maxx, maxy = bbox
    if grid.north_up:
        near, far = grid.lat_edge - maxy, grid.lat_edge - miny
    else:
        near, far = miny - grid.lat_edge, maxy - grid.lat_edge
    row0 = math.floor(near / grid.res + _EPS)
    row1 = max(math.ceil(far / grid.res - _EPS), row0 + 1)
    x0 = (minx - grid.lon_edge) % 360
    col0 = math.floor(x0 / grid.res + _EPS)
    col1 = max(math.ceil((x0 + maxx - minx) / grid.res - _EPS), col0 + 1)
    return slice(row0, row1), np.arange(col0, col1) % grid.cols


def aoi_mean(grid: Grid, values: np.ndarray, bbox: Bbox) -> float | None:
    rows, cols = cell_window(grid, bbox)
    cells = values[rows][:, cols]
    valid = cells[cells >= 0]
    return float(valid.mean()) if valid.size else None

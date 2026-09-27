"""PDIR-Now grid cropping — no network. The global daily grid is 3000 x 9000
float32 cells of 0.04 degrees, north-up from 60 N, longitudes 0-360."""

import numpy as np

from app.daily import pdir_now

# the live Thessaly field's bounding box
BBOX = (22.55, 39.45, 22.75, 39.60)


def _grid(fill: float) -> np.ndarray:
    return np.full((pdir_now.ROWS, pdir_now.COLS), fill, dtype=np.float32)


def test_cells_cover_the_bbox_and_nothing_more() -> None:
    rows, cols = pdir_now.cell_window(BBOX)
    assert (rows.start, rows.stop) == (510, 514)  # 39.60 -> 39.44 N
    assert (cols.start, cols.stop) == (563, 569)  # 22.52 -> 22.76 E


def test_rain_is_mean_of_valid_cells_over_the_aoi() -> None:
    grid = _grid(100.0)  # heavy rain everywhere else must not leak in
    rows, cols = pdir_now.cell_window(BBOX)
    grid[rows, cols] = 4.0
    grid[rows.start, cols.start] = 10.0
    grid[rows.start, cols.start + 1] = pdir_now.NODATA
    n = (rows.stop - rows.start) * (cols.stop - cols.start) - 1
    assert pdir_now.aoi_rain_mm(grid, BBOX) == np.float32((4.0 * (n - 1) + 10.0) / n)


def test_aoi_smaller_than_a_cell_uses_its_cell() -> None:
    grid = _grid(0.0)
    grid[510, 566] = 7.5
    assert pdir_now.aoi_rain_mm(grid, (22.645, 39.58, 22.65, 39.585)) == 7.5


def test_no_valid_cells_is_none() -> None:
    assert pdir_now.aoi_rain_mm(_grid(pdir_now.NODATA), BBOX) is None

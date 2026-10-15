"""Cropping global lat/lon grids to an AOI bbox — no network."""

import numpy as np

from app.daily import pdir_now, temis
from app.daily.grid import aoi_mean, cell_window

NORTH_UP = pdir_now.GRID  # north-up from 60 N, longitudes 0-360 from 0 E
SOUTH_UP = temis.GRID  # south-up from 90 S, longitudes from 180 W

THESSALY = (22.55, 39.45, 22.75, 39.60)


def test_north_up_cells_cover_the_bbox_and_nothing_more() -> None:
    rows, cols = cell_window(NORTH_UP, THESSALY)
    assert (rows.start, rows.stop) == (510, 514)  # 39.60 -> 39.44 N
    assert cols.tolist() == list(range(563, 569))  # 22.52 -> 22.76 E


def test_south_up_cells_cover_the_bbox_and_nothing_more() -> None:
    rows, cols = cell_window(SOUTH_UP, THESSALY)
    assert (rows.start, rows.stop) == (517, 519)  # 39.25 -> 39.75 N
    assert cols.tolist() == [810]  # 22.50 -> 22.75 E


def test_bbox_across_the_seam_reads_both_sides() -> None:
    london = (-0.1, 51.4, 0.1, 51.6)
    _, cols = cell_window(NORTH_UP, london)
    assert cols.tolist() == [8997, 8998, 8999, 0, 1, 2]
    _, cols = cell_window(SOUTH_UP, (179.9, 0.0, 180.1, 0.1))
    assert cols.tolist() == [1439, 0]


def test_mean_of_valid_cells_over_the_aoi() -> None:
    values = np.full((NORTH_UP.rows, NORTH_UP.cols), 100.0, dtype=np.float32)
    rows, cols = cell_window(NORTH_UP, THESSALY)
    values[rows, cols] = 4.0
    values[510, 563] = 10.0
    values[510, 564] = -9999.0
    assert aoi_mean(NORTH_UP, values, THESSALY) == np.float32((4.0 * 22 + 10.0) / 23)


def test_aoi_smaller_than_a_cell_uses_its_cell() -> None:
    values = np.zeros((NORTH_UP.rows, NORTH_UP.cols), dtype=np.float32)
    values[510, 566] = 7.5
    assert aoi_mean(NORTH_UP, values, (22.645, 39.58, 22.65, 39.585)) == 7.5


def test_no_valid_cells_is_none() -> None:
    values = np.full((SOUTH_UP.rows, SOUTH_UP.cols), -1.0, dtype=np.float32)
    assert aoi_mean(SOUTH_UP, values, THESSALY) is None

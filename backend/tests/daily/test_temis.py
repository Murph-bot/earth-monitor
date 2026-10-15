"""TEMIS daily UV index decoding — no network. A real daily file is HDF-4
with UVI_field as int16 thousandths of a UV index unit, 720 x 1440,
south-up from 90 S, and -1000 as the fill value."""

from pathlib import Path

import numpy as np
from pyhdf.SD import SD, SDC

from app.daily import temis
from app.daily.grid import aoi_mean

THESSALY = (22.55, 39.45, 22.75, 39.60)


def _write_day(path: Path, raw: np.ndarray) -> None:
    sd = SD(str(path), SDC.WRITE | SDC.CREATE)
    ds = sd.create("UVI_field", SDC.INT16, raw.shape)
    ds[:] = raw
    ds.endaccess()
    sd.end()


def test_uv_index_is_scaled_and_fill_is_no_data(tmp_path: Path) -> None:
    raw = np.full((temis.GRID.rows, temis.GRID.cols), 12000, dtype=np.int16)
    raw[517:519, 810] = (5117, -1000)  # the two cells over the Thessaly field
    _write_day(tmp_path / "day.hdf", raw)

    uvi = temis.read_uvi(tmp_path / "day.hdf")

    assert uvi.shape == (720, 1440)
    assert aoi_mean(temis.GRID, uvi, THESSALY) == np.float32(5.117)

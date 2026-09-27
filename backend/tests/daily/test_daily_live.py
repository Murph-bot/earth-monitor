"""Live daily sources (PDIR-Now rain, TEMIS UV). Skipped by default:
EM_INTEGRATION=1 uv run pytest tests/daily/test_daily_live.py -v
"""

import os
from datetime import date

import pytest

from app.daily import pdir_now, temis
from app.daily.grid import aoi_mean

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("EM_INTEGRATION") != "1", reason="live source test; set EM_INTEGRATION=1"
    ),
]

THESSALY = (22.55, 39.45, 22.75, 39.60)


def test_real_rain_day_over_thessaly() -> None:
    grid = pdir_now.fetch_daily(date(2026, 9, 25))
    assert grid is not None and grid.shape == (pdir_now.GRID.rows, pdir_now.GRID.cols)
    mm = aoi_mean(pdir_now.GRID, grid, THESSALY)
    assert mm is not None and 1.0 < mm < 10.0, mm  # research fetch saw a 3.9 mm mean


def test_real_uv_day_over_thessaly() -> None:
    uvi = temis.fetch_daily(date(2026, 9, 26))
    assert uvi is not None and uvi.shape == (temis.GRID.rows, temis.GRID.cols)
    value = aoi_mean(temis.GRID, uvi, THESSALY)
    assert value is not None and 4.0 < value < 6.5, value  # research read 5.1 at Larissa


def test_unpublished_day_is_none() -> None:
    assert pdir_now.fetch_daily(date(2030, 1, 1)) is None
    assert temis.fetch_daily(date(2030, 1, 1)) is None

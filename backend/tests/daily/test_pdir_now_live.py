"""Live PDIR-Now fetch (UC Irvine CHRS, anonymous HTTPS). Skipped by default:
EM_INTEGRATION=1 uv run pytest tests/daily/test_pdir_now_live.py -v
"""

import os
from datetime import date

import pytest

from app.daily import pdir_now

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("EM_INTEGRATION") != "1", reason="live source test; set EM_INTEGRATION=1"
    ),
]


def test_real_rain_day_over_thessaly() -> None:
    grid = pdir_now.fetch_daily(date(2026, 9, 25))
    assert grid is not None and grid.shape == (pdir_now.ROWS, pdir_now.COLS)
    mm = pdir_now.aoi_rain_mm(grid, (22.55, 39.45, 22.75, 39.60))
    assert mm is not None and 1.0 < mm < 10.0, mm  # research fetch saw a 3.9 mm mean


def test_unpublished_day_is_none() -> None:
    assert pdir_now.fetch_daily(date(2030, 1, 1)) is None

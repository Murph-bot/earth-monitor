"""Spectral index modules — the proof that the seam works.

NDVI and NDWI are band ratios over masked-mean statistics. Bands arrive in
physical units (adapters apply scale/dn_offset), so module code is pure
math — no DN bookkeeping here.
"""

import numpy as np

from app.adapters.base import BandWindow, SceneWindow
from app.analysis.base import AnalysisError, AnalysisModule


def _masked_index_mean(
    window: SceneWindow, mask: BandWindow, num_band: str, den_band: str
) -> float | None:
    """Mean of (a - b) / (a + b) over valid pixels. Shared by index modules."""
    if num_band not in window.bands or den_band not in window.bands:
        return None  # asset missing from the scene — a data gap, not an error
    a = window.bands[num_band].array.astype(np.float32)
    b = window.bands[den_band].array.astype(np.float32)
    valid = mask.array.astype(bool)
    if a.shape != valid.shape or b.shape != valid.shape:
        raise AnalysisError(
            f"grid mismatch: bands {a.shape}/{b.shape} vs mask {valid.shape} "
            "(modules must request bands on one grid)"
        )
    denom = a + b
    with np.errstate(invalid="ignore", divide="ignore"):
        index = np.where(denom != 0, (a - b) / denom, np.nan)
    # Reflectance is physically non-negative — the DN offset can push fill /
    # edge pixels negative, which makes near-zero denominators explode the
    # ratio (observed: ndvi_mean = 10.7 on a real scene). Positivity is the
    # physically-correct validity floor for index math.
    sel = valid & np.isfinite(index) & (a > 0) & (b > 0)
    if not sel.any():
        return None
    return float(index[sel].mean())


class Ndvi(AnalysisModule):
    """(nir - red) / (nir + red): vegetation vigor, [-1, 1]."""

    name = "ndvi"
    sensors = ("sentinel-2", "landsat-8-9")  # landsat activates when its adapter lands
    required_bands = ("red", "nir")
    metric_name = "ndvi_mean"
    unit = "index"

    def compute(self, window: SceneWindow, mask: BandWindow) -> float | None:
        return _masked_index_mean(window, mask, "nir", "red")


class Ndwi(AnalysisModule):
    """(green - nir) / (green + nir): open water, McFeeters 1996."""

    name = "ndwi"
    sensors = ("sentinel-2", "landsat-8-9")
    required_bands = ("green", "nir")
    metric_name = "ndwi_mean"
    unit = "index"

    def compute(self, window: SceneWindow, mask: BandWindow) -> float | None:
        return _masked_index_mean(window, mask, "green", "nir")

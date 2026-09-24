"""The analysis module seam.

A module answers one question: "what is my metric's value over the valid
pixels of this window?" It declares which sensors it supports and which
bands it needs; the runner reads the union of bands once per (scene, aoi)
and lets each module compute.

Constraints a module must honor:
- required_bands must share one grid (the quality mask is computed on the
  finest science band's grid — mixing resolutions needs per-band masks,
  deferred until a module actually needs it).
- compute() returns the metric value, or None when no valid pixels exist.
  Missing bands in the window are a normal None, not an error.

valid_pixel_pct is computed once by the runner (same mask for all modules)
— modules never report it themselves.
"""

from abc import ABC, abstractmethod

from app.adapters.base import BandWindow, SceneWindow


class AnalysisError(Exception):
    """A module was asked to compute something structurally impossible —
    e.g. mask and band grids disagree. Programming errors, not data gaps."""


class AnalysisModule(ABC):
    name: str
    sensors: tuple[str, ...]  # sensor_ids this module can run on
    required_bands: tuple[str, ...]
    metric_name: str
    unit: str

    @abstractmethod
    def compute(self, window: SceneWindow, mask: BandWindow) -> float | None:
        """Metric value over valid pixels; None if nothing valid to measure."""

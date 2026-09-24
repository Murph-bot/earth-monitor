"""Module registry — one place to add an analysis module."""

from app.analysis.base import AnalysisModule
from app.analysis.indices import Ndvi, Ndwi

_MODULES: list[AnalysisModule] = [Ndvi(), Ndwi()]


def all_modules() -> list[AnalysisModule]:
    return list(_MODULES)


def modules_for(sensor_id: str) -> list[AnalysisModule]:
    return [m for m in _MODULES if sensor_id in m.sensors]

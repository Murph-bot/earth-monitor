"""Adapter registry — sensor_id -> adapter instance.

One place to add a sensor; ingestion/API code looks adapters up by id and
never imports a concrete class.
"""

from app.adapters.base import SensorAdapter
from app.adapters.sentinel2 import Sentinel2Adapter

_ADAPTERS: dict[str, SensorAdapter] = {a.sensor_id: a for a in [Sentinel2Adapter()]}


def get_adapter(sensor_id: str) -> SensorAdapter:
    try:
        return _ADAPTERS[sensor_id]
    except KeyError:
        raise KeyError(
            f"no adapter registered for '{sensor_id}'. Known: {sorted(_ADAPTERS)}"
        ) from None


def all_adapters() -> dict[str, SensorAdapter]:
    return dict(_ADAPTERS)

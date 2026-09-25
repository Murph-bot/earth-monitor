from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based config. Every field reads from EM_* env vars or .env.

    Dev/prod differ only by env values — never by code branches.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="EM_", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/earth_monitor"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # api
    dev_user_email: str = "dev@earth-monitor.local"  # pre-auth stub (Phase 8 replaces)
    max_aoi_area_km2: float = 500.0  # windowed reads scale with AOI area

    # ingestion worker (python -m app.ingest)
    ingest_backfill_days: int = 30  # first-run lookback when no watermark exists
    ingest_overlap_hours: int = 48  # re-search margin for late-arriving catalog items
    ingest_min_interval_hours: float = 6.0  # floor on per-sensor poll cadence
    ingest_interval_hours: float | None = None  # set to override all sensor cadences
    ingest_tick_seconds: int = 60  # scheduler wake-up granularity
    ingest_analyze: bool = True  # False = catalog-only sweeps (no pixel reads)


@lru_cache
def get_settings() -> Settings:
    return Settings()

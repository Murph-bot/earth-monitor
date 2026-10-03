import re
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based config. Every field reads from EM_* env vars or .env.

    Dev/prod differ only by env values — never by code branches.
    """

    # hide_input_in_errors: a bad EM_DATABASE_URL must never print its password
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="EM_", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/earth_monitor"
    # pasted by hand into dashboards: JSON array or comma list, any quotes
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # api
    # tokenless fallback used only when no Authorization header is present
    # (deps.get_current_user also refuses it outside dev regardless); no
    # default — a deploy that forgets to set EM_ENVIRONMENT must not get a
    # free pass into every endpoint. Set explicitly for local dev (see
    # .env.example).
    dev_user_email: str | None = None
    jwt_secret: str = "dev-secret-change-me-0123456789abcdef"  # HS256; env in prod
    jwt_ttl_hours: int = 336  # 14 days
    max_aoi_area_km2: float = 500.0  # windowed reads scale with AOI area
    rate_auth_per_minute: int = 10  # register + login, per client IP
    rate_tiles_per_minute: int = 600  # a map pan loads dozens of tiles at once

    # ingestion worker (python -m app.ingest)
    ingest_backfill_days: int = 30  # first-run lookback when no watermark exists
    ingest_overlap_hours: int = 48  # re-search margin for late-arriving catalog items
    ingest_min_interval_hours: float = 6.0  # floor on per-sensor poll cadence
    ingest_interval_hours: float | None = None  # set to override all sensor cadences
    ingest_tick_seconds: int = 60  # scheduler wake-up granularity
    ingest_analyze: bool = True  # False = catalog-only sweeps (no pixel reads)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _origins(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        # browsers send Origin without a trailing slash, so match that form
        parts = re.split(r"[,\s]+", re.sub("[\\[\\]\"'\u201c\u201d\u2018\u2019]", "", v))
        return [o.rstrip("/") for o in parts if o]

    @field_validator("database_url")
    @classmethod
    def _bare_postgres_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError(
                "EM_DATABASE_URL must be a bare postgresql://... connection string"
                " (not a psql command, not wrapped in quotes, not empty)"
            )
        return v


_DEFAULT_JWT_SECRET = "dev-secret-change-me-0123456789abcdef"


class InsecureConfigError(RuntimeError):
    """Raised when the app would start with an unsafe default outside dev/test."""


def ensure_safe_to_start(settings: Settings) -> None:
    """Refuse to start outside dev/test with the default JWT secret — a
    deploy that forgets EM_JWT_SECRET must fail loudly, not serve every
    token as forgeable."""
    if settings.environment not in ("dev", "test") and settings.jwt_secret == _DEFAULT_JWT_SECRET:
        raise InsecureConfigError(
            "EM_JWT_SECRET is still the default — set a real secret outside dev/test"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

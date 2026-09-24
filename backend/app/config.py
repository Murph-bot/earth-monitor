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


@lru_cache
def get_settings() -> Settings:
    return Settings()

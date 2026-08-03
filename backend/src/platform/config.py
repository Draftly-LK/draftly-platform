"""Typed runtime configuration for the Draftly API."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Non-secret Phase 0 settings loaded from ``DRAFTLY_*`` variables."""

    model_config = SettingsConfigDict(
        env_prefix="DRAFTLY_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    environment: Literal["local", "test", "preview", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "draftly-api"

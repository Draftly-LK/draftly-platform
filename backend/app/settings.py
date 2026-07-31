from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    confidence_threshold: float = 0.55
    gemini_api_key: str = ""
    # Cheap/fast model for type + side classification.
    gemini_classify_model: str = "gemini-3.1-flash-lite"
    # Stronger multimodal model for transcription + field extraction.
    gemini_extract_model: str = "gemini-2.5-flash"
    # Legacy single-model fallback (unused when classify/extract are set).
    gemini_model: str = "gemini-2.5-flash"
    cors_origins: str = (
        "http://localhost:4310,http://127.0.0.1:4310,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

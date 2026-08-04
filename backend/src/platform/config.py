"""Typed application settings loaded from environment variables.

A missing or malformed required setting fails the boot; it never silently
defaults to a production value (per infrastructure.md §Configuration).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Support running from backend/ or repo root.  The real .env lives at the repo
# root alongside the frontend workspace.
_here = Path(__file__).resolve().parent  # backend/src/platform/
_root_env = _here.parents[2] / ".env"  # repo-root/.env
_backend_env = _here.parents[1] / ".env"  # backend/.env


class Settings(BaseSettings):
    """All settings are read from the environment or a .env file.

    Secrets are never committed — see backend/.env.example for the full list.
    """

    model_config = SettingsConfigDict(
        # Try backend/.env first, then the repo-root .env
        env_file=[str(_backend_env), str(_root_env)],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    # Pooled endpoint for the app runtime (PgBouncer)
    database_url: str
    # Direct (un-pooled) endpoint for Alembic migrations
    database_url_direct: str

    # ── Clerk identity provider ─────────────────────────────────────────────
    clerk_issuer: str = ""
    clerk_secret_key: str = ""
    clerk_audience: str = ""

    # ── Object storage ──────────────────────────────────────────────────────
    object_storage_bucket: str = ""
    object_storage_endpoint_url: str = ""
    object_storage_region: str = "auto"
    object_storage_access_key_id: str = ""
    object_storage_secret_access_key: str = ""

    # ── Google Cloud / Gemini ───────────────────────────────────────────────
    gcp_project_id: str = ""
    gcp_location: str = "asia-south1"
    docai_processor_id: str = ""
    gemini_api_key: str = ""
    gemini_classify_model: str = "gemini-3.1-flash-lite"
    gemini_extract_model: str = "gemini-2.5-flash"

    # ── App behaviour ───────────────────────────────────────────────────────
    environment: str = "local"
    # Seconds a Clerk session may be before step-up auth is required
    step_up_max_age_seconds: int = 600
    # When true, skip Clerk and use the deterministic stub identity (CI/local)
    use_stub_identity: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def clerk_configured(self) -> bool:
        return bool(self.clerk_issuer and self.clerk_secret_key)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings

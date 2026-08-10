"""Typed application settings loaded from environment variables.

A missing or malformed required setting fails the boot; it never silently
defaults to a production value (per infrastructure.md §Configuration).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_backend_env = Path(__file__).resolve().parents[2] / ".env"  # backend/.env


class Settings(BaseSettings):
    """All settings are read from the environment or backend/.env.

    Secrets are never committed — see backend/.env.example for the full list.
    """

    model_config = SettingsConfigDict(
        env_file=str(_backend_env),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str
    database_url_direct: str

    # ── Clerk identity provider ─────────────────────────────────────────────
    clerk_issuer: str = ""
    clerk_secret_key: str = ""
    clerk_audience: str = ""
    clerk_authorized_party: str = ""

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
    step_up_max_age_seconds: int = 600
    use_stub_identity: bool = False

    # ── Party field encryption (local/test adapter only) ────────────────────
    party_identifier_key: str = ""
    party_blind_index_key: str = ""

    # ── Billing / PayHere ───────────────────────────────────────────────────
    use_stub_billing: bool = True
    payhere_merchant_secret: str = ""
    payhere_checkout_base_url: str = "https://payhere.lk"
    billing_grace_period_days: int = 14
    billing_webhook_max_body_bytes: int = 65536
    platform_admin_user_ids: str = ""
    api_cursor_signing_key: str = ""

    # ── Notification / Resend ───────────────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "Draftly <notifications@draftly.local>"
    resend_webhook_secret: str = ""
    resend_outbound_enabled: bool = False
    resend_allowed_recipient_domains: str = "example.com,example.org,draftly.local"
    notification_compliance_allowlist: str = ""
    notification_require_published_template: bool = False
    email_sending_enabled: bool = False
    resend_recipient_allowlist: str = ""
    compliance_alert_user_ids: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_non_production(self) -> bool:
        return self.environment in {"local", "test", "ci", "preview", "demo"}

    @property
    def payhere_configured(self) -> bool:
        return bool(self.payhere_merchant_secret)

    @property
    def provider_email_enabled(self) -> bool:
        return bool(self.email_sending_enabled and self.resend_api_key)

    def parsed_recipient_allowlist(self) -> tuple[str, ...]:
        return tuple(
            entry.strip() for entry in self.resend_recipient_allowlist.split(",") if entry.strip()
        )

    def parsed_compliance_user_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.strip() for entry in self.compliance_alert_user_ids.split(",") if entry.strip()
        )

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

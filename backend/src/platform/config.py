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
    # Required when using the real Clerk adapter — comma-separated JWT `azp`
    # origins (fail closed). Local work uses both :3000 and :4310.
    clerk_authorized_party: str = ""
    # Tolerance for clock drift between this host and Clerk, in seconds.
    #
    # With no leeway a host running even two seconds slow rejects every token
    # as "not yet valid (iat)", which presents as a total login outage rather
    # than as a clock problem. RFC 7519 §4.1.4 allows a small leeway for
    # exactly this.
    #
    # PyJWT applies leeway to `exp` as well as `iat`/`nbf`, so this also
    # extends how long an expired token stays acceptable. Clerk session tokens
    # are short-lived and refreshed automatically, so keep this well under
    # their lifetime — raise it only if a host genuinely cannot keep time.
    clerk_leeway_seconds: int = 30

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
    gemini_extract_model: str = "gemini-3.5-flash"

    # ── Document processing (document-processing.md) ────────────────────────
    # "gemini" | "stub". The stub is confined to local/test/ci at bootstrap.
    extraction_provider: str = "stub"
    # §10A data-protection gate: while false, the pipeline refuses documents
    # not flagged synthetic and routes them to manual_review. Flip only after
    # provider region/retention/training terms are recorded and approved.
    provider_data_approval: bool = False
    # Classification confidence below which extraction is skipped (manual
    # review instead). Tunable per §10 — measured, not guessed.
    confidence_threshold: float = 0.55
    # Demo override: send every page to the extractor even when the kind is
    # uncertain or has no template, instead of stopping at manual_review. The
    # honesty rules still hold — an unregistered kind yields a transcript and
    # NO candidate fields, and the reason codes that would have routed the
    # document to review are still reported. Does not bypass the §10A gate
    # above; that remains a separate decision.
    extraction_send_all: bool = False
    # Rasterization density; recorded with each page so coordinate mapping
    # stays exact when a box-producing engine is added later (§4, §6).
    raster_dpi: int = 200

    # ── Source-file ingestion (RTA workflow §6.2) ───────────────────────────
    # "filesystem" | "object_storage". The filesystem adapter is confined to
    # local/test/ci at bootstrap, like the stub identity and extraction
    # adapters: it has no encryption-at-rest or object versioning guarantee.
    source_file_storage: str = "filesystem"
    source_file_storage_dir: str = ".data/source-files"
    # §6.2 stage 1 limits. Enforced server-side; the client's progress bar is
    # not authoritative.
    max_source_file_bytes: int = 52_428_800  # 50 MiB
    max_source_file_pages: int = 300

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

    @property
    def clerk_authorized_parties(self) -> frozenset[str]:
        """Trusted JWT `azp` origins, parsed from `CLERK_AUTHORIZED_PARTY`."""
        return frozenset(
            party.strip() for party in self.clerk_authorized_party.split(",") if party.strip()
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings

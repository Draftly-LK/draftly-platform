"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from src.modules.auth.ports import IdentityPort
from src.modules.party.infrastructure.event_log import LoggingEventAdapter
from src.modules.party.infrastructure.field_encryption import (
    LocalFieldEncryptionAdapter,
    build_field_encryption_adapter,
)
from src.modules.party.infrastructure.matter_access_stub import (
    StubMatterAccessAdapter,
    build_matter_access_adapter,
)
from src.platform.config import get_settings
from src.platform.request_context import RequestContext

if TYPE_CHECKING:
    from src.modules.auth.application.auth_service import AuthService


def register_routers(app: FastAPI) -> None:
    """Mount all module routers under /api/v1."""
    from src.modules.auth.api.router import router as auth_router
    from src.modules.party.api.router import router as party_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(party_router, prefix="/api/v1")


def build_identity_adapter() -> IdentityPort:
    """Return the appropriate IdentityPort implementation for this environment."""
    settings = get_settings()
    if settings.use_stub_identity or not settings.clerk_configured:
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()
    from src.modules.auth.infrastructure.clerk_adapter import ClerkIdentityAdapter

    if not settings.clerk_authorized_party:
        raise RuntimeError("CLERK_AUTHORIZED_PARTY is required when Clerk identity is enabled.")
    return ClerkIdentityAdapter(
        issuer=settings.clerk_issuer,
        secret_key=settings.clerk_secret_key,
        audience=settings.clerk_audience or None,
        authorized_party=settings.clerk_authorized_party,
    )


# ── party_service adapters ───────────────────────────────────────────────────


class AuthPractisingNotaryAdapter:
    """Bridges party_service's `PractisingNotaryPort` to auth_service.

    The party module must not import another module's application service, so
    the bridge is built here in the composition root.
    """

    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    async def assert_practising(self, ctx: RequestContext) -> None:
        await self._auth.require_practising_notary(ctx)


def build_party_field_encryption() -> LocalFieldEncryptionAdapter:
    """Local adapter today; refuses to start unless keys are configured (§12.7)."""
    return build_field_encryption_adapter(get_settings())


def build_party_matter_access() -> StubMatterAccessAdapter:
    """Narrow stub — matter_service does not exist yet and this is not it."""
    return build_matter_access_adapter(get_settings().environment)


def build_party_event_adapter() -> LoggingEventAdapter:
    """No broker chosen yet; events are recorded, not transported."""
    return LoggingEventAdapter()

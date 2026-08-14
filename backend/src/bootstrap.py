"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from fastapi import FastAPI

from src.modules.auth.ports import IdentityPort
from src.platform.config import get_settings


def register_routers(app: FastAPI) -> None:
    """Mount all module routers under /api/v1."""
    from src.modules.auth.api.router import router as auth_router

    app.include_router(auth_router, prefix="/api/v1")


"""Environments where the stub identity adapter may be selected at all.

The stub accepts any bearer token as one fixed identity, so it is confined to
developer machines and CI. Anywhere else, an incomplete Clerk configuration is
a startup failure rather than an open door.
"""
STUB_IDENTITY_ENVIRONMENTS = frozenset({"local", "test", "ci"})


def build_identity_adapter() -> IdentityPort:
    """Return the appropriate IdentityPort implementation for this environment."""
    settings = get_settings()
    stub_allowed = settings.environment in STUB_IDENTITY_ENVIRONMENTS

    if settings.use_stub_identity:
        if not stub_allowed:
            raise RuntimeError(
                f"USE_STUB_IDENTITY is not permitted in environment "
                f"'{settings.environment}'. The stub adapter accepts any bearer "
                f"token as a fixed identity and is limited to "
                f"{sorted(STUB_IDENTITY_ENVIRONMENTS)}."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    if not settings.clerk_configured:
        if not stub_allowed:
            raise RuntimeError(
                f"Clerk identity is not configured and environment "
                f"'{settings.environment}' does not permit the stub adapter. "
                f"Set CLERK_ISSUER, CLERK_SECRET_KEY and CLERK_AUTHORIZED_PARTY."
            )
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

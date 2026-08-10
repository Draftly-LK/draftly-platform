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
    from src.modules.notarial_register.api.router import router as notarial_register_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(notarial_register_router, prefix="/api/v1")


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

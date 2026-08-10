"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from fastapi import FastAPI

from src.modules.auth.ports import IdentityPort
from src.modules.billing.ports import BillingProviderPort
from src.modules.notification.ports import EmailPort
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
from src.platform.config import get_settings


def register_routers(app: FastAPI) -> None:
    """Mount all module routers under /api/v1."""
    from src.modules.auth.api.router import router as auth_router
    from src.modules.billing.api.router import router as billing_router
    from src.modules.notarial_register.api.router import router as notarial_register_router
    from src.modules.notification.api.router import router as notification_router
    from src.modules.obligations.api.router import router as obligations_router
    from src.modules.party.api.router import router as party_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.include_router(party_router, prefix="/api/v1")
    app.include_router(notification_router, prefix="/api/v1")
    app.include_router(obligations_router, prefix="/api/v1")
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


def build_billing_adapter() -> BillingProviderPort:
    """Return the billing provider adapter for this environment."""
    settings = get_settings()
    if settings.use_stub_billing or not settings.payhere_configured:
        from src.modules.billing.infrastructure.stub_adapter import StubBillingAdapter

        return StubBillingAdapter()
    from src.modules.billing.infrastructure.payhere_adapter import PayHereBillingAdapter

    return PayHereBillingAdapter(
        merchant_secret=settings.payhere_merchant_secret,
        checkout_base_url=settings.payhere_checkout_base_url,
    )


def build_email_adapter() -> EmailPort:
    """Return console adapter by default; Resend when API key is configured."""
    settings = get_settings()
    if settings.resend_api_key:
        from src.modules.notification.infrastructure.email.resend_adapter import (
            ResendEmailAdapter,
        )

        return ResendEmailAdapter(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from_email,
        )
    from src.modules.notification.infrastructure.email.console_adapter import (
        ConsoleEmailAdapter,
    )

    return ConsoleEmailAdapter()


def build_deadline_rule_port() -> FixtureDeadlineRulePort:
    """Fixture-approved deadline rules for local and test environments."""
    return FixtureDeadlineRulePort()

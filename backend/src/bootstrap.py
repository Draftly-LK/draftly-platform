"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import IdentityPort
from src.modules.billing.infrastructure.platform_admin import (
    DenyAllPlatformAdminAdapter,
    SettingsPlatformAdminAdapter,
)
from src.modules.billing.ports import BillingProviderPort, PlatformAdminPort
from src.modules.notification.infrastructure.email.resend_adapter import ResendEmailAdapter
from src.modules.notification.ports import EmailPort
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
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
from src.platform.messaging.dispatcher import MessageDispatcher
from src.platform.request_context import RequestContext

if TYPE_CHECKING:
    from src.modules.auth.application.auth_service import AuthService


def register_routers(app: FastAPI) -> None:
    """Mount all module routers under /api/v1."""
    from src.modules.auth.api.router import router as auth_router
    from src.modules.billing.api.admin_router import router as billing_admin_router
    from src.modules.billing.api.router import router as billing_router
    from src.modules.notarial_register.api.router import router as notarial_register_router
    from src.modules.notification.api.router import router as notification_router
    from src.modules.obligations.api.router import router as obligations_router
    from src.modules.party.api.router import router as party_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.include_router(billing_admin_router, prefix="/api/v1")
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


def build_platform_admin_adapter() -> PlatformAdminPort:
    """Resolve platform.administer from deployment config until auth owns the grant."""
    settings = get_settings()
    if settings.platform_admin_user_ids.strip():
        return SettingsPlatformAdminAdapter(settings.platform_admin_user_ids)
    return DenyAllPlatformAdminAdapter()


def build_email_adapter() -> EmailPort:
    """Console adapter for local/tests; Resend only when explicitly enabled."""
    settings = get_settings()
    if settings.resend_api_key and settings.resend_outbound_enabled:
        domains = frozenset(
            part.strip()
            for part in settings.resend_allowed_recipient_domains.split(",")
            if part.strip()
        )
        return ResendEmailAdapter(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from_email,
            outbound_enabled=True,
            allowed_recipient_domains=domains if domains else None,
        )
    from src.modules.notification.infrastructure.email.console_adapter import (
        ConsoleEmailAdapter,
    )

    return ConsoleEmailAdapter()


def build_deadline_rule_port() -> FixtureDeadlineRulePort:
    """Fixture-approved deadline rules for local and test environments."""
    return FixtureDeadlineRulePort()


class AuthPractisingNotaryAdapter:
    """Bridges party_service's PractisingNotaryPort to auth_service."""

    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    async def assert_practising(self, ctx: RequestContext) -> None:
        await self._auth.require_practising_notary(ctx)


def build_party_field_encryption() -> LocalFieldEncryptionAdapter:
    """Local adapter today; production KMS remains an open decision."""
    return build_field_encryption_adapter(get_settings())


def build_party_matter_access() -> StubMatterAccessAdapter:
    """Narrow stub — matter_service does not exist yet."""
    return build_matter_access_adapter(get_settings().environment)


def build_party_event_adapter() -> LoggingEventAdapter:
    """No broker chosen yet; events are recorded, not transported."""
    return LoggingEventAdapter()


def build_dispatcher() -> MessageDispatcher:
    """Register worker handlers for every module job and event consumer."""
    from src.modules.notification.application.notification_service import DELIVER_JOB_TYPE
    from src.modules.notification.jobs import (
        NOTIFICATION_CONSUMED_EVENTS,
        consume_registered_event,
        run_delivery_job,
    )
    from src.platform.messaging.dispatcher import Handler, MessageDispatcher, MessageResult
    from src.platform.messaging.outbox import ClaimedMessage

    dispatcher = MessageDispatcher()

    async def deliver_handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
        outcome = await run_delivery_job(session, message.payload)
        if outcome in {"delivered", "suppressed", "permanent-failure", "unknown-delivery"}:
            return MessageResult.DONE
        if outcome == "retry":
            return MessageResult.RETRY
        if outcome == "dead-letter":
            return MessageResult.DEAD_LETTER
        return MessageResult.FAILED

    dispatcher.register_job(DELIVER_JOB_TYPE, deliver_handler)

    def make_event_handler(event_name: str) -> Handler:
        async def handler(session: AsyncSession, message: ClaimedMessage) -> MessageResult:
            outcome = await consume_registered_event(session, message.payload)
            if outcome in {"processed", "duplicate", "suppressed"}:
                return MessageResult.DONE
            if outcome == "dead-letter":
                return MessageResult.DEAD_LETTER
            return MessageResult.FAILED

        _ = event_name
        return handler

    for event_name in NOTIFICATION_CONSUMED_EVENTS:
        dispatcher.register_event(event_name, make_event_handler(event_name))

    return dispatcher

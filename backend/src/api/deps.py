"""Shared FastAPI dependencies — used by every module router.

The get_request_context dependency is the security perimeter for all
authenticated API routes. It validates the token, builds the RequestContext,
and rejects the request before any business logic runs.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.infrastructure.repository import (
    SqlUserIdentityRepository,
    SqlUserRepository,
)
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.infrastructure.clock import SystemClock as BillingClock
from src.modules.billing.infrastructure.event_port import InMemoryEventPort
from src.modules.billing.infrastructure.repository import (
    SqlBillingWebhookEventRepository,
    SqlPlanRepository,
    SqlSubscriptionRepository,
    SqlUsageRepository,
)
from src.modules.notarial_register.application.notarial_register_service import (
    NotarialRegisterService,
)
from src.modules.notification.application.notification_service import NotificationService
from src.modules.notification.infrastructure.clock import SystemClock as NotificationClock
from src.modules.notification.infrastructure.recipient_resolver import (
    SqlRecipientEmailResolver,
)
from src.modules.notification.infrastructure.repository import (
    SqlDeliveryRepository,
    SqlPreferenceRepository,
)
from src.modules.obligations.application.obligations_service import ObligationsService
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
from src.modules.obligations.infrastructure.repository import (
    SqlNotificationIntentPort,
    SqlObligationEventPort,
    SqlObligationRepository,
    SqlReminderRepository,
)
from src.modules.obligations.infrastructure.stubs import SystemClockPort
from src.modules.party.application.party_service import PartyService
from src.modules.party.infrastructure.field_encryption import StubFieldEncryptionAdapter
from src.modules.party.infrastructure.matter_access_stub import StubMatterAccessAdapter
from src.modules.party.infrastructure.repository import (
    SqlIdentityEvidenceRepository,
    SqlPartyRepository,
)
from src.modules.party.infrastructure.stub_screening import ManualScreeningAdapter
from src.platform.db.session import get_db
from src.platform.errors import UnauthenticatedError
from src.platform.observability.logging import bind_request_context
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

_http_bearer = HTTPBearer(auto_error=False)

_auth_service_instance: AuthService | None = None
_billing_service_instance: BillingService | None = None
_event_port_instance: InMemoryEventPort | None = None
_party_service_instance: PartyService | None = None
_matter_access_stub: StubMatterAccessAdapter | None = None
_notification_service_instance: NotificationService | None = None
_obligations_service_instance: ObligationsService | None = None
_obligations_org_id: str | None = None
_notarial_register_service_instance: NotarialRegisterService | None = None


def get_auth_service_instance() -> AuthService:
    """Return the singleton AuthService wired at startup."""
    global _auth_service_instance
    if _auth_service_instance is None:
        raise RuntimeError("AuthService not yet initialized. Call init_services() at startup.")
    return _auth_service_instance


def get_billing_service_instance() -> BillingService:
    global _billing_service_instance
    if _billing_service_instance is None:
        raise RuntimeError(
            "BillingService not yet initialized. Call init_services() at startup."
        )
    return _billing_service_instance


def get_event_port_instance() -> InMemoryEventPort:
    global _event_port_instance
    if _event_port_instance is None:
        raise RuntimeError("EventPort not yet initialized. Call init_services() first.")
    return _event_port_instance


def get_party_service_instance() -> PartyService:
    global _party_service_instance
    if _party_service_instance is None:
        raise RuntimeError("PartyService not yet initialized. Call init_services() at startup.")
    return _party_service_instance


def get_matter_access_stub() -> StubMatterAccessAdapter:
    global _matter_access_stub
    if _matter_access_stub is None:
        raise RuntimeError("Matter access stub not initialized.")
    return _matter_access_stub


def get_notification_service_instance() -> NotificationService:
    global _notification_service_instance
    if _notification_service_instance is None:
        raise RuntimeError(
            "NotificationService not yet initialized. Call init_services() at startup."
        )
    return _notification_service_instance


def get_notarial_register_service() -> NotarialRegisterService:
    global _notarial_register_service_instance
    if _notarial_register_service_instance is None:
        raise RuntimeError(
            "NotarialRegisterService not yet initialized. Call init_services() at startup."
        )
    return _notarial_register_service_instance


def get_obligations_service_instance() -> ObligationsService:
    global _obligations_service_instance
    if _obligations_service_instance is None:
        raise RuntimeError(
            "ObligationsService not yet initialized. Call init_services() at startup."
        )
    return _obligations_service_instance


def init_services(session: AsyncSession) -> None:
    """Wire services for a request; called inside a session context."""
    user_identity_repo = SqlUserIdentityRepository(session)
    user_repo = SqlUserRepository(session)
    audit_repo = SqlAuditRepository(session)
    audit_service = AuditService(repository=audit_repo)

    from src.bootstrap import (
        build_billing_adapter,
        build_email_adapter,
        build_identity_adapter,
    )

    identity_adapter = build_identity_adapter()
    billing_adapter = build_billing_adapter()

    global \
        _auth_service_instance, \
        _billing_service_instance, \
        _event_port_instance, \
        _party_service_instance, \
        _matter_access_stub, \
        _notification_service_instance, \
        _notarial_register_service_instance

    _event_port_instance = InMemoryEventPort()
    _auth_service_instance = AuthService(
        identity_port=identity_adapter,
        user_identity_repo=user_identity_repo,
        user_repo=user_repo,
        audit_port=audit_service,
    )
    _billing_service_instance = BillingService(
        plan_repo=SqlPlanRepository(session),
        subscription_repo=SqlSubscriptionRepository(session),
        usage_repo=SqlUsageRepository(session),
        webhook_repo=SqlBillingWebhookEventRepository(session),
        billing_provider=billing_adapter,
        audit_port=audit_service,
        event_port=_event_port_instance,
        clock=BillingClock(),
    )

    encryption = StubFieldEncryptionAdapter()
    _matter_access_stub = StubMatterAccessAdapter()
    _party_service_instance = PartyService(
        party_repo=SqlPartyRepository(session),
        identity_repo=SqlIdentityEvidenceRepository(session, encryption),
        screening_port=ManualScreeningAdapter(),
        field_encryption=encryption,
        matter_access=_matter_access_stub,
        audit_port=audit_service,
    )

    _notification_service_instance = NotificationService(
        preferences=SqlPreferenceRepository(session),
        deliveries=SqlDeliveryRepository(session),
        email_port=build_email_adapter(),
        audit_port=audit_service,
        clock=NotificationClock(),
        recipient_resolver=SqlRecipientEmailResolver(session),
    )

    from src.modules.notarial_register.infrastructure.repository import (
        SqlAttestationRepository,
        SqlEventPort,
        SqlMonthlyReturnRepository,
        SqlProtocolRepository,
        SqlRegisterRepository,
        SqlRegistrationSubmissionRepository,
        StubApprovedInstrumentAdapter,
        StubMatterAccessAdapter as NotarialMatterAccess,
        SystemClock as NotarialClock,
    )

    _notarial_register_service_instance = NotarialRegisterService(
        attestation_repo=SqlAttestationRepository(session),
        register_repo=SqlRegisterRepository(session),
        protocol_repo=SqlProtocolRepository(session),
        registration_repo=SqlRegistrationSubmissionRepository(session),
        monthly_return_repo=SqlMonthlyReturnRepository(session),
        approved_instrument_port=StubApprovedInstrumentAdapter(),
        matter_access=NotarialMatterAccess(),
        audit_port=audit_service,
        event_port=SqlEventPort(session),
        clock=NotarialClock(),
    )


async def init_billing_service(session: AsyncSession) -> BillingService:
    """Initialize services for unauthenticated billing routes (webhooks)."""
    init_services(session)
    return get_billing_service_instance()


async def get_request_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    session: AsyncSession = Depends(get_db),
) -> RequestContext:
    """Core auth dependency — validates the Bearer token and builds RequestContext."""
    if credentials is None:
        raise UnauthenticatedError("Authorization header with Bearer token is required.")

    init_services(session)

    auth_service = get_auth_service_instance()
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())

    ctx = await auth_service.build_request_context(
        token=credentials.credentials,
        correlation_id=correlation_id,
    )

    bind_request_context(ctx.correlation_id, ctx.actor_id)
    return ctx


async def get_obligations_service(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db),
) -> ObligationsService:
    """Per-request obligations service wired to the current organisation scope."""
    global _obligations_service_instance, _obligations_org_id
    org_id = f"org_{ctx.actor_id}"
    if _obligations_service_instance is None or _obligations_org_id != org_id:
        obligation_repo = SqlObligationRepository(session)
        reminder_repo = SqlReminderRepository(session)
        audit_repo = SqlAuditRepository(session)
        audit_service = AuditService(repository=audit_repo)
        events = SqlObligationEventPort(session, org_id)
        notification_intents = SqlNotificationIntentPort()
        _obligations_service_instance = ObligationsService(
            obligation_repo=obligation_repo,
            reminder_repo=reminder_repo,
            deadline_rules=FixtureDeadlineRulePort(),
            events=events,
            audit=audit_service,
            clock=SystemClockPort(),
            notification_intents=notification_intents,
        )
        _obligations_org_id = org_id
    return _obligations_service_instance

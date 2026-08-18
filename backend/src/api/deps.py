"""Shared FastAPI dependencies — used by every module router.

The get_request_context dependency is the security perimeter for all
authenticated API routes. It validates the token, builds the RequestContext,
and rejects the request before any business logic runs.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import Depends, Header, Request
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
from src.modules.billing.infrastructure.repository import (
    SqlBillingWebhookEventRepository,
    SqlPlanRepository,
    SqlSubscriptionRepository,
    SqlUsageRepository,
)
from src.modules.billing.infrastructure.user_read import AuthUserReadAdapter
from src.modules.notarial_register.application.notarial_register_service import (
    NotarialRegisterService,
)
from src.modules.notification.application.notification_service import NotificationService
from src.modules.notification.infrastructure.service_factory import build_notification_service
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
from src.modules.party.infrastructure.matter_access_stub import StubMatterAccessAdapter
from src.modules.party.infrastructure.repository import (
    SqlIdentityEvidenceRepository,
    SqlPartyRepository,
)
from src.modules.party.infrastructure.stub_screening import ManualScreeningAdapter
from src.platform.config import get_settings
from src.platform.db.session import get_db
from src.platform.errors import PreconditionRequiredError, UnauthenticatedError
from src.platform.messaging.outbox import SqlOutboxEventPort
from src.platform.observability.logging import bind_request_context
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

_http_bearer = HTTPBearer(auto_error=False)


def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    """Build a request-scoped AuthService.

    Deliberately not a module-level singleton: the repositories below are bound
    to this request's AsyncSession, so a shared instance would let one request
    execute against another request's session after that session had closed.
    """
    from src.bootstrap import build_identity_adapter

    return AuthService(
        identity_port=build_identity_adapter(),
        user_identity_repo=SqlUserIdentityRepository(session),
        user_repo=SqlUserRepository(session),
        audit_port=AuditService(repository=SqlAuditRepository(session)),
    )


def get_matter_access_stub() -> StubMatterAccessAdapter:
    """Stub matter-access adapter; real matter authorisation is an open decision."""
    from src.bootstrap import build_party_matter_access

    return build_party_matter_access()


def get_party_service(
    session: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    matter_access: StubMatterAccessAdapter = Depends(get_matter_access_stub),
) -> PartyService:
    """Build a request-scoped PartyService.

    Request-scoped for the reason given in get_auth_service: the party and
    identity-evidence repositories below hold this request's AsyncSession, and
    protected identity data must never be read through another request's
    session.
    """
    from src.bootstrap import (
        AuthPractisingNotaryAdapter,
        build_party_event_adapter,
        build_party_field_encryption,
    )

    encryption = build_party_field_encryption()
    return PartyService(
        party_repo=SqlPartyRepository(session),
        identity_repo=SqlIdentityEvidenceRepository(session, encryption),
        screening_port=ManualScreeningAdapter(),
        field_encryption=encryption,
        matter_access=matter_access,
        audit_port=AuditService(repository=SqlAuditRepository(session)),
        event_port=build_party_event_adapter(),
        notary_port=AuthPractisingNotaryAdapter(auth_service),
    )


def get_notification_service(
    session: AsyncSession = Depends(get_db),
) -> NotificationService:
    """Build a request-scoped NotificationService."""
    return build_notification_service(session)


def get_notarial_register_service(
    session: AsyncSession = Depends(get_db),
) -> NotarialRegisterService:
    """Build a request-scoped NotarialRegisterService."""
    from src.modules.notarial_register.infrastructure.repository import (
        SqlAttestationRepository,
        SqlEventPort,
        SqlMonthlyReturnRepository,
        SqlProtocolRepository,
        SqlRegisterRepository,
        SqlRegistrationSubmissionRepository,
        StubApprovedInstrumentAdapter,
    )
    from src.modules.notarial_register.infrastructure.repository import (
        StubMatterAccessAdapter as NotarialMatterAccess,
    )
    from src.modules.notarial_register.infrastructure.repository import (
        SystemClock as NotarialClock,
    )

    return NotarialRegisterService(
        attestation_repo=SqlAttestationRepository(session),
        register_repo=SqlRegisterRepository(session),
        protocol_repo=SqlProtocolRepository(session),
        registration_repo=SqlRegistrationSubmissionRepository(session),
        monthly_return_repo=SqlMonthlyReturnRepository(session),
        approved_instrument_port=StubApprovedInstrumentAdapter(),
        matter_access=NotarialMatterAccess(),
        audit_port=AuditService(repository=SqlAuditRepository(session)),
        event_port=SqlEventPort(session),
        clock=NotarialClock(),
    )


def build_billing_service(session: AsyncSession) -> BillingService:
    """Construct a BillingService bound to this request's session."""
    from src.bootstrap import build_billing_adapter, build_platform_admin_adapter

    settings = get_settings()
    return BillingService(
        plan_repo=SqlPlanRepository(session),
        subscription_repo=SqlSubscriptionRepository(session),
        usage_repo=SqlUsageRepository(session),
        webhook_repo=SqlBillingWebhookEventRepository(session),
        billing_provider=build_billing_adapter(),
        user_read_port=AuthUserReadAdapter(SqlUserRepository(session)),
        platform_admin_port=build_platform_admin_adapter(),
        audit_port=AuditService(repository=SqlAuditRepository(session)),
        event_port=SqlOutboxEventPort(session),
        clock=BillingClock(),
        grace_period_days=settings.billing_grace_period_days,
    )


async def get_billing_service(
    session: AsyncSession = Depends(get_db),
) -> BillingService:
    """FastAPI dependency for billing routes, including the provider webhook."""
    return build_billing_service(session)


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> str:
    """Return the raw Bearer token, or reject the request."""
    if credentials is None:
        raise UnauthenticatedError("Authorization header with Bearer token is required.")
    return credentials.credentials


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", None) or str(uuid.uuid4())


def require_if_match(if_match: str | None = Header(default=None, alias="If-Match")) -> int:
    """Parse the ``If-Match`` header into the expected aggregate version.

    Optimistic concurrency travels as a conditional request, not a body field
    (api-conventions §3): a missing header is 428, a malformed one is 428 as
    well, and a stale value becomes 412 when the repository rejects the write.
    """
    if if_match is None:
        raise PreconditionRequiredError()
    try:
        return int(if_match.strip().strip('"').removeprefix("W/").strip('"'))
    except ValueError:
        raise PreconditionRequiredError(
            "If-Match must be the quoted integer version returned in ETag."
        )


async def get_request_context(
    token: str = Depends(get_bearer_token),
    correlation_id: str = Depends(get_correlation_id),
    auth_service: AuthService = Depends(get_auth_service),
) -> RequestContext:
    """Core auth dependency — validates the Bearer token and builds RequestContext.

    Requires an already-provisioned identity. First-time callers get
    AccountPendingError and must complete provisioning via
    ``POST /api/v1/me/provision`` before any other route will admit them.
    """
    ctx = await auth_service.build_request_context(
        token=token,
        correlation_id=correlation_id,
    )

    bind_request_context(ctx.correlation_id, ctx.actor_id)
    return ctx


async def get_obligations_service(
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db),
) -> ObligationsService:
    """Build a request-scoped ObligationsService for the caller's scope.

    Not cached per organisation: the repositories and the event port below hold
    this request's AsyncSession and this request's scope id, so reusing an
    instance across requests would write one caller's deadlines through
    another's session.
    """
    org_id = f"org_{ctx.actor_id}"
    return ObligationsService(
        obligation_repo=SqlObligationRepository(session),
        reminder_repo=SqlReminderRepository(session),
        deadline_rules=FixtureDeadlineRulePort(),
        events=SqlObligationEventPort(session, org_id),
        audit=AuditService(repository=SqlAuditRepository(session)),
        clock=SystemClockPort(),
        notification_intents=SqlNotificationIntentPort(),
    )

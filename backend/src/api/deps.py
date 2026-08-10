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
from src.modules.obligations.application.obligations_service import ObligationsService
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
from src.modules.obligations.infrastructure.repository import (
    SqlNotificationIntentPort,
    SqlObligationEventPort,
    SqlObligationRepository,
    SqlReminderRepository,
)
from src.modules.obligations.infrastructure.stubs import SystemClockPort
from src.platform.db.session import get_db
from src.platform.errors import UnauthenticatedError
from src.platform.observability.logging import bind_request_context
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

_http_bearer = HTTPBearer(auto_error=False)

_auth_service_instance: AuthService | None = None
_obligations_service_instance: ObligationsService | None = None
_obligations_org_id: str | None = None


def get_auth_service_instance() -> AuthService:
    """Return the singleton AuthService wired at startup."""
    global _auth_service_instance
    if _auth_service_instance is None:
        raise RuntimeError("AuthService not yet initialized. Call init_services() at startup.")
    return _auth_service_instance


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

    from src.bootstrap import build_identity_adapter

    identity_adapter = build_identity_adapter()

    global _auth_service_instance
    _auth_service_instance = AuthService(
        identity_port=identity_adapter,
        user_identity_repo=user_identity_repo,
        user_repo=user_repo,
        audit_port=audit_service,
    )


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

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
from src.modules.notarial_register.application.notarial_register_service import (
    NotarialRegisterService,
)
from src.platform.db.session import get_db
from src.platform.errors import UnauthenticatedError
from src.platform.observability.logging import bind_request_context
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

_http_bearer = HTTPBearer(auto_error=False)

_auth_service_instance: AuthService | None = None
_notarial_register_service_instance: NotarialRegisterService | None = None


def get_auth_service_instance() -> AuthService:
    """Return the singleton AuthService wired at startup."""
    global _auth_service_instance
    if _auth_service_instance is None:
        raise RuntimeError("AuthService not yet initialized. Call init_services() at startup.")
    return _auth_service_instance


def get_notarial_register_service() -> NotarialRegisterService:
    """Return the NotarialRegisterService wired for the current request session."""
    global _notarial_register_service_instance
    if _notarial_register_service_instance is None:
        raise RuntimeError(
            "NotarialRegisterService not yet initialized. Call init_services() at startup."
        )
    return _notarial_register_service_instance


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

    from src.modules.notarial_register.infrastructure.repository import (
        SqlAttestationRepository,
        SqlEventPort,
        SqlMonthlyReturnRepository,
        SqlProtocolRepository,
        SqlRegisterRepository,
        SqlRegistrationSubmissionRepository,
        StubApprovedInstrumentAdapter,
        StubMatterAccessAdapter,
        SystemClock,
    )

    global _notarial_register_service_instance
    _notarial_register_service_instance = NotarialRegisterService(
        attestation_repo=SqlAttestationRepository(session),
        register_repo=SqlRegisterRepository(session),
        protocol_repo=SqlProtocolRepository(session),
        registration_repo=SqlRegistrationSubmissionRepository(session),
        monthly_return_repo=SqlMonthlyReturnRepository(session),
        approved_instrument_port=StubApprovedInstrumentAdapter(),
        matter_access=StubMatterAccessAdapter(),
        audit_port=audit_service,
        event_port=SqlEventPort(session),
        clock=SystemClock(),
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

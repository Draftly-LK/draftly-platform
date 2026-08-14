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
from src.platform.db.session import get_db
from src.platform.errors import UnauthenticatedError
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


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> str:
    """Return the raw Bearer token, or reject the request."""
    if credentials is None:
        raise UnauthenticatedError("Authorization header with Bearer token is required.")
    return credentials.credentials


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", None) or str(uuid.uuid4())


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

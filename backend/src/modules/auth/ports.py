"""Auth module port definitions (Protocols).

Application services depend on these protocols, never on concrete adapters.
Infrastructure implements these protocols; wiring happens only in bootstrap.py.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.modules.auth.domain.models import User, UserIdentity


class IdentityClaims:
    """Verified claims extracted from a validated OIDC token."""

    def __init__(
        self,
        *,
        issuer: str,
        subject: str,
        verified_email: str | None = None,
        provider: str = "clerk",
        auth_time: int | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.issuer = issuer
        self.subject = subject
        self.verified_email = verified_email
        self.provider = provider
        self.auth_time = auth_time  # Unix timestamp of authentication
        self.raw: dict[str, Any] = raw or {}


class IdentityPort(Protocol):
    """Validate an OIDC token and return verified claims.

    Provider-neutral so the OIDC provider can change (plan §12).
    V0 implemented by ClerkIdentityAdapter; CI uses StubIdentityAdapter.
    """

    async def validate_token(self, token: str) -> IdentityClaims:
        """Validate the token and return claims. Raise IdentityValidationError on failure."""
        ...


class UserIdentityRepository(Protocol):
    """Resolve (issuer, subject) → UserIdentity; persist only via controlled path."""

    async def find_by_subject(self, issuer: str, subject: str) -> UserIdentity | None: ...

    async def find_by_verified_email(self, email: str) -> UserIdentity | None: ...

    async def create(self, identity: UserIdentity) -> UserIdentity: ...


class UserRepository(Protocol):
    async def get(self, user_id: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def create(self, user: User) -> User: ...

    async def update(self, user: User) -> User: ...


class AuditPort(Protocol):
    """Append-only audit event recorder.

    Called by every application service after a material mutation.
    Writes in the same database transaction as the mutation (audit-service.md §5).
    """

    async def record(self, event: AuditEventInput) -> None: ...


class AuditEventInput:
    """Input to AuditPort.record — actor and id are NOT caller-supplied."""

    def __init__(
        self,
        *,
        user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        matter_id: str | None = None,
        actor: str | None = None,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
        correlation_id: str = "",
        causation_id: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.action = action
        self.target_type = target_type
        self.target_id = target_id
        self.matter_id = matter_id
        self.actor = actor
        self.before_ref = before_ref
        self.after_ref = after_ref
        self.reason = reason
        self.correlation_id = correlation_id
        self.causation_id = causation_id

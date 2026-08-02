"""Auth module port definitions (Protocols).

Application services depend on these protocols, never on concrete adapters.
Infrastructure implements these protocols; wiring happens only in bootstrap.py.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.modules.auth.domain.models import (
    MatterMembership,
    MatterMembershipRole,
    Organisation,
    OrganisationMembership,
    OrgRole,
    Role,
    User,
    UserIdentity,
)


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

    async def create(self, identity: UserIdentity) -> UserIdentity: ...


class UserRepository(Protocol):
    async def get(self, user_id: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def create(self, user: User) -> User: ...

    async def update(self, user: User) -> User: ...


class OrganisationRepository(Protocol):
    async def get(self, org_id: str) -> Organisation | None: ...


class OrganisationMembershipRepository(Protocol):
    """Verify active organisation membership and load org role."""

    async def find(self, org_id: str, user_id: str) -> OrganisationMembership | None: ...

    async def create(self, membership: OrganisationMembership) -> OrganisationMembership: ...

    async def count_owners(self, org_id: str) -> int: ...


class MatterMembershipRepository(Protocol):
    """Load and mutate matter memberships — always org-scoped."""

    async def list_for_user(self, org_id: str, user_id: str) -> list[MatterMembership]: ...

    async def find(
        self, org_id: str, matter_id: str, user_id: str
    ) -> MatterMembership | None: ...

    async def create(self, membership: MatterMembership) -> MatterMembership: ...

    async def update(self, membership: MatterMembership) -> MatterMembership: ...


class MembershipCommandPort(Protocol):
    """Used by matter_service to grant the initial owner membership.

    matter_service never writes the matter_memberships table directly; it calls
    this port inside its creation transaction (security-model.md §4).
    """

    async def grant_owner_membership(
        self,
        org_id: str,
        matter_id: str,
        user_id: str,
    ) -> None: ...


class InvitationRepository(Protocol):
    async def find_active(self, org_id: str, email: str) -> Any | None: ...

    async def mark_accepted(self, invitation_id: str) -> None: ...


class AuditPort(Protocol):
    """Append-only audit event recorder.

    Called by every application service after a material mutation.
    Writes in the same database transaction as the mutation (audit-service.md §5).
    """

    async def record(self, event: "AuditEventInput") -> None: ...


class AuditEventInput:
    """Input to AuditPort.record — actor and id are NOT caller-supplied."""

    def __init__(
        self,
        *,
        organisation_id: str,
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
        self.organisation_id = organisation_id
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

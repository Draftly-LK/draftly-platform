"""Auth domain models — identity, accounts, roles, and memberships.

These are pure domain entities with no FastAPI, SQLAlchemy, or Clerk imports.
The server owns every field that determines access; the browser supplies none.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ── Enumerations ─────────────────────────────────────────────────────────────


class AccountStatus(str, enum.Enum):
    """Lifecycle state of a Draftly user account."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Role(str, enum.Enum):
    """The four Draftly account roles (mirrors frontend user.ts).

    No fifth role is invented here — any new capability tier is a product
    decision that goes through the plan (auth-service.md §10.6).
    """

    REVIEWER = "reviewer"
    APPROVER = "approver"
    MAINTAINER = "maintainer"
    ADMINISTRATOR = "administrator"


class OrgRole(str, enum.Enum):
    """Organisation-level membership role — MVP: owner | member.

    'admin' is deliberately omitted for the MVP; it can be added when the
    product needs delegated workspace administration without full ownership.
    """

    OWNER = "owner"
    MEMBER = "member"


class MatterMembershipRole(str, enum.Enum):
    """Role a user holds on a specific matter."""

    ASSIGNEE = "assignee"
    SUPERVISOR = "supervisor"


class OrgStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class OrgType(str, enum.Enum):
    SOLO = "solo"
    FIRM = "firm"
    ENTERPRISE = "enterprise"
    DEMO = "demo"


# ── Domain entities ───────────────────────────────────────────────────────────


@dataclass
class User:
    """Draftly application user. The server owns role and account_status."""

    id: str
    display_name: str
    account_status: AccountStatus
    role: Role | None  # nullable while pending
    notary_registration: str | None
    jurisdiction: str | None
    created_at: datetime
    updated_at: datetime
    qualifications: str | None = None
    professional_titles: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    phone: str | None = None


@dataclass
class UserIdentity:
    """External identity link keyed by (issuer, subject) — never by email.

    For Clerk-issued tokens, issuer and subject are the verified Clerk issuer
    and stable Clerk user ID. Upstream Google/email metadata may be retained
    for audit but is not the application key.
    """

    user_id: str
    provider: str  # "clerk"
    issuer: str
    subject: str
    verified_email: str | None
    linked_at: datetime


@dataclass
class Organisation:
    """Tenant / workspace boundary. Every matter and subscription is scoped here."""

    id: str
    name: str
    type: OrgType
    status: OrgStatus
    created_at: datetime


@dataclass
class OrganisationMembership:
    """Maps a user to an organisation with an org-level role (owner | member)."""

    organisation_id: str
    user_id: str
    org_role: OrgRole
    joined_at: datetime


@dataclass
class MatterMembership:
    """Join table: (user, matter, role) within one organisation."""

    organisation_id: str
    matter_id: str
    user_id: str
    role: MatterMembershipRole
    assigned_at: datetime


@dataclass
class Invitation:
    """Admin-issued invitation that activates a pending account.

    On first login, the pending user's identity is matched to an invitation.
    Only the role and matter memberships recorded on the invitation are applied.
    The browser cannot approve its own account or select a role.
    """

    id: str
    organisation_id: str
    email: str  # matched after Clerk verifies it; never used as the auth key
    assigned_role: Role
    matter_memberships: list[tuple[str, MatterMembershipRole]] = field(default_factory=list)
    invited_by: str = ""  # actor_id of the administrator
    expires_at: datetime | None = None
    accepted_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False

        return datetime.now(tz=UTC) > self.expires_at

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

"""Auth domain models — identity, accounts, and roles.

These are pure domain entities with no FastAPI, SQLAlchemy, or Clerk imports.
The server owns every field that determines access; the browser supplies none.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime

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
    """External identity link keyed by (issuer, subject) — never by email alone.

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

"""API response/request schemas for the auth module.

UserRead matches the frontend User type exactly:
  id, displayName, role, notaryRegistration, jurisdiction
so the frontend can call GET /api/v1/me and use the result directly.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class UserRead(BaseModel):
    """Mirrors frontend/src/types/user.ts User interface exactly.

    model_dump(by_alias=True) → camelCase keys matching the frontend type.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: str
    display_name: str
    role: str
    notary_registration: str | None = None
    jurisdiction: str | None = None


class AccountStatusRead(BaseModel):
    """Returned for authenticated-but-pending accounts."""

    status: str  # "pending" | "active" | "suspended"
    message: str


class MembershipRead(BaseModel):
    """Returned after a successful membership assignment."""

    matter_id: str
    user_id: str
    role: str


class MatterMembershipRequest(BaseModel):
    user_id: str
    role: str = "assignee"  # "assignee" | "supervisor"


class SetRoleRequest(BaseModel):
    role: str  # "reviewer" | "approver" | "maintainer" | "administrator"

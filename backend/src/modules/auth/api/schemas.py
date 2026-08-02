"""API response/request schemas for the auth module.

UserRead matches the frontend User type exactly:
  id, displayName, role, notaryRegistration, jurisdiction
so the frontend can call GET /api/v1/me and use the result directly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    """Mirrors frontend/src/types/user.ts User interface exactly."""

    id: str
    displayName: str = Field(alias="display_name")
    role: str
    notaryRegistration: str | None = Field(default=None, alias="notary_registration")
    jurisdiction: str | None = None

    model_config = {"populate_by_name": True}


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

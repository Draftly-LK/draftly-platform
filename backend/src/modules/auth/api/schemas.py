"""API response/request schemas for the auth module.

UserRead matches the frontend User type exactly (camelCase aliases).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class UserRead(BaseModel):
    """Mirrors frontend/src/types/user.ts User interface.

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
    qualifications: str | None = None
    professional_titles: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    phone: str | None = None


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
    role: str

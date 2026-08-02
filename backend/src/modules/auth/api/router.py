"""Auth API router.

Routes:
  GET  /api/v1/me                             → get_current_user
  GET  /api/v1/account-status                 → account status (authenticated/pending)
  POST /api/v1/matters/{matter_id}/memberships → assign_membership (administrator only)
  PATCH /api/v1/users/{user_id}/role           → set_user_role (administrator only)

All routes consume RequestContext via Depends(get_request_context).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.modules.auth.api.schemas import (
    AccountStatusRead,
    MatterMembershipRequest,
    MembershipRead,
    SetRoleRequest,
    UserRead,
)
from src.modules.auth.domain.models import MatterMembershipRole, Role
from src.platform.errors import DraftlyError
from src.platform.request_context import RequestContext
from src.api.deps import get_request_context, get_auth_service_instance

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=UserRead)
async def get_current_user(
    ctx: RequestContext = Depends(get_request_context),
) -> UserRead:
    """Return the authenticated user's profile.

    Mirrors frontend User shape exactly:
      id, displayName, role, notaryRegistration, jurisdiction
    Used by the frontend sidebar profile display.
    """
    auth_service = get_auth_service_instance()
    user = await auth_service.get_current_user(ctx)
    return UserRead(
        id=user.id,
        display_name=user.display_name,
        role=user.role.value if user.role else "pending",
        notary_registration=user.notary_registration,
        jurisdiction=user.jurisdiction,
    )


@router.get("/account-status", response_model=AccountStatusRead)
async def get_account_status() -> AccountStatusRead:
    """Return account activation status. Does NOT require a full active context.

    Called by the frontend before a user is approved to show a pending screen.
    """
    return AccountStatusRead(
        status="pending",
        message="Your account is awaiting approval by an administrator.",
    )


@router.post("/matters/{matter_id}/memberships", response_model=MembershipRead)
async def assign_membership(
    matter_id: str,
    body: MatterMembershipRequest,
    ctx: RequestContext = Depends(get_request_context),
) -> MembershipRead:
    """Assign or update a user's role on a matter (administrator only)."""
    auth_service = get_auth_service_instance()
    try:
        role = MatterMembershipRole(body.role)
    except ValueError:
        raise DraftlyError(
            f"Invalid role '{body.role}'. Valid values: assignee, supervisor."
        )
    membership = await auth_service.assign_membership(ctx, matter_id, body.user_id, role)
    return MembershipRead(
        matter_id=membership.matter_id,
        user_id=membership.user_id,
        role=membership.role.value,
    )


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def set_user_role(
    user_id: str,
    body: SetRoleRequest,
    ctx: RequestContext = Depends(get_request_context),
) -> UserRead:
    """Update a user's account role (administrator only). Audited."""
    auth_service = get_auth_service_instance()
    try:
        new_role = Role(body.role)
    except ValueError:
        raise DraftlyError(
            f"Invalid role '{body.role}'. Valid: reviewer, approver, maintainer, administrator."
        )
    user = await auth_service.set_user_role(ctx, user_id, new_role)
    return UserRead(
        id=user.id,
        display_name=user.display_name,
        role=user.role.value if user.role else "pending",
        notary_registration=user.notary_registration,
        jurisdiction=user.jurisdiction,
    )

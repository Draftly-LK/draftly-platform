"""Auth API router.

Routes:
  GET  /api/v1/me                             → get_current_user
  GET  /api/v1/account-status                 → account status
  PATCH /api/v1/users/{user_id}/role           → set_user_role (capability-gated)

All routes consume RequestContext via Depends(get_request_context).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_auth_service_instance, get_request_context
from src.modules.auth.api.schemas import AccountStatusRead, SetRoleRequest, UserRead
from src.modules.auth.domain.models import Role, User
from src.platform.errors import DraftlyError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["auth"])


def _to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        display_name=user.display_name,
        role=user.role.value if user.role else "pending",
        notary_registration=user.notary_registration,
        jurisdiction=user.jurisdiction,
        qualifications=user.qualifications,
        professional_titles=user.professional_titles,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
        phone=user.phone,
    )


@router.get("/me", response_model=UserRead)
async def get_current_user(
    ctx: RequestContext = Depends(get_request_context),
) -> UserRead:
    """Return the authenticated user's profile (frontend User shape)."""
    auth_service = get_auth_service_instance()
    user = await auth_service.get_current_user(ctx)
    return _to_user_read(user)


@router.get("/account-status", response_model=AccountStatusRead)
async def get_account_status(
    ctx: RequestContext = Depends(get_request_context),
) -> AccountStatusRead:
    """Return account activation status for the authenticated user."""
    _ = ctx
    return AccountStatusRead(
        status="active",
        message="Your account is active.",
    )


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def set_user_role(
    user_id: str,
    body: SetRoleRequest,
    ctx: RequestContext = Depends(get_request_context),
) -> UserRead:
    """Update a user's account role. Audited."""
    auth_service = get_auth_service_instance()
    try:
        new_role = Role(body.role)
    except ValueError:
        raise DraftlyError(
            f"Invalid role '{body.role}'. Valid: reviewer, approver, maintainer, administrator."
        )
    user = await auth_service.set_user_role(ctx, user_id, new_role)
    return _to_user_read(user)

"""Auth API router.

Routes:
  POST  /api/v1/me/provision      → first-login provisioning (no prior identity)
  GET   /api/v1/me                → get_current_user
  PATCH /api/v1/me                → update own professional/contact fields
  GET   /api/v1/account-status    → account status
  PATCH /api/v1/me/role           → set own role (step-up gated)

Every route except provisioning consumes RequestContext via
Depends(get_request_context). Provisioning cannot, because the context it would
build does not exist until provisioning has run.

Mutating routes depend on ``get_uow`` so the mutation and its audit event commit
as one transaction.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from src.api.deps import (
    get_auth_service,
    get_bearer_token,
    get_correlation_id,
    get_request_context,
)
from src.modules.auth.api.schemas import (
    AccountStatusRead,
    SetRoleRequest,
    UpdateProfileRequest,
    UserRead,
)
from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.domain.models import Role, User
from src.platform.db.session import get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
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


@router.post("/me/provision", response_model=UserRead)
async def provision_me(
    token: str = Depends(get_bearer_token),
    correlation_id: str = Depends(get_correlation_id),
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_uow),
) -> UserRead:
    """Link a verified identity to a Draftly account on first login.

    Deliberately outside ``get_request_context``: a brand-new subject has no
    UserIdentity yet, so building the normal context would reject it and leave
    the account unreachable. This route validates the token itself, provisions
    the user and identity, and commits through the UnitOfWork. It is idempotent
    — an already-linked identity returns the existing user.
    """
    _ = uow  # commits on success, rolls back on failure
    user = await auth_service.provision_identity(token=token, correlation_id=correlation_id)
    return _to_user_read(user)


@router.get("/me", response_model=UserRead)
async def get_current_user(
    ctx: RequestContext = Depends(get_request_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserRead:
    """Return the authenticated user's profile (frontend User shape)."""
    user = await auth_service.get_current_user(ctx)
    return _to_user_read(user)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    body: UpdateProfileRequest,
    ctx: RequestContext = Depends(get_request_context),
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_uow),
) -> UserRead:
    """Update the caller's own professional and contact fields.

    The request schema admits only editable fields; identity, role, account
    status, verified email and certificate approval state are server-owned and
    are rejected by the schema before reaching the service.
    """
    _ = uow
    changes = body.model_dump(exclude_unset=True, by_alias=False)
    user = await auth_service.update_own_profile(ctx, changes)
    return _to_user_read(user)


@router.get("/account-status", response_model=AccountStatusRead)
async def get_account_status(
    ctx: RequestContext = Depends(get_request_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> AccountStatusRead:
    """Return account activation status for the authenticated user."""
    user = await auth_service.get_current_user(ctx)
    status = user.account_status.value
    messages = {
        "active": "Your account is active.",
        "pending": "Your account is awaiting activation.",
        "suspended": "Your account is suspended.",
    }
    return AccountStatusRead(
        status=status,
        message=messages.get(status, "Account status unavailable."),
    )


@router.patch("/me/role", response_model=UserRead)
async def set_own_role(
    body: SetRoleRequest,
    ctx: RequestContext = Depends(get_request_context),
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_uow),
    step_up_token: str | None = Header(default=None, alias="X-Step-Up-Token"),
) -> UserRead:
    """Change the caller's own account role. Step-up gated and audited.

    Scoped to ``ctx.actor_id`` rather than a path parameter: in the solo model
    every user is an approver holding ``user.role.set``, so a user-id path
    would let any customer edit another customer's role.
    """
    _ = uow
    try:
        new_role = Role(body.role)
    except ValueError:
        raise DomainRuleError(
            f"Invalid role '{body.role}'. Valid: reviewer, approver, maintainer, administrator."
        )
    user = await auth_service.set_user_role(
        ctx,
        ctx.actor_id,
        new_role,
        step_up_token=step_up_token,
    )
    return _to_user_read(user)

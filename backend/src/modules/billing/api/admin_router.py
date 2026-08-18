"""Plan administration routes — `platform.administer` only.

These are Draftly staff operations, not account administration. A firm
`administrator` cannot reach them (security-model.md §3.4, billing-service.md
§11), and the grant is resolved server-side per request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_billing_service, get_request_context
from src.modules.billing.api.presenters import plan_read, subscription_read
from src.modules.billing.api.schemas import (
    CreatePlanRequest,
    GrantTrialRequest,
    PlanRead,
    SubscriptionRead,
)
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.domain.errors import InvalidPlanInputError
from src.modules.billing.domain.models import (
    BillingInterval,
    EntitlementRequest,
    PlanVersionDraft,
)
from src.platform.db.session import get_db
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.request_context import RequestContext

router = APIRouter(prefix="/admin", tags=["billing-admin"])


@router.post("/plans", response_model=PlanRead, status_code=201)
async def create_plan(
    body: CreatePlanRequest,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
) -> PlanRead:
    """Draft a new plan version. It is not offered for checkout until activated."""
    try:
        interval = BillingInterval(body.billing_interval)
    except ValueError:
        raise InvalidPlanInputError(
            "billingInterval must be one of: trial, monthly, yearly.",
            billingInterval=body.billing_interval,
        )

    draft = PlanVersionDraft(
        code=body.code,
        family=body.family,
        name=body.name,
        billing_interval=interval,
        currency=body.currency,
        price_minor_units=body.price_minor_units,
        entitlements=[
            EntitlementRequest(
                feature_key=e.feature_key,
                limit_value=e.limit_value,
                enabled=e.enabled,
            )
            for e in body.entitlements
        ],
    )
    async with UnitOfWork(session):
        plan, entitlements = await billing.create_plan_version(ctx, draft)
    return plan_read(plan, entitlements)


@router.post("/plans/{plan_version_id}/activate", response_model=PlanRead)
async def activate_plan(
    plan_version_id: str,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
) -> PlanRead:
    """Publish a draft plan version. Published versions are immutable thereafter."""
    async with UnitOfWork(session):
        plan = await billing.activate_plan_version(ctx, plan_version_id)
        entitlements = await billing.list_entitlements_for_admin(ctx, plan.id)
    return plan_read(plan, entitlements)


@router.post("/subscriptions/{id}/grant-trial", response_model=SubscriptionRead)
async def grant_trial(
    id: str,
    body: GrantTrialRequest,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    """Provision a trial subscription for an existing active account."""
    async with UnitOfWork(session):
        sub = await billing.grant_trial(
            ctx,
            user_id=id,
            plan_version_id=body.plan_version_id,
            trial_days=body.trial_days,
        )
    return subscription_read(sub)

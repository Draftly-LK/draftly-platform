"""Billing API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import (
    get_billing_service_instance,
    get_request_context,
    init_billing_service,
)
from src.modules.billing.api.schemas import (
    CheckoutRead,
    CheckoutRequest,
    PlanEntitlementRead,
    PlanRead,
    PortalRead,
    SubscriptionRead,
    UsageReadSchema,
    WebhookReceiptRead,
)
from src.modules.billing.domain.models import PlanEntitlement, Subscription, UsageRead
from src.modules.billing.ports import RawWebhook
from src.platform.db.session import get_db
from src.platform.request_context import RequestContext

router = APIRouter(prefix="/billing", tags=["billing"])


def _subscription_read(sub: Subscription) -> SubscriptionRead:
    return SubscriptionRead(
        id=sub.id,
        user_id=sub.user_id,
        plan_version_id=sub.plan_version_id,
        provider=sub.provider,
        status=sub.status.value,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        trial_ends_at=sub.trial_ends_at,
        cancel_at_period_end=sub.cancel_at_period_end,
        grace_period_ends_at=sub.grace_period_ends_at,
    )


def _usage_read(u: UsageRead) -> UsageReadSchema:
    return UsageReadSchema(
        metric=u.metric,
        quantity=u.quantity,
        period_start=u.period_start,
        period_end=u.period_end,
        limit_value=u.limit_value,
    )


@router.get("/plans", response_model=list[PlanRead])
async def list_plans(
    ctx: RequestContext = Depends(get_request_context),
) -> list[PlanRead]:
    billing = get_billing_service_instance()
    rows = await billing.list_plans(ctx)
    out: list[PlanRead] = []
    for row in rows:
        plan = row["plan"]
        entitlements: list[PlanEntitlement] = row["entitlements"]
        out.append(
            PlanRead(
                id=plan.id,
                code=plan.code,
                family=plan.family,
                name=plan.name,
                version=plan.version,
                billing_interval=plan.billing_interval.value,
                currency=plan.currency,
                price_minor_units=plan.price_minor_units,
                entitlements=[
                    PlanEntitlementRead(
                        feature_key=e.feature_key,
                        limit_value=e.limit_value,
                        enabled=e.enabled,
                    )
                    for e in entitlements
                ],
            )
        )
    return out


@router.get("/subscription", response_model=SubscriptionRead)
async def get_subscription(
    ctx: RequestContext = Depends(get_request_context),
) -> SubscriptionRead:
    billing = get_billing_service_instance()
    sub = await billing.get_subscription(ctx)
    return _subscription_read(sub)


@router.get("/usage", response_model=list[UsageReadSchema])
async def get_usage(
    ctx: RequestContext = Depends(get_request_context),
) -> list[UsageReadSchema]:
    billing = get_billing_service_instance()
    usage = await billing.get_usage(ctx)
    return [_usage_read(u) for u in usage]


@router.post("/checkout", response_model=CheckoutRead)
async def create_checkout(
    body: CheckoutRequest,
    ctx: RequestContext = Depends(get_request_context),
) -> CheckoutRead:
    billing = get_billing_service_instance()
    result = await billing.create_checkout(ctx, body.plan_version_id, body.return_path)
    return CheckoutRead(
        checkout_url=result["checkout_url"],
        session_id=result["session_id"],
    )


@router.post("/customer-portal", response_model=PortalRead)
async def create_customer_portal(
    ctx: RequestContext = Depends(get_request_context),
) -> PortalRead:
    billing = get_billing_service_instance()
    result = await billing.create_customer_portal(ctx)
    return PortalRead(portal_url=result["portal_url"])


@router.post("/cancel", response_model=SubscriptionRead)
async def cancel_subscription(
    ctx: RequestContext = Depends(get_request_context),
) -> SubscriptionRead:
    billing = get_billing_service_instance()
    sub = await billing.cancel_subscription(ctx)
    return _subscription_read(sub)


@router.post("/reactivate", response_model=SubscriptionRead)
async def reactivate_subscription(
    ctx: RequestContext = Depends(get_request_context),
) -> SubscriptionRead:
    billing = get_billing_service_instance()
    sub = await billing.reactivate_subscription(ctx)
    return _subscription_read(sub)


@router.post("/webhooks/payhere", response_model=WebhookReceiptRead)
async def payhere_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> WebhookReceiptRead:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    billing = await init_billing_service(session)
    receipt = await billing.handle_webhook(
        "payhere",
        RawWebhook(headers=headers, body=body, provider="payhere"),
    )
    return WebhookReceiptRead(
        provider_event_id=receipt.provider_event_id,
        processing_state=receipt.processing_state.value,
        duplicate=receipt.duplicate,
    )

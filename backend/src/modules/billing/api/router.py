"""Billing API router.

The router parses requests, enforces the wire-level conventions (pagination,
`If-Match`, `Idempotency-Key`, body limits), and commits the unit of work. It
never grants an entitlement, and the checkout return page is display-only.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_billing_service, get_request_context
from src.modules.billing.api.presenters import plan_read, subscription_read, usage_read
from src.modules.billing.api.schemas import (
    CheckoutRead,
    CheckoutRequest,
    PlanRead,
    PortalRead,
    SubscriptionRead,
    UsageReadSchema,
    WebhookReceiptRead,
)
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.domain.errors import WebhookPayloadTooLargeError
from src.modules.billing.ports import RawWebhook
from src.platform.api.conditional import etag_for_version, require_if_match
from src.platform.api.pagination import Page, clamp_limit, paginate_by_id
from src.platform.config import get_settings
from src.platform.db.idempotency import (
    IdempotencyKeyRequiredError,
    SqlIdempotencyStore,
    request_fingerprint,
)
from src.platform.db.session import get_db
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.request_context import RequestContext

router = APIRouter(prefix="/billing", tags=["billing"])

_CHECKOUT_ROUTE = "POST /api/v1/billing/checkout"


@router.get("/plans", response_model=Page[PlanRead])
async def list_plans(
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> Page[PlanRead]:
    rows = await billing.list_plans(ctx)
    reads = [plan_read(plan, entitlements) for plan, entitlements in rows]
    window, page = paginate_by_id(reads, limit=clamp_limit(limit), cursor=cursor)
    return Page[PlanRead](items=window, page=page)


@router.get("/subscription", response_model=SubscriptionRead)
async def get_subscription(
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
) -> SubscriptionRead:
    sub = await billing.get_subscription(ctx)
    response.headers["ETag"] = etag_for_version(sub.version)
    return subscription_read(sub)


@router.get("/usage", response_model=Page[UsageReadSchema])
async def get_usage(
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> Page[UsageReadSchema]:
    usage = [usage_read(u) for u in await billing.get_usage(ctx)]
    window, page = paginate_by_id(usage, limit=clamp_limit(limit), cursor=cursor, key="metric")
    return Page[UsageReadSchema](items=window, page=page)


@router.post("/checkout", response_model=CheckoutRead)
async def create_checkout(
    body: CheckoutRequest,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CheckoutRead:
    """Create a provider checkout. A replayed `Idempotency-Key` returns the first result."""
    if not idempotency_key:
        raise IdempotencyKeyRequiredError()

    store = SqlIdempotencyStore(session)
    fingerprint = request_fingerprint(body.model_dump(by_alias=True))
    replayed = await store.find(
        user_id=ctx.actor_id,
        route=_CHECKOUT_ROUTE,
        key=idempotency_key,
        request_hash=fingerprint,
    )
    if replayed is not None:
        return CheckoutRead.model_validate(replayed)

    async with UnitOfWork(session):
        result = await billing.create_checkout(ctx, body.plan_version_id, body.return_path)
        read = CheckoutRead(
            checkout_url=result["checkout_url"],
            session_id=result["session_id"],
        )
        await store.store(
            record_id=f"idem_{uuid.uuid4().hex[:16]}",
            user_id=ctx.actor_id,
            route=_CHECKOUT_ROUTE,
            key=idempotency_key,
            request_hash=fingerprint,
            response=read.model_dump(by_alias=True),
        )
    return read


@router.post("/customer-portal", response_model=PortalRead)
async def create_customer_portal(
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
) -> PortalRead:
    async with UnitOfWork(session):
        result = await billing.create_customer_portal(ctx)
    return PortalRead(portal_url=result["portal_url"])


@router.post("/cancel", response_model=SubscriptionRead)
async def cancel_subscription(
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> SubscriptionRead:
    expected_version = require_if_match(if_match)
    async with UnitOfWork(session):
        sub = await billing.cancel_subscription(ctx, expected_version)
    response.headers["ETag"] = etag_for_version(sub.version)
    return subscription_read(sub)


@router.post("/reactivate", response_model=SubscriptionRead)
async def reactivate_subscription(
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> SubscriptionRead:
    expected_version = require_if_match(if_match)
    async with UnitOfWork(session):
        sub = await billing.reactivate_subscription(ctx, expected_version)
    response.headers["ETag"] = etag_for_version(sub.version)
    return subscription_read(sub)


@router.post("/webhooks/payhere", response_model=WebhookReceiptRead)
async def payhere_webhook(
    request: Request,
    billing: BillingService = Depends(get_billing_service),
    session: AsyncSession = Depends(get_db),
) -> WebhookReceiptRead:
    """Provider webhook.

    No user authentication: the provider signature over the unmodified raw body
    is the only credential. The body is size-capped before it is parsed, and the
    subscription update, event row, audit event, and outbox rows commit
    together.
    """
    max_bytes = get_settings().billing_webhook_max_body_bytes
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise WebhookPayloadTooLargeError(limitBytes=max_bytes)

    body = await request.body()
    if len(body) > max_bytes:
        raise WebhookPayloadTooLargeError(limitBytes=max_bytes)

    headers: dict[str, str] = {k.lower(): v for k, v in request.headers.items()}
    async with UnitOfWork(session):
        receipt = await billing.handle_webhook(
            "payhere",
            RawWebhook(headers=headers, body=body, provider="payhere"),
        )
    return WebhookReceiptRead(
        provider_event_id=receipt.provider_event_id,
        processing_state=receipt.processing_state.value,
        duplicate=receipt.duplicate,
    )

"""Domain-to-wire mapping for billing. Domain objects are never serialised directly."""

from __future__ import annotations

from src.modules.billing.api.schemas import (
    PlanEntitlementRead,
    PlanRead,
    SubscriptionRead,
    UsageReadSchema,
)
from src.modules.billing.domain.models import (
    PlanEntitlement,
    PlanVersion,
    Subscription,
    UsageRead,
)


def subscription_read(sub: Subscription) -> SubscriptionRead:
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
        version=sub.version,
    )


def plan_read(plan: PlanVersion, entitlements: list[PlanEntitlement]) -> PlanRead:
    return PlanRead(
        id=plan.id,
        code=plan.code,
        family=plan.family,
        name=plan.name,
        version=plan.version,
        billing_interval=plan.billing_interval.value,
        currency=plan.currency,
        price_minor_units=plan.price_minor_units,
        state=plan.state.value,
        entitlements=[
            PlanEntitlementRead(
                feature_key=e.feature_key,
                limit_value=e.limit_value,
                enabled=e.enabled,
            )
            for e in entitlements
        ],
    )


def usage_read(usage: UsageRead) -> UsageReadSchema:
    return UsageReadSchema(
        metric=usage.metric,
        quantity=usage.quantity,
        period_start=usage.period_start,
        period_end=usage.period_end,
        limit_value=usage.limit_value,
    )

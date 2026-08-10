"""Billing API schemas — camelCase aliases like auth UserRead."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class PlanEntitlementRead(_CamelModel):
    feature_key: str
    limit_value: int | None = None
    enabled: bool


class PlanRead(_CamelModel):
    id: str
    code: str
    family: str
    name: str
    version: int
    billing_interval: str
    currency: str
    price_minor_units: int
    entitlements: list[PlanEntitlementRead] = Field(default_factory=list)


class SubscriptionRead(_CamelModel):
    id: str
    user_id: str
    plan_version_id: str
    provider: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    trial_ends_at: datetime | None = None
    cancel_at_period_end: bool
    grace_period_ends_at: datetime | None = None


class UsageReadSchema(_CamelModel):
    metric: str
    quantity: int
    period_start: datetime
    period_end: datetime
    limit_value: int | None = None


class CheckoutRead(_CamelModel):
    checkout_url: str
    session_id: str


class PortalRead(_CamelModel):
    portal_url: str


class CheckoutRequest(_CamelModel):
    plan_version_id: str
    return_path: str


class WebhookReceiptRead(_CamelModel):
    provider_event_id: str
    processing_state: str
    duplicate: bool = False

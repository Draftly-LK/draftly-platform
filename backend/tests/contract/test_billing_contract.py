"""Contract tests for billing API schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from src.modules.billing.api.schemas import (
    CheckoutRead,
    PlanRead,
    SubscriptionRead,
    UsageReadSchema,
)


class TestBillingContract:
    def test_subscription_read_camel_case(self):
        now = datetime(2026, 8, 1, tzinfo=UTC)
        read = SubscriptionRead(
            id="sub_1",
            user_id="usr_1",
            plan_version_id="plan_solo_v1",
            provider="payhere",
            status="active",
            current_period_start=now,
            current_period_end=now,
            cancel_at_period_end=False,
        )
        data = read.model_dump(by_alias=True)
        assert data["userId"] == "usr_1"
        assert data["planVersionId"] == "plan_solo_v1"
        assert data["currentPeriodStart"] == now
        assert "user_id" not in data

    def test_plan_read_camel_case(self):
        read = PlanRead(
            id="plan_solo_v1",
            code="solo-v1",
            family="solo",
            name="Solo",
            version=1,
            billing_interval="monthly",
            currency="LKR",
            price_minor_units=499900,
            entitlements=[],
        )
        data = read.model_dump(by_alias=True)
        assert data["billingInterval"] == "monthly"
        assert data["priceMinorUnits"] == 499900

    def test_usage_read_camel_case(self):
        now = datetime(2026, 8, 1, tzinfo=UTC)
        read = UsageReadSchema(
            metric="document_pages.monthly",
            quantity=12,
            period_start=now,
            period_end=now,
            limit_value=500,
        )
        data = read.model_dump(by_alias=True)
        assert data["limitValue"] == 500
        assert data["periodStart"] == now

    def test_checkout_read_camel_case(self):
        read = CheckoutRead(checkout_url="https://example/checkout", session_id="sess_1")
        data = read.model_dump(by_alias=True)
        assert data["checkoutUrl"] == "https://example/checkout"
        assert data["sessionId"] == "sess_1"

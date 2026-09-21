"""Unit tests for BillingService — in-memory fakes, no DB."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from src.modules.auth.domain.errors import CapabilityDeniedError
from src.modules.auth.domain.models import Role
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.domain.errors import (
    FeatureDeniedError,
    QuotaExceededError,
)
from src.modules.billing.domain.models import (
    BillingInterval,
    BillingWebhookEvent,
    PlanEntitlement,
    PlanState,
    PlanVersion,
    Reservation,
    Subscription,
    SubscriptionStatus,
    UsageAggregate,
    UsageLedgerEntry,
    UsageLedgerState,
    WebhookProcessingState,
)
from src.modules.billing.domain.policies import can_transition, is_known_feature_key
from src.modules.billing.infrastructure.stub_adapter import StubBillingAdapter
from src.modules.billing.ports import AuditEventInput, BillingUser, RawWebhook
from src.platform.messaging.outbox import InMemoryEventPort
from src.platform.request_context import RequestContext

_NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
_PERIOD_END = _NOW + timedelta(days=30)


class FakeClock:
    def __init__(self, now: datetime = _NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


class FakeEventPort(InMemoryEventPort):
    """Test double wired through the platform in-memory outbox port."""


class FakeUserReadPort:
    def __init__(self, active_users: frozenset[str] | None = None) -> None:
        self._active = active_users or frozenset({"usr_a", "usr_b"})

    async def get_billing_user(self, user_id: str) -> BillingUser | None:
        if user_id not in self._active:
            return None
        return BillingUser(user_id=user_id, is_active=True)


class DenyPlatformAdminPort:
    async def is_platform_admin(self, user_id: str) -> bool:
        _ = user_id
        return False


class FakePlanRepo:
    def __init__(
        self,
        plans: list[PlanVersion],
        entitlements: dict[str, list[PlanEntitlement]],
    ) -> None:
        self._plans = {p.id: p for p in plans}
        self._entitlements = entitlements

    async def list_active(self) -> list[PlanVersion]:
        return [p for p in self._plans.values() if p.state == PlanState.ACTIVE]

    async def get(self, plan_version_id: str) -> PlanVersion | None:
        return self._plans.get(plan_version_id)

    async def get_entitlements(self, plan_version_id: str) -> list[PlanEntitlement]:
        return list(self._entitlements.get(plan_version_id, []))

    async def find_by_code(self, code: str) -> PlanVersion | None:
        for plan in self._plans.values():
            if plan.code == code:
                return plan
        return None

    async def next_version_for_family(self, family: str) -> int:
        versions = [p.version for p in self._plans.values() if p.family == family]
        return max(versions, default=0) + 1

    async def create_draft(
        self, plan: PlanVersion, entitlements: list[PlanEntitlement]
    ) -> PlanVersion:
        self._plans[plan.id] = plan
        self._entitlements[plan.id] = list(entitlements)
        return plan

    async def activate(self, plan_version_id: str) -> PlanVersion:
        plan = self._plans[plan_version_id]
        activated = PlanVersion(
            id=plan.id,
            code=plan.code,
            family=plan.family,
            name=plan.name,
            version=plan.version,
            billing_interval=plan.billing_interval,
            currency=plan.currency,
            price_minor_units=plan.price_minor_units,
            state=PlanState.ACTIVE,
            effective_from=plan.effective_from,
            effective_to=plan.effective_to,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
        self._plans[plan_version_id] = activated
        return activated


class FakeSubscriptionRepo:
    def __init__(self, subs: dict[str, Subscription]) -> None:
        self._by_user: dict[str, Subscription] = dict(subs)
        self._by_provider: dict[str, Subscription] = {
            s.provider_subscription_id: s for s in subs.values() if s.provider_subscription_id
        }

    async def get_by_user_id(self, user_id: str) -> Subscription | None:
        return self._by_user.get(user_id)

    async def get_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> Subscription | None:
        return self._by_provider.get(provider_subscription_id)

    async def create(self, subscription: Subscription) -> Subscription:
        self._by_user[subscription.user_id] = subscription
        if subscription.provider_subscription_id:
            self._by_provider[subscription.provider_subscription_id] = subscription
        return subscription

    async def update(self, subscription: Subscription, expected_version: int) -> Subscription:
        current = self._by_user.get(subscription.user_id)
        if current is None or current.version != expected_version:
            from src.modules.billing.domain.errors import ConcurrencyError

            raise ConcurrencyError()
        updated = Subscription(
            id=subscription.id,
            user_id=subscription.user_id,
            plan_version_id=subscription.plan_version_id,
            provider=subscription.provider,
            provider_customer_id=subscription.provider_customer_id,
            provider_subscription_id=subscription.provider_subscription_id,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
            cancel_at_period_end=subscription.cancel_at_period_end,
            grace_period_ends_at=subscription.grace_period_ends_at,
            provider_state_updated_at=subscription.provider_state_updated_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            version=expected_version + 1,
        )
        self._by_user[updated.user_id] = updated
        if updated.provider_subscription_id:
            self._by_provider[updated.provider_subscription_id] = updated
        return updated


class FakeUsageRepo:
    def __init__(self) -> None:
        self._ledger: dict[str, UsageLedgerEntry] = {}
        self._ledger_by_op: dict[tuple[str, str, str], UsageLedgerEntry] = {}
        self._aggregates: dict[tuple[str, str, datetime, datetime], UsageAggregate] = {}

    async def get_aggregates_for_user(self, user_id: str) -> list[UsageAggregate]:
        return [a for k, a in self._aggregates.items() if k[0] == user_id]

    async def get_aggregate(
        self, user_id: str, metric: str, period_start: datetime, period_end: datetime
    ) -> UsageAggregate | None:
        return self._aggregates.get((user_id, metric, period_start, period_end))

    async def find_ledger_by_operation(
        self, user_id: str, metric: str, operation_id: str
    ) -> UsageLedgerEntry | None:
        return self._ledger_by_op.get((user_id, metric, operation_id))

    async def get_ledger_entry(self, entry_id: str, user_id: str) -> UsageLedgerEntry | None:
        entry = self._ledger.get(entry_id)
        if entry is None or entry.user_id != user_id:
            return None
        return entry

    async def reserve(
        self,
        *,
        user_id: str,
        metric: str,
        quantity: int,
        operation_id: str,
        period_start: datetime,
        period_end: datetime,
        entry_id: str,
    ) -> Reservation:
        entry = UsageLedgerEntry(
            id=entry_id,
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            period_start=period_start,
            period_end=period_end,
            operation_id=operation_id,
            state=UsageLedgerState.RESERVED,
            created_at=_NOW,
        )
        self._ledger[entry_id] = entry
        self._ledger_by_op[(user_id, metric, operation_id)] = entry
        key = (user_id, metric, period_start, period_end)
        agg = self._aggregates.get(key)
        if agg is None:
            self._aggregates[key] = UsageAggregate(
                user_id=user_id,
                metric=metric,
                quantity=quantity,
                period_start=period_start,
                period_end=period_end,
                updated_at=_NOW,
                version=1,
            )
        else:
            self._aggregates[key] = UsageAggregate(
                user_id=agg.user_id,
                metric=agg.metric,
                quantity=agg.quantity + quantity,
                period_start=agg.period_start,
                period_end=agg.period_end,
                updated_at=_NOW,
                version=agg.version + 1,
            )
        return Reservation(
            id=entry_id,
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            operation_id=operation_id,
        )

    async def re_reserve(self, entry_id: str, user_id: str, quantity: int) -> Reservation:
        entry = self._ledger[entry_id]
        if entry.user_id != user_id:
            raise KeyError(entry_id)
        released = UsageLedgerEntry(
            id=entry.id,
            user_id=entry.user_id,
            metric=entry.metric,
            quantity=quantity,
            period_start=entry.period_start,
            period_end=entry.period_end,
            operation_id=entry.operation_id,
            state=UsageLedgerState.RESERVED,
            created_at=entry.created_at,
        )
        self._ledger[entry_id] = released
        self._ledger_by_op[(entry.user_id, entry.metric, entry.operation_id)] = released
        key = (entry.user_id, entry.metric, entry.period_start, entry.period_end)
        agg = self._aggregates[key]
        delta = quantity
        self._aggregates[key] = UsageAggregate(
            user_id=agg.user_id,
            metric=agg.metric,
            quantity=agg.quantity + delta,
            period_start=agg.period_start,
            period_end=agg.period_end,
            updated_at=_NOW,
            version=agg.version + 1,
        )
        return Reservation(
            id=entry_id,
            user_id=entry.user_id,
            metric=entry.metric,
            quantity=quantity,
            operation_id=entry.operation_id,
        )

    async def consume(self, entry_id: str, user_id: str, actual_quantity: int) -> UsageLedgerEntry:
        entry = self._ledger[entry_id]
        delta = actual_quantity - entry.quantity
        entry = UsageLedgerEntry(
            id=entry.id,
            user_id=entry.user_id,
            metric=entry.metric,
            quantity=actual_quantity,
            period_start=entry.period_start,
            period_end=entry.period_end,
            operation_id=entry.operation_id,
            state=UsageLedgerState.CONSUMED,
            created_at=entry.created_at,
        )
        self._ledger[entry_id] = entry
        key = (entry.user_id, entry.metric, entry.period_start, entry.period_end)
        agg = self._aggregates[key]
        self._aggregates[key] = UsageAggregate(
            user_id=agg.user_id,
            metric=agg.metric,
            quantity=agg.quantity + delta,
            period_start=agg.period_start,
            period_end=agg.period_end,
            updated_at=_NOW,
            version=agg.version + 1,
        )
        return entry

    async def release(self, entry_id: str, user_id: str) -> UsageLedgerEntry:
        entry = self._ledger[entry_id]
        entry = UsageLedgerEntry(
            id=entry.id,
            user_id=entry.user_id,
            metric=entry.metric,
            quantity=entry.quantity,
            period_start=entry.period_start,
            period_end=entry.period_end,
            operation_id=entry.operation_id,
            state=UsageLedgerState.RELEASED,
            created_at=entry.created_at,
        )
        self._ledger[entry_id] = entry
        key = (entry.user_id, entry.metric, entry.period_start, entry.period_end)
        agg = self._aggregates[key]
        self._aggregates[key] = UsageAggregate(
            user_id=agg.user_id,
            metric=agg.metric,
            quantity=max(0, agg.quantity - entry.quantity),
            period_start=agg.period_start,
            period_end=agg.period_end,
            updated_at=_NOW,
            version=agg.version + 1,
        )
        return entry


class FakeWebhookRepo:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], BillingWebhookEvent] = {}

    async def get_by_provider_event(
        self, provider: str, provider_event_id: str
    ) -> BillingWebhookEvent | None:
        return self._events.get((provider, provider_event_id))

    async def claim(
        self,
        *,
        event_id: str,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload_hash: str,
        provider_occurred_at: datetime | None,
    ) -> BillingWebhookEvent:
        ev = BillingWebhookEvent(
            id=event_id,
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            received_at=_NOW,
            provider_occurred_at=provider_occurred_at,
            processed_at=None,
            processing_state=WebhookProcessingState.RECEIVED,
            payload_hash=payload_hash,
            failure_code=None,
        )
        self._events[(provider, provider_event_id)] = ev
        return ev

    async def mark_processed(self, event_id: str) -> BillingWebhookEvent:
        for key, ev in self._events.items():
            if ev.id == event_id:
                updated = BillingWebhookEvent(
                    id=ev.id,
                    provider=ev.provider,
                    provider_event_id=ev.provider_event_id,
                    event_type=ev.event_type,
                    received_at=ev.received_at,
                    provider_occurred_at=ev.provider_occurred_at,
                    processed_at=_NOW,
                    processing_state=WebhookProcessingState.PROCESSED,
                    payload_hash=ev.payload_hash,
                    failure_code=None,
                )
                self._events[key] = updated
                return updated
        raise RuntimeError("event not found")

    async def mark_ignored(
        self, event_id: str, failure_code: str | None = None
    ) -> BillingWebhookEvent:
        for key, ev in self._events.items():
            if ev.id == event_id:
                updated = BillingWebhookEvent(
                    id=ev.id,
                    provider=ev.provider,
                    provider_event_id=ev.provider_event_id,
                    event_type=ev.event_type,
                    received_at=ev.received_at,
                    provider_occurred_at=ev.provider_occurred_at,
                    processed_at=_NOW,
                    processing_state=WebhookProcessingState.IGNORED,
                    payload_hash=ev.payload_hash,
                    failure_code=failure_code,
                )
                self._events[key] = updated
                return updated
        raise RuntimeError("event not found")

    async def mark_failed(self, event_id: str, failure_code: str) -> BillingWebhookEvent:
        for key, ev in self._events.items():
            if ev.id == event_id:
                updated = BillingWebhookEvent(
                    id=ev.id,
                    provider=ev.provider,
                    provider_event_id=ev.provider_event_id,
                    event_type=ev.event_type,
                    received_at=ev.received_at,
                    provider_occurred_at=ev.provider_occurred_at,
                    processed_at=_NOW,
                    processing_state=WebhookProcessingState.FAILED,
                    payload_hash=ev.payload_hash,
                    failure_code=failure_code,
                )
                self._events[key] = updated
                return updated
        raise RuntimeError("event not found")


def _plan(plan_id: str = "plan_solo_v1") -> PlanVersion:
    return PlanVersion(
        id=plan_id,
        code="solo-v1",
        family="solo",
        name="Solo",
        version=1,
        billing_interval=BillingInterval.MONTHLY,
        currency="LKR",
        price_minor_units=499900,
        state=PlanState.ACTIVE,
        effective_from=_NOW,
        effective_to=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _solo_entitlements() -> list[PlanEntitlement]:
    return [
        PlanEntitlement("plan_solo_v1", "document_processing.enabled", None, True),
        PlanEntitlement("plan_solo_v1", "research.enabled", None, True),
        PlanEntitlement("plan_solo_v1", "drafting.enabled", None, True),
        PlanEntitlement("plan_solo_v1", "export.enabled", None, True),
        PlanEntitlement("plan_solo_v1", "active_matters.max", 25, True),
        PlanEntitlement("plan_solo_v1", "document_pages.monthly", 100, True),
    ]


def _subscription(
    user_id: str = "usr_a",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> Subscription:
    return Subscription(
        id="sub_a",
        user_id=user_id,
        plan_version_id="plan_solo_v1",
        provider="payhere",
        provider_customer_id="cust_a",
        provider_subscription_id="prov_sub_a",
        status=status,
        current_period_start=_NOW,
        current_period_end=_PERIOD_END,
        trial_ends_at=None,
        cancel_at_period_end=False,
        grace_period_ends_at=None,
        provider_state_updated_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
        version=1,
    )


def make_service(
    *,
    subs: dict[str, Subscription] | None = None,
    usage: FakeUsageRepo | None = None,
    clock: FakeClock | None = None,
    enforce_plan_limits: bool = True,
) -> BillingService:
    plan = _plan()
    entitlements = {"plan_solo_v1": _solo_entitlements()}
    sub_map = subs or {"usr_a": _subscription()}
    return BillingService(
        plan_repo=FakePlanRepo([plan], entitlements),
        subscription_repo=FakeSubscriptionRepo(sub_map),
        usage_repo=usage or FakeUsageRepo(),
        webhook_repo=FakeWebhookRepo(),
        billing_provider=StubBillingAdapter(),
        user_read_port=FakeUserReadPort(),
        platform_admin_port=DenyPlatformAdminPort(),
        audit_port=FakeAudit(),
        event_port=FakeEventPort(),
        clock=clock or FakeClock(),
        grace_period_days=14,
        enforce_plan_limits=enforce_plan_limits,
    )


def ctx(role: Role = Role.APPROVER, actor_id: str = "usr_a") -> RequestContext:
    return RequestContext(actor_id=actor_id, account_role=role, correlation_id="corr")


class TestStatusTransitions:
    def test_allowed_payment_failure_path(self):
        assert can_transition(SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)
        assert can_transition(SubscriptionStatus.PAST_DUE, SubscriptionStatus.GRACE_PERIOD)
        assert can_transition(SubscriptionStatus.GRACE_PERIOD, SubscriptionStatus.RESTRICTED)

    def test_expired_is_terminal(self):
        assert not can_transition(SubscriptionStatus.EXPIRED, SubscriptionStatus.ACTIVE)


class TestRequireFeature:
    @pytest.mark.asyncio
    async def test_unknown_feature_fail_closed(self):
        svc = make_service()
        decision = await svc.require_feature("usr_a", "not.a.real.feature")
        assert not decision.allowed
        assert decision.reason == "unknown_feature_key"

    @pytest.mark.asyncio
    async def test_restricted_denies_processing(self):
        svc = make_service(subs={"usr_a": _subscription(status=SubscriptionStatus.RESTRICTED)})
        decision = await svc.require_feature("usr_a", "document_processing.enabled")
        assert not decision.allowed
        assert decision.reason == "restricted_mode"


class TestPlanLimitsSwitchedOff:
    """ENFORCE_PLAN_LIMITS=false: everyone gets everything, whatever their plan."""

    @pytest.mark.asyncio
    async def test_enforcing_is_the_default_and_denies_an_account_with_no_plan(self):
        svc = make_service(subs={"usr_a": _subscription()})
        decision = await svc.require_feature("usr_nobody", "research.enabled")
        assert not decision.allowed
        assert decision.reason == "no_subscription"

    @pytest.mark.asyncio
    async def test_an_account_with_no_subscription_gets_every_feature(self):
        svc = make_service(enforce_plan_limits=False)
        for feature in (
            "research.enabled",
            "drafting.enabled",
            "export.enabled",
            "document_processing.enabled",
        ):
            decision = await svc.require_feature("usr_nobody", feature)
            assert decision.allowed and decision.limit_value is None
        assert (await svc.require_feature_or_raise("usr_nobody", "research.enabled")).allowed

    @pytest.mark.asyncio
    async def test_a_restricted_subscription_is_not_a_barrier(self):
        restricted = _subscription(status=SubscriptionStatus.RESTRICTED)
        svc = make_service(subs={"usr_a": restricted}, enforce_plan_limits=False)
        assert (await svc.require_feature("usr_a", "research.enabled")).allowed

    @pytest.mark.asyncio
    async def test_unknown_feature_keys_still_fail_closed(self):
        svc = make_service(enforce_plan_limits=False)
        decision = await svc.require_feature("usr_a", "not.a.real.feature")
        assert not decision.allowed
        assert decision.reason == "unknown_feature_key"

    @pytest.mark.asyncio
    async def test_no_quota_applies_and_an_unsubscribed_account_can_reserve(self):
        svc = make_service(enforce_plan_limits=False)
        reservation = await svc.reserve_usage(
            "usr_nobody", "document_pages.monthly", 10_000_000, "op-1"
        )
        assert reservation.id.startswith("usg_unmetered_")
        consumed = await svc.consume_usage("usr_nobody", reservation.id, 10_000_000)
        assert (consumed.metric, consumed.quantity) == ("document_pages.monthly", 0)
        released = await svc.release_usage("usr_nobody", reservation.id)
        assert released.quantity == 0

    @pytest.mark.asyncio
    async def test_enforcing_still_refuses_an_unsubscribed_reservation(self):
        svc = make_service(enforce_plan_limits=True)
        with pytest.raises(FeatureDeniedError):
            await svc.reserve_usage("usr_nobody", "document_pages.monthly", 1, "op-2")


class TestUsageIdempotency:
    @pytest.mark.asyncio
    async def test_reserve_retry_same_operation(self):
        svc = make_service()
        first = await svc.reserve_usage("usr_a", "document_pages.monthly", 10, "op-1")
        second = await svc.reserve_usage("usr_a", "document_pages.monthly", 10, "op-1")
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_consume_twice_is_stable(self):
        svc = make_service()
        res = await svc.reserve_usage("usr_a", "document_pages.monthly", 10, "op-2")
        u1 = await svc.consume_usage("usr_a", res.id, 8)
        u2 = await svc.consume_usage("usr_a", res.id, 8)
        assert u1.quantity == u2.quantity

    @pytest.mark.asyncio
    async def test_release_twice_is_stable(self):
        svc = make_service()
        res = await svc.reserve_usage("usr_a", "document_pages.monthly", 5, "op-3")
        u1 = await svc.release_usage("usr_a", res.id)
        u2 = await svc.release_usage("usr_a", res.id)
        assert u1.quantity == u2.quantity


class TestPlanCatalogue:
    def test_unknown_metric_not_in_catalogue(self):
        assert not is_known_feature_key("bogus.feature")

    @pytest.mark.asyncio
    async def test_list_plans_only_active(self):
        retired = PlanVersion(
            id="plan_old",
            code="solo-v0",
            family="solo",
            name="Old",
            version=0,
            billing_interval=BillingInterval.MONTHLY,
            currency="LKR",
            price_minor_units=1,
            state=PlanState.RETIRED,
            effective_from=_NOW,
            effective_to=None,
            created_at=_NOW,
            updated_at=_NOW,
        )
        plan = _plan()
        svc = BillingService(
            plan_repo=FakePlanRepo([plan, retired], {"plan_solo_v1": _solo_entitlements()}),
            subscription_repo=FakeSubscriptionRepo({"usr_a": _subscription()}),
            usage_repo=FakeUsageRepo(),
            webhook_repo=FakeWebhookRepo(),
            billing_provider=StubBillingAdapter(),
            user_read_port=FakeUserReadPort(),
            platform_admin_port=DenyPlatformAdminPort(),
            audit_port=FakeAudit(),
            event_port=FakeEventPort(),
            clock=FakeClock(),
            grace_period_days=14,
        )
        rows = await svc.list_plans(ctx())
        assert len(rows) == 1
        assert rows[0][0].id == "plan_solo_v1"


class TestWebhookHandling:
    @pytest.mark.asyncio
    async def test_duplicate_webhook_returns_success(self):
        svc = make_service()
        payload = {
            "event_id": "evt_dup",
            "event_type": "payment.failed",
            "status": "past_due",
            "subscription_id": "prov_sub_a",
            "customer_id": "cust_a",
        }
        body = {**payload}
        canonical = json.dumps(dict(body), sort_keys=True, separators=(",", ":"))
        body["checksum"] = hashlib.sha256(canonical.encode()).hexdigest()
        raw = RawWebhook(
            headers={},
            body=json.dumps(body).encode(),
            provider="payhere",
        )
        first = await svc.handle_webhook("payhere", raw)
        second = await svc.handle_webhook("payhere", raw)
        assert first.processing_state == WebhookProcessingState.PROCESSED
        assert second.duplicate is True

    @pytest.mark.asyncio
    async def test_quota_exceeded(self):
        svc = make_service()
        await svc.reserve_usage("usr_a", "document_pages.monthly", 90, "op-q1")
        with pytest.raises(QuotaExceededError):
            await svc.reserve_usage("usr_a", "document_pages.monthly", 20, "op-q2")


class TestBillingManage:
    @pytest.mark.asyncio
    async def test_reviewer_denied_list_plans(self):
        svc = make_service()
        with pytest.raises(CapabilityDeniedError):
            await svc.list_plans(ctx(role=Role.REVIEWER))

"""billing_service — plans, subscriptions, entitlements, usage, webhooks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog

from src.modules.auth.domain.errors import CapabilityDeniedError
from src.modules.auth.domain.policies import is_capability_granted
from src.modules.billing.domain.errors import (
    BillingNotFoundError,
    ConcurrencyError,
    FeatureDeniedError,
    InvalidWebhookError,
    QuotaExceededError,
)
from src.modules.billing.domain.models import (
    EntitlementDecision,
    PlanState,
    Reservation,
    Subscription,
    SubscriptionStatus,
    UsageLedgerState,
    UsageRead,
    WebhookProcessingState,
)
from src.modules.billing.domain.policies import (
    can_transition,
    is_known_feature_key,
    should_enter_grace,
    should_enter_restricted,
    subscription_allows_feature,
)
from src.modules.billing.ports import (
    AuditEventInput,
    AuditPort,
    BillingProviderPort,
    BillingWebhookEventRepository,
    CheckoutCommand,
    ClockPort,
    EventPort,
    PlanRepository,
    RawWebhook,
    SubscriptionRepository,
    UsageRepository,
    WebhookReceipt,
)
from src.platform.config import get_settings
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

_BILLING_MANAGE = "billing.manage"


class BillingService:
    def __init__(
        self,
        *,
        plan_repo: PlanRepository,
        subscription_repo: SubscriptionRepository,
        usage_repo: UsageRepository,
        webhook_repo: BillingWebhookEventRepository,
        billing_provider: BillingProviderPort,
        audit_port: AuditPort,
        event_port: EventPort,
        clock: ClockPort,
    ) -> None:
        self._plans = plan_repo
        self._subscriptions = subscription_repo
        self._usage = usage_repo
        self._webhooks = webhook_repo
        self._provider = billing_provider
        self._audit = audit_port
        self._events = event_port
        self._clock = clock

    def _require_billing_manage(self, ctx: RequestContext) -> None:
        if not is_capability_granted(ctx.account_role, _BILLING_MANAGE):
            raise CapabilityDeniedError(
                f"Capability '{_BILLING_MANAGE}' is not granted to role '{ctx.account_role}'.",
                capability=_BILLING_MANAGE,
            )

    async def list_plans(self, ctx: RequestContext) -> list[dict[str, Any]]:
        self._require_billing_manage(ctx)
        plans = await self._plans.list_active()
        result: list[dict[str, Any]] = []
        for plan in plans:
            entitlements = await self._plans.get_entitlements(plan.id)
            result.append(
                {
                    "plan": plan,
                    "entitlements": entitlements,
                }
            )
        return result

    async def get_subscription(self, ctx: RequestContext) -> Subscription:
        self._require_billing_manage(ctx)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None:
            raise BillingNotFoundError("No subscription found for this account.")
        return sub

    async def get_usage(self, ctx: RequestContext) -> list[UsageRead]:
        self._require_billing_manage(ctx)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None:
            return []
        aggregates = await self._usage.get_aggregates_for_user(ctx.actor_id)
        entitlements = await self._plans.get_entitlements(sub.plan_version_id)
        limit_by_metric: dict[str, int | None] = {}
        for ent in entitlements:
            if ent.feature_key.endswith(".monthly") or ent.feature_key.endswith(".max"):
                limit_by_metric[ent.feature_key] = ent.limit_value

        reads: list[UsageRead] = []
        for agg in aggregates:
            reads.append(
                UsageRead(
                    metric=agg.metric,
                    quantity=agg.quantity,
                    period_start=agg.period_start,
                    period_end=agg.period_end,
                    limit_value=limit_by_metric.get(agg.metric),
                )
            )
        return reads

    async def create_checkout(
        self, ctx: RequestContext, plan_version_id: str, return_path: str
    ) -> dict[str, str]:
        self._require_billing_manage(ctx)
        plan = await self._plans.get(plan_version_id)
        if plan is None or plan.state != PlanState.ACTIVE:
            raise BillingNotFoundError("Plan version is not available for checkout.")

        checkout = await self._provider.create_checkout(
            CheckoutCommand(
                user_id=ctx.actor_id,
                plan_version_id=plan_version_id,
                return_path=return_path,
            )
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.checkout.created",
                target_type="plan_version",
                target_id=plan_version_id,
                actor=ctx.actor_id,
                correlation_id=ctx.correlation_id,
            )
        )
        return {"checkout_url": checkout.checkout_url, "session_id": checkout.provider_session_id}

    async def create_customer_portal(self, ctx: RequestContext) -> dict[str, str]:
        self._require_billing_manage(ctx)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None or not sub.provider_customer_id:
            raise BillingNotFoundError("No provider customer for this account.")
        portal = await self._provider.create_customer_portal(sub.provider_customer_id)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.portal.opened",
                target_type="subscription",
                target_id=sub.id,
                actor=ctx.actor_id,
                correlation_id=ctx.correlation_id,
            )
        )
        return {"portal_url": portal.portal_url}

    async def cancel_subscription(self, ctx: RequestContext) -> Subscription:
        self._require_billing_manage(ctx)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None:
            raise BillingNotFoundError("No subscription found.")
        if sub.provider_subscription_id:
            await self._provider.cancel_subscription(sub.provider_subscription_id)
        updated = Subscription(
            id=sub.id,
            user_id=sub.user_id,
            plan_version_id=sub.plan_version_id,
            provider=sub.provider,
            provider_customer_id=sub.provider_customer_id,
            provider_subscription_id=sub.provider_subscription_id,
            status=sub.status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            trial_ends_at=sub.trial_ends_at,
            cancel_at_period_end=True,
            grace_period_ends_at=sub.grace_period_ends_at,
            provider_state_updated_at=self._clock.now(),
            created_at=sub.created_at,
            updated_at=self._clock.now(),
            version=sub.version,
        )
        saved = await self._subscriptions.update(updated, sub.version)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.subscription.cancel_requested",
                target_type="subscription",
                target_id=sub.id,
                actor=ctx.actor_id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.emit(
            "billing.subscription-cancelled",
            {"subscriptionId": sub.id, "effectiveAt": sub.current_period_end.isoformat()},
        )
        return saved

    async def reactivate_subscription(self, ctx: RequestContext) -> Subscription:
        self._require_billing_manage(ctx)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None:
            raise BillingNotFoundError("No subscription found.")
        if sub.provider_subscription_id:
            await self._provider.reactivate_subscription(sub.provider_subscription_id)
        new_status = (
            SubscriptionStatus.ACTIVE
            if sub.status != SubscriptionStatus.TRIALING
            else SubscriptionStatus.TRIALING
        )
        updated = Subscription(
            id=sub.id,
            user_id=sub.user_id,
            plan_version_id=sub.plan_version_id,
            provider=sub.provider,
            provider_customer_id=sub.provider_customer_id,
            provider_subscription_id=sub.provider_subscription_id,
            status=new_status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            trial_ends_at=sub.trial_ends_at,
            cancel_at_period_end=False,
            grace_period_ends_at=None,
            provider_state_updated_at=self._clock.now(),
            created_at=sub.created_at,
            updated_at=self._clock.now(),
            version=sub.version,
        )
        saved = await self._subscriptions.update(updated, sub.version)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.subscription.reactivated",
                target_type="subscription",
                target_id=sub.id,
                actor=ctx.actor_id,
                before_ref=sub.status.value,
                after_ref=new_status.value,
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    async def require_feature(self, user_id: str, feature_key: str) -> EntitlementDecision:
        if not is_known_feature_key(feature_key):
            return EntitlementDecision(
                allowed=False,
                feature_key=feature_key,
                reason="unknown_feature_key",
            )

        sub = await self._subscriptions.get_by_user_id(user_id)
        if sub is None:
            return EntitlementDecision(
                allowed=False,
                feature_key=feature_key,
                reason="no_subscription",
            )

        if not subscription_allows_feature(sub.status, feature_key):
            return EntitlementDecision(
                allowed=False,
                feature_key=feature_key,
                reason="restricted_mode",
            )

        entitlements = await self._plans.get_entitlements(sub.plan_version_id)
        ent = next((e for e in entitlements if e.feature_key == feature_key), None)
        if ent is None:
            return EntitlementDecision(
                allowed=False,
                feature_key=feature_key,
                reason="not_in_plan",
            )
        if not ent.enabled:
            return EntitlementDecision(
                allowed=False,
                feature_key=feature_key,
                reason="feature_disabled",
            )
        return EntitlementDecision(
            allowed=True,
            feature_key=feature_key,
            limit_value=ent.limit_value,
        )

    async def require_feature_or_raise(self, user_id: str, feature_key: str) -> EntitlementDecision:
        decision = await self.require_feature(user_id, feature_key)
        if not decision.allowed:
            raise FeatureDeniedError(
                decision.reason or "feature_denied",
                feature_key=feature_key,
            )
        return decision

    async def reserve_usage(
        self,
        user_id: str,
        metric: str,
        quantity: int,
        operation_id: str,
    ) -> Reservation:
        if quantity <= 0:
            raise FeatureDeniedError("Quantity must be positive.", feature_key=metric)

        if not is_known_feature_key(metric):
            raise FeatureDeniedError("Unknown usage metric.", feature_key=metric)

        existing = await self._usage.find_ledger_by_operation(user_id, metric, operation_id)
        if existing is not None:
            if existing.state == UsageLedgerState.RESERVED:
                return Reservation(
                    id=existing.id,
                    user_id=existing.user_id,
                    metric=existing.metric,
                    quantity=existing.quantity,
                    operation_id=existing.operation_id,
                )
            if existing.state == UsageLedgerState.CONSUMED:
                return Reservation(
                    id=existing.id,
                    user_id=existing.user_id,
                    metric=existing.metric,
                    quantity=existing.quantity,
                    operation_id=existing.operation_id,
                )

        sub = await self._subscriptions.get_by_user_id(user_id)
        if sub is None:
            raise FeatureDeniedError("no_subscription", feature_key=metric)

        decision = await self.require_feature(user_id, metric)
        if not decision.allowed:
            raise FeatureDeniedError(decision.reason or "feature_denied", feature_key=metric)

        period_start = sub.current_period_start
        period_end = sub.current_period_end
        agg = await self._usage.get_aggregate(user_id, metric, period_start, period_end)
        current_qty = agg.quantity if agg else 0
        if decision.limit_value is not None and current_qty + quantity > decision.limit_value:
            raise QuotaExceededError(
                "Quota exceeded for metric.",
                metric=metric,
                limit=decision.limit_value,
            )

        entry_id = f"usg_{uuid.uuid4().hex}"
        return await self._usage.reserve(
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            operation_id=operation_id,
            period_start=period_start,
            period_end=period_end,
            entry_id=entry_id,
        )

    async def consume_usage(self, reservation_id: str, actual_quantity: int) -> UsageRead:
        entry = await self._usage.get_ledger_entry(reservation_id)
        if entry is None:
            raise BillingNotFoundError("Reservation not found.")
        if entry.state == UsageLedgerState.CONSUMED:
            agg = await self._usage.get_aggregate(
                entry.user_id, entry.metric, entry.period_start, entry.period_end
            )
            qty = agg.quantity if agg else entry.quantity
            return UsageRead(
                metric=entry.metric,
                quantity=qty,
                period_start=entry.period_start,
                period_end=entry.period_end,
            )
        if entry.state == UsageLedgerState.RELEASED:
            raise FeatureDeniedError("Reservation was released.", feature_key=entry.metric)

        updated = await self._usage.consume(reservation_id, actual_quantity)
        agg = await self._usage.get_aggregate(
            updated.user_id, updated.metric, updated.period_start, updated.period_end
        )
        return UsageRead(
            metric=updated.metric,
            quantity=agg.quantity if agg else actual_quantity,
            period_start=updated.period_start,
            period_end=updated.period_end,
        )

    async def release_usage(self, reservation_id: str) -> UsageRead:
        entry = await self._usage.get_ledger_entry(reservation_id)
        if entry is None:
            raise BillingNotFoundError("Reservation not found.")
        if entry.state == UsageLedgerState.RELEASED:
            agg = await self._usage.get_aggregate(
                entry.user_id, entry.metric, entry.period_start, entry.period_end
            )
            return UsageRead(
                metric=entry.metric,
                quantity=agg.quantity if agg else 0,
                period_start=entry.period_start,
                period_end=entry.period_end,
            )
        if entry.state == UsageLedgerState.CONSUMED:
            raise FeatureDeniedError("Cannot release consumed usage.", feature_key=entry.metric)

        updated = await self._usage.release(reservation_id)
        agg = await self._usage.get_aggregate(
            updated.user_id, updated.metric, updated.period_start, updated.period_end
        )
        return UsageRead(
            metric=updated.metric,
            quantity=agg.quantity if agg else 0,
            period_start=updated.period_start,
            period_end=updated.period_end,
        )

    async def handle_webhook(self, provider: str, raw_request: RawWebhook) -> WebhookReceipt:
        try:
            event = await self._provider.verify_webhook(raw_request)
        except InvalidWebhookError:
            raise
        except Exception:
            raise InvalidWebhookError("Webhook verification failed.")

        existing = await self._webhooks.get_by_provider_event(provider, event.provider_event_id)
        if existing and existing.processing_state == WebhookProcessingState.PROCESSED:
            return WebhookReceipt(
                provider_event_id=event.provider_event_id,
                processing_state=WebhookProcessingState.PROCESSED,
                duplicate=True,
            )

        event_id = existing.id if existing else f"bwe_{uuid.uuid4().hex}"
        if existing is None:
            claimed = await self._webhooks.claim(
                event_id=event_id,
                provider=provider,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                payload_hash=event.payload_hash,
                provider_occurred_at=event.occurred_at,
            )
        else:
            claimed = existing

        sub: Subscription | None = None
        if event.provider_subscription_id:
            sub = await self._subscriptions.get_by_provider_subscription_id(
                event.provider_subscription_id
            )

        if sub is None:
            await self._webhooks.mark_ignored(claimed.id, failure_code="subscription_not_mapped")
            return WebhookReceipt(
                provider_event_id=event.provider_event_id,
                processing_state=WebhookProcessingState.IGNORED,
            )

        new_status = self._map_provider_status(event, sub.status)
        if new_status is None:
            await self._webhooks.mark_ignored(claimed.id, failure_code="unhandled_event")
            return WebhookReceipt(
                provider_event_id=event.provider_event_id,
                processing_state=WebhookProcessingState.IGNORED,
            )

        if not can_transition(sub.status, new_status):
            await self._webhooks.mark_ignored(claimed.id, failure_code="stale_or_invalid_transition")
            return WebhookReceipt(
                provider_event_id=event.provider_event_id,
                processing_state=WebhookProcessingState.IGNORED,
            )

        grace_ends: datetime | None = sub.grace_period_ends_at
        settings = get_settings()
        grace_days = settings.billing_grace_period_days
        if new_status == SubscriptionStatus.GRACE_PERIOD and should_enter_grace(sub.status):
            grace_ends = self._clock.now() + timedelta(days=grace_days)
        if new_status == SubscriptionStatus.RESTRICTED and should_enter_restricted(sub.status):
            grace_ends = None

        updated = Subscription(
            id=sub.id,
            user_id=sub.user_id,
            plan_version_id=sub.plan_version_id,
            provider=sub.provider,
            provider_customer_id=event.provider_customer_id or sub.provider_customer_id,
            provider_subscription_id=sub.provider_subscription_id,
            status=new_status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            trial_ends_at=sub.trial_ends_at,
            cancel_at_period_end=sub.cancel_at_period_end,
            grace_period_ends_at=grace_ends,
            provider_state_updated_at=event.occurred_at or self._clock.now(),
            created_at=sub.created_at,
            updated_at=self._clock.now(),
            version=sub.version,
        )
        try:
            saved = await self._subscriptions.update(updated, sub.version)
        except ConcurrencyError:
            await self._webhooks.mark_failed(claimed.id, "concurrency_conflict")
            raise

        await self._webhooks.mark_processed(claimed.id)
        await self._audit.record(
            AuditEventInput(
                user_id=sub.user_id,
                action="billing.subscription.provider_update",
                target_type="subscription",
                target_id=sub.id,
                before_ref=sub.status.value,
                after_ref=saved.status.value,
                correlation_id=event.provider_event_id,
            )
        )
        if new_status == SubscriptionStatus.PAST_DUE:
            await self._events.emit(
                "billing.payment-failed",
                {"subscriptionId": sub.id, "failureCode": event.event_type},
            )
        if new_status == SubscriptionStatus.RESTRICTED:
            await self._events.emit(
                "billing.subscription-restricted",
                {"subscriptionId": sub.id, "restrictedAt": self._clock.now().isoformat()},
            )

        return WebhookReceipt(
            provider_event_id=event.provider_event_id,
            processing_state=WebhookProcessingState.PROCESSED,
        )

    def _map_provider_status(
        self, event: object, current: SubscriptionStatus
    ) -> SubscriptionStatus | None:
        from src.modules.billing.ports import ProviderEvent

        pe = event
        if not isinstance(pe, ProviderEvent):
            return None
        normalized = pe.normalized_status or pe.event_type
        mapping = {
            "active": SubscriptionStatus.ACTIVE,
            "subscription.activated": SubscriptionStatus.ACTIVE,
            "trialing": SubscriptionStatus.TRIALING,
            "past_due": SubscriptionStatus.PAST_DUE,
            "payment.failed": SubscriptionStatus.PAST_DUE,
            "grace_period": SubscriptionStatus.GRACE_PERIOD,
            "restricted": SubscriptionStatus.RESTRICTED,
            "cancelled": SubscriptionStatus.CANCELLED,
            "expired": SubscriptionStatus.EXPIRED,
        }
        if normalized in mapping:
            return mapping[normalized]
        if pe.event_type in mapping:
            return mapping[pe.event_type]
        _ = current
        return None

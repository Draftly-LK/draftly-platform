"""billing_service — plans, subscriptions, entitlements, usage, webhooks.

Every customer-owned read and command is scoped to ``ctx.actor_id``; a user id
in a request body is never trusted (billing-service.md §3). Every mutation
records exactly one audit event and publishes through the outbox in the same
unit of work as the state change.
"""

from __future__ import annotations

import uuid
from dataclasses import replace as dataclass_replace
from datetime import datetime, timedelta

import structlog

from src.modules.auth.domain.errors import CapabilityDeniedError
from src.modules.auth.domain.policies import is_capability_granted
from src.modules.billing.domain.errors import (
    BillingNotFoundError,
    ConcurrencyError,
    FeatureDeniedError,
    InvalidPlanInputError,
    InvalidReturnPathError,
    InvalidWebhookError,
    PlanImmutableError,
    QuotaExceededError,
    UserAccountNotBillableError,
)
from src.modules.billing.domain.models import (
    EntitlementDecision,
    PlanEntitlement,
    PlanState,
    PlanVersion,
    PlanVersionDraft,
    Reservation,
    Subscription,
    SubscriptionStatus,
    UsageLedgerEntry,
    UsageLedgerState,
    UsageRead,
    WebhookProcessingState,
)
from src.modules.billing.domain.policies import (
    EVENT_PAYMENT_FAILED,
    EVENT_PLAN_CHANGED,
    EVENT_SUBSCRIPTION_CANCELLED,
    EVENT_SUBSCRIPTION_RESTRICTED,
    can_transition,
    is_known_feature_key,
    is_plan_mutable,
    is_safe_return_path,
    is_stale_provider_event,
    is_valid_money,
    restricted_mode_blocks,
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
    PlatformAdminPort,
    ProviderEvent,
    RawWebhook,
    SubscriptionRepository,
    UsageRepository,
    UserReadPort,
    WebhookReceipt,
)
from src.platform.errors import ConflictError
from src.platform.messaging.events import EventEnvelope
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

_BILLING_MANAGE = "billing.manage"
_PLATFORM_ADMINISTER = "platform.administer"

_PROVIDER_STATUS_MAP: dict[str, SubscriptionStatus] = {
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


class BillingService:
    def __init__(
        self,
        *,
        plan_repo: PlanRepository,
        subscription_repo: SubscriptionRepository,
        usage_repo: UsageRepository,
        webhook_repo: BillingWebhookEventRepository,
        billing_provider: BillingProviderPort,
        user_read_port: UserReadPort,
        platform_admin_port: PlatformAdminPort,
        audit_port: AuditPort,
        event_port: EventPort,
        clock: ClockPort,
        grace_period_days: int,
    ) -> None:
        self._plans = plan_repo
        self._subscriptions = subscription_repo
        self._usage = usage_repo
        self._webhooks = webhook_repo
        self._provider = billing_provider
        self._users = user_read_port
        self._platform_admins = platform_admin_port
        self._audit = audit_port
        self._events = event_port
        self._clock = clock
        self._grace_period_days = grace_period_days

    # ── gates ────────────────────────────────────────────────────────────────

    def _require_billing_manage(self, ctx: RequestContext) -> None:
        if not is_capability_granted(ctx.account_role, _BILLING_MANAGE):
            raise CapabilityDeniedError(
                f"Capability '{_BILLING_MANAGE}' is not granted to role '{ctx.account_role}'.",
                capability=_BILLING_MANAGE,
            )

    async def _require_platform_administer(self, ctx: RequestContext) -> None:
        """Plan administration is Draftly staff, not an account administrator.

        No account role grants this capability, so the only source is the
        platform grant, re-read per request (security-model.md §3.4).
        """
        if not await self._platform_admins.is_platform_admin(ctx.actor_id):
            raise CapabilityDeniedError(
                f"Capability '{_PLATFORM_ADMINISTER}' is not granted to this actor.",
                capability=_PLATFORM_ADMINISTER,
            )

    async def _require_billable_account(self, user_id: str) -> None:
        account = await self._users.get_billing_user(user_id)
        if account is None or not account.is_active:
            raise UserAccountNotBillableError()

    # ── reads ────────────────────────────────────────────────────────────────

    async def list_plans(
        self, ctx: RequestContext
    ) -> list[tuple[PlanVersion, list[PlanEntitlement]]]:
        self._require_billing_manage(ctx)
        plans = sorted(await self._plans.list_active(), key=lambda p: p.id)
        return [(plan, await self._plans.get_entitlements(plan.id)) for plan in plans]

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
        aggregates = sorted(
            await self._usage.get_aggregates_for_user(ctx.actor_id),
            key=lambda a: a.metric,
        )
        entitlements = await self._plans.get_entitlements(sub.plan_version_id)
        limit_by_metric = {e.feature_key: e.limit_value for e in entitlements}
        return [
            UsageRead(
                metric=agg.metric,
                quantity=agg.quantity,
                period_start=agg.period_start,
                period_end=agg.period_end,
                limit_value=limit_by_metric.get(agg.metric),
            )
            for agg in aggregates
        ]

    # ── customer commands ────────────────────────────────────────────────────

    async def create_checkout(
        self, ctx: RequestContext, plan_version_id: str, return_path: str
    ) -> dict[str, str]:
        self._require_billing_manage(ctx)
        await self._require_billable_account(ctx.actor_id)

        if not is_safe_return_path(return_path):
            raise InvalidReturnPathError()

        plan = await self._plans.get(plan_version_id)
        if plan is None or plan.state != PlanState.ACTIVE:
            raise BillingNotFoundError("Plan version is not available for checkout.")

        existing = await self._subscriptions.get_by_user_id(ctx.actor_id)
        checkout = await self._provider.create_checkout(
            CheckoutCommand(
                user_id=ctx.actor_id,
                plan_version_id=plan_version_id,
                return_path=return_path,
                currency=plan.currency,
                price_minor_units=plan.price_minor_units,
                provider_customer_id=existing.provider_customer_id if existing else None,
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
        log.info(
            "billing.checkout.created",
            plan_version_id=plan_version_id,
            correlation_id=ctx.correlation_id,
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

    async def cancel_subscription(self, ctx: RequestContext, expected_version: int) -> Subscription:
        self._require_billing_manage(ctx)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None:
            raise BillingNotFoundError("No subscription found.")
        if sub.provider_subscription_id:
            await self._provider.cancel_subscription(sub.provider_subscription_id)

        now = self._clock.now()
        saved = await self._subscriptions.update(
            dataclass_replace(
                sub,
                cancel_at_period_end=True,
                provider_state_updated_at=now,
                updated_at=now,
            ),
            expected_version,
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.subscription.cancel_requested",
                target_type="subscription",
                target_id=sub.id,
                actor=ctx.actor_id,
                before_ref=str(sub.version),
                after_ref=str(saved.version),
                correlation_id=ctx.correlation_id,
            )
        )
        await self._emit(
            EVENT_SUBSCRIPTION_CANCELLED,
            subscription=saved,
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
            data={
                "subscriptionId": saved.id,
                "effectiveAt": saved.current_period_end.isoformat(),
            },
        )
        return saved

    async def reactivate_subscription(
        self, ctx: RequestContext, expected_version: int
    ) -> Subscription:
        self._require_billing_manage(ctx)
        await self._require_billable_account(ctx.actor_id)
        sub = await self._subscriptions.get_by_user_id(ctx.actor_id)
        if sub is None:
            raise BillingNotFoundError("No subscription found.")
        if sub.provider_subscription_id:
            await self._provider.reactivate_subscription(sub.provider_subscription_id)

        new_status = (
            SubscriptionStatus.TRIALING
            if sub.status == SubscriptionStatus.TRIALING
            else SubscriptionStatus.ACTIVE
        )
        now = self._clock.now()
        saved = await self._subscriptions.update(
            dataclass_replace(
                sub,
                status=new_status,
                cancel_at_period_end=False,
                grace_period_ends_at=None,
                provider_state_updated_at=now,
                updated_at=now,
            ),
            expected_version,
        )
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.subscription.reactivated",
                target_type="subscription",
                target_id=sub.id,
                actor=ctx.actor_id,
                before_ref=sub.status.value,
                after_ref=saved.status.value,
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    # ── admin commands (platform.administer) ─────────────────────────────────

    async def create_plan_version(
        self, ctx: RequestContext, draft: PlanVersionDraft
    ) -> tuple[PlanVersion, list[PlanEntitlement]]:
        """Draft a new immutable plan version. Prices are data, supplied here."""
        await self._require_platform_administer(ctx)

        if not is_valid_money(draft.currency, draft.price_minor_units):
            raise InvalidPlanInputError(
                "Plan price must be a non-negative integer of minor units with an ISO currency."
            )
        unknown = [
            e.feature_key for e in draft.entitlements if not is_known_feature_key(e.feature_key)
        ]
        if unknown:
            raise FeatureDeniedError("Unknown entitlement key.", featureKeys=sorted(unknown))
        if await self._plans.find_by_code(draft.code) is not None:
            raise ConflictError(
                "A plan version with this code already exists; publish a new code instead."
            )

        now = self._clock.now()
        plan_id = f"plan_{uuid.uuid4().hex[:16]}"
        version = await self._plans.next_version_for_family(draft.family)
        plan = PlanVersion(
            id=plan_id,
            code=draft.code,
            family=draft.family,
            name=draft.name,
            version=version,
            billing_interval=draft.billing_interval,
            currency=draft.currency,
            price_minor_units=draft.price_minor_units,
            state=PlanState.DRAFT,
            effective_from=now,
            effective_to=None,
            created_at=now,
            updated_at=now,
        )
        entitlements = [
            PlanEntitlement(
                plan_version_id=plan_id,
                feature_key=e.feature_key,
                limit_value=e.limit_value,
                enabled=e.enabled,
            )
            for e in draft.entitlements
        ]
        created = await self._plans.create_draft(plan, entitlements)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.plan_version.drafted",
                target_type="plan_version",
                target_id=created.id,
                actor=ctx.actor_id,
                after_ref=PlanState.DRAFT.value,
                correlation_id=ctx.correlation_id,
            )
        )
        return created, entitlements

    async def list_entitlements_for_admin(
        self, ctx: RequestContext, plan_version_id: str
    ) -> list[PlanEntitlement]:
        """Load entitlements for a plan version after a platform-admin mutation."""
        await self._require_platform_administer(ctx)
        plan = await self._plans.get(plan_version_id)
        if plan is None:
            raise BillingNotFoundError("Plan version not found.")
        return await self._plans.get_entitlements(plan_version_id)

    async def activate_plan_version(self, ctx: RequestContext, plan_version_id: str) -> PlanVersion:
        """Publish a draft plan version. Published versions are then immutable."""
        await self._require_platform_administer(ctx)
        plan = await self._plans.get(plan_version_id)
        if plan is None:
            raise BillingNotFoundError("Plan version not found.")
        if not is_plan_mutable(plan.state):
            raise PlanImmutableError()

        activated = await self._plans.activate(plan_version_id)
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="billing.plan_version.activated",
                target_type="plan_version",
                target_id=plan_version_id,
                actor=ctx.actor_id,
                before_ref=plan.state.value,
                after_ref=activated.state.value,
                correlation_id=ctx.correlation_id,
            )
        )
        return activated

    async def grant_trial(
        self,
        ctx: RequestContext,
        *,
        user_id: str,
        plan_version_id: str,
        trial_days: int,
    ) -> Subscription:
        """Provision a trial subscription for an existing, active account."""
        await self._require_platform_administer(ctx)
        if trial_days <= 0:
            raise InvalidPlanInputError("Trial length must be a positive number of days.")
        await self._require_billable_account(user_id)

        plan = await self._plans.get(plan_version_id)
        if plan is None or plan.state != PlanState.ACTIVE:
            raise BillingNotFoundError("Plan version is not available.")
        if await self._subscriptions.get_by_user_id(user_id) is not None:
            raise ConflictError("This account already has a subscription.")

        now = self._clock.now()
        trial_end = now + timedelta(days=trial_days)
        subscription = Subscription(
            id=f"sub_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            plan_version_id=plan_version_id,
            provider="internal",
            provider_customer_id=None,
            provider_subscription_id=None,
            status=SubscriptionStatus.TRIALING,
            current_period_start=now,
            current_period_end=trial_end,
            trial_ends_at=trial_end,
            cancel_at_period_end=False,
            grace_period_ends_at=None,
            provider_state_updated_at=now,
            created_at=now,
            updated_at=now,
            version=1,
        )
        created = await self._subscriptions.create(subscription)
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                action="billing.subscription.trial_granted",
                target_type="subscription",
                target_id=created.id,
                actor=ctx.actor_id,
                after_ref=SubscriptionStatus.TRIALING.value,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._emit(
            EVENT_PLAN_CHANGED,
            subscription=created,
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
            data={
                "subscriptionId": created.id,
                "beforePlanVersionId": None,
                "afterPlanVersionId": plan_version_id,
            },
        )
        return created

    # ── entitlement and quota gates ──────────────────────────────────────────

    async def require_feature(self, user_id: str, feature_key: str) -> EntitlementDecision:
        if not is_known_feature_key(feature_key):
            return EntitlementDecision(
                allowed=False, feature_key=feature_key, reason="unknown_feature_key"
            )

        sub = await self._subscriptions.get_by_user_id(user_id)
        if sub is None:
            return EntitlementDecision(
                allowed=False, feature_key=feature_key, reason="no_subscription"
            )
        if not subscription_allows_feature(sub.status, feature_key):
            return EntitlementDecision(
                allowed=False, feature_key=feature_key, reason="restricted_mode"
            )

        entitlements = await self._plans.get_entitlements(sub.plan_version_id)
        ent = next((e for e in entitlements if e.feature_key == feature_key), None)
        if ent is None:
            return EntitlementDecision(allowed=False, feature_key=feature_key, reason="not_in_plan")
        if not ent.enabled:
            return EntitlementDecision(
                allowed=False, feature_key=feature_key, reason="feature_disabled"
            )
        return EntitlementDecision(
            allowed=True, feature_key=feature_key, limit_value=ent.limit_value
        )

    async def require_feature_or_raise(self, user_id: str, feature_key: str) -> EntitlementDecision:
        decision = await self.require_feature(user_id, feature_key)
        if not decision.allowed:
            raise FeatureDeniedError(decision.reason or "feature_denied", feature_key=feature_key)
        return decision

    async def reserve_usage(
        self, user_id: str, metric: str, quantity: int, operation_id: str
    ) -> Reservation:
        """Reserve quota, idempotently on ``operation_id``.

        A retry of the same operation returns the existing reservation rather
        than charging twice. A previously released reservation is re-reserved on
        the same ledger row, so a retry after a terminal failure is still safe.
        """
        if quantity <= 0:
            raise FeatureDeniedError("Quantity must be positive.", feature_key=metric)
        if not is_known_feature_key(metric):
            raise FeatureDeniedError("Unknown usage metric.", feature_key=metric)

        existing = await self._usage.find_ledger_by_operation(user_id, metric, operation_id)
        if existing is not None and existing.state in {
            UsageLedgerState.RESERVED,
            UsageLedgerState.CONSUMED,
        }:
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

        await self._assert_within_quota(
            user_id=user_id,
            metric=metric,
            additional=quantity,
            limit=decision.limit_value,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
        )

        if existing is not None:
            return await self._usage.re_reserve(existing.id, user_id, quantity)

        return await self._usage.reserve(
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            operation_id=operation_id,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            entry_id=f"usg_{uuid.uuid4().hex}",
        )

    async def consume_usage(
        self, user_id: str, reservation_id: str, actual_quantity: int
    ) -> UsageRead:
        if actual_quantity < 0:
            raise FeatureDeniedError("Actual quantity cannot be negative.", feature_key="usage")

        entry = await self._load_own_ledger_entry(user_id, reservation_id)
        if entry.state == UsageLedgerState.CONSUMED:
            return await self._usage_read_for(entry)
        if entry.state == UsageLedgerState.RELEASED:
            raise FeatureDeniedError("Reservation was released.", feature_key=entry.metric)

        if actual_quantity > entry.quantity:
            decision = await self.require_feature(user_id, entry.metric)
            await self._assert_within_quota(
                user_id=user_id,
                metric=entry.metric,
                additional=actual_quantity - entry.quantity,
                limit=decision.limit_value,
                period_start=entry.period_start,
                period_end=entry.period_end,
            )

        updated = await self._usage.consume(reservation_id, user_id, actual_quantity)
        return await self._usage_read_for(updated)

    async def release_usage(self, user_id: str, reservation_id: str) -> UsageRead:
        entry = await self._load_own_ledger_entry(user_id, reservation_id)
        if entry.state == UsageLedgerState.RELEASED:
            return await self._usage_read_for(entry)
        if entry.state == UsageLedgerState.CONSUMED:
            raise FeatureDeniedError("Cannot release consumed usage.", feature_key=entry.metric)
        updated = await self._usage.release(reservation_id, user_id)
        return await self._usage_read_for(updated)

    async def _load_own_ledger_entry(self, user_id: str, entry_id: str) -> UsageLedgerEntry:
        entry = await self._usage.get_ledger_entry(entry_id, user_id)
        if entry is None or entry.user_id != user_id:
            raise BillingNotFoundError("Reservation not found.")
        return entry

    async def _assert_within_quota(
        self,
        *,
        user_id: str,
        metric: str,
        additional: int,
        limit: int | None,
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        if limit is None:
            return
        agg = await self._usage.get_aggregate(user_id, metric, period_start, period_end)
        current = agg.quantity if agg else 0
        if current + additional > limit:
            raise QuotaExceededError(metric=metric, limit=limit)

    async def _usage_read_for(self, entry: UsageLedgerEntry) -> UsageRead:
        agg = await self._usage.get_aggregate(
            entry.user_id, entry.metric, entry.period_start, entry.period_end
        )
        return UsageRead(
            metric=entry.metric,
            quantity=agg.quantity if agg else 0,
            period_start=entry.period_start,
            period_end=entry.period_end,
        )

    # ── webhooks ─────────────────────────────────────────────────────────────

    async def handle_webhook(self, provider: str, raw_request: RawWebhook) -> WebhookReceipt:
        """Verify, claim, and apply one provider event.

        The provider event id is the idempotency key: a replay returns the
        stored result, a stale event never regresses state, and the subscription
        update, event row, audit event, and outbox rows land in one transaction.
        """
        try:
            event = await self._provider.verify_webhook(raw_request)
        except InvalidWebhookError:
            raise
        except Exception:
            raise InvalidWebhookError()

        existing = await self._webhooks.get_by_provider_event(provider, event.provider_event_id)
        if existing is not None and existing.processing_state in {
            WebhookProcessingState.PROCESSED,
            WebhookProcessingState.IGNORED,
        }:
            return WebhookReceipt(
                provider_event_id=event.provider_event_id,
                processing_state=existing.processing_state,
                duplicate=True,
            )

        if existing is not None:
            claimed_id = existing.id
        else:
            try:
                claimed = await self._webhooks.claim(
                    event_id=f"bwe_{uuid.uuid4().hex}",
                    provider=provider,
                    provider_event_id=event.provider_event_id,
                    event_type=event.event_type,
                    payload_hash=event.payload_hash,
                    provider_occurred_at=event.occurred_at,
                )
                claimed_id = claimed.id
            except ConcurrencyError:
                raced = await self._webhooks.get_by_provider_event(
                    provider, event.provider_event_id
                )
                if raced is None:
                    raise
                if raced.processing_state in {
                    WebhookProcessingState.PROCESSED,
                    WebhookProcessingState.IGNORED,
                }:
                    return WebhookReceipt(
                        provider_event_id=event.provider_event_id,
                        processing_state=raced.processing_state,
                        duplicate=True,
                    )
                claimed_id = raced.id

        sub: Subscription | None = None
        if event.provider_subscription_id:
            sub = await self._subscriptions.get_by_provider_subscription_id(
                event.provider_subscription_id
            )
        if sub is None:
            # Quarantine for operator review; a webhook never creates a user.
            return await self._ignore_event(
                event, claimed_id, failure_code="subscription_not_mapped"
            )

        new_status = self._map_provider_status(event)
        if new_status is None:
            return await self._ignore_event(event, claimed_id, failure_code="unhandled_event")
        if is_stale_provider_event(event.occurred_at, sub.provider_state_updated_at):
            return await self._ignore_event(event, claimed_id, failure_code="stale_event")
        if not can_transition(sub.status, new_status):
            return await self._ignore_event(event, claimed_id, failure_code="invalid_transition")

        grace_ends = sub.grace_period_ends_at
        if new_status == SubscriptionStatus.GRACE_PERIOD and should_enter_grace(sub.status):
            grace_ends = self._clock.now() + timedelta(days=self._grace_period_days)
        if new_status == SubscriptionStatus.RESTRICTED and should_enter_restricted(sub.status):
            grace_ends = None

        now = self._clock.now()
        try:
            saved = await self._subscriptions.update(
                dataclass_replace(
                    sub,
                    status=new_status,
                    provider_customer_id=event.provider_customer_id or sub.provider_customer_id,
                    grace_period_ends_at=grace_ends,
                    provider_state_updated_at=event.occurred_at or now,
                    updated_at=now,
                ),
                sub.version,
            )
        except ConcurrencyError:
            await self._webhooks.mark_failed(claimed_id, "concurrency_conflict")
            raise

        await self._webhooks.mark_processed(claimed_id)
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
            await self._emit(
                EVENT_PAYMENT_FAILED,
                subscription=saved,
                actor_id=None,
                correlation_id=event.provider_event_id,
                data={"subscriptionId": saved.id, "failureCode": event.event_type},
            )
        if new_status == SubscriptionStatus.RESTRICTED:
            await self._emit(
                EVENT_SUBSCRIPTION_RESTRICTED,
                subscription=saved,
                actor_id=None,
                correlation_id=event.provider_event_id,
                data={"subscriptionId": saved.id, "restrictedAt": now.isoformat()},
            )

        log.info(
            "billing.webhook.processed",
            provider=provider,
            event_type=event.event_type,
            payload_hash=event.payload_hash,
            before_status=sub.status.value,
            after_status=saved.status.value,
        )
        return WebhookReceipt(
            provider_event_id=event.provider_event_id,
            processing_state=WebhookProcessingState.PROCESSED,
        )

    async def _ignore_event(
        self, event: ProviderEvent, claimed_id: str, *, failure_code: str
    ) -> WebhookReceipt:
        await self._webhooks.mark_ignored(claimed_id, failure_code=failure_code)
        await self._audit.record(
            AuditEventInput(
                user_id="system",
                action="billing.webhook.ignored",
                target_type="billing_webhook_event",
                target_id=claimed_id,
                after_ref=failure_code,
                correlation_id=event.provider_event_id,
            )
        )
        log.info(
            "billing.webhook.ignored",
            event_type=event.event_type,
            failure_code=failure_code,
            payload_hash=event.payload_hash,
        )
        return WebhookReceipt(
            provider_event_id=event.provider_event_id,
            processing_state=WebhookProcessingState.IGNORED,
        )

    def _map_provider_status(self, event: ProviderEvent) -> SubscriptionStatus | None:
        for candidate in (event.normalized_status, event.event_type):
            if candidate and candidate in _PROVIDER_STATUS_MAP:
                return _PROVIDER_STATUS_MAP[candidate]
        return None

    # ── outbox ───────────────────────────────────────────────────────────────

    async def _emit(
        self,
        event_name: str,
        *,
        subscription: Subscription,
        actor_id: str | None,
        correlation_id: str,
        data: dict[str, object],
    ) -> None:
        """Publish through the outbox, keyed by the aggregate and its version."""
        await self._events.emit(
            EventEnvelope(
                event_name=event_name,
                organisation_id=subscription.user_id,
                idempotency_key=f"{event_name}:{subscription.id}:v{subscription.version}",
                occurred_at=self._clock.now(),
                data=data,
                actor_id=actor_id,
                correlation_id=correlation_id,
            )
        )

    def restricted_mode_blocks(self, feature_key: str) -> bool:
        """Exposed for product services that need the policy without a decision."""
        return restricted_mode_blocks(feature_key)

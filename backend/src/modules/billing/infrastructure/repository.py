"""SQLAlchemy repositories for billing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.domain.errors import ConcurrencyError, PlanImmutableError
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
from src.modules.billing.infrastructure.orm import (
    BillingWebhookEventRow,
    PlanEntitlementRow,
    PlanVersionRow,
    SubscriptionRow,
    UsageAggregateRow,
    UsageLedgerEntryRow,
)


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def _plan_row_to_domain(row: PlanVersionRow) -> PlanVersion:
    return PlanVersion(
        id=row.id,
        code=row.code,
        family=row.family,
        name=row.name,
        version=row.version,
        billing_interval=BillingInterval(row.billing_interval),
        currency=row.currency,
        price_minor_units=row.price_minor_units,
        state=PlanState(row.state),
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _sub_row_to_domain(row: SubscriptionRow) -> Subscription:
    return Subscription(
        id=row.id,
        user_id=row.user_id,
        plan_version_id=row.plan_version_id,
        provider=row.provider,
        provider_customer_id=row.provider_customer_id,
        provider_subscription_id=row.provider_subscription_id,
        status=SubscriptionStatus(row.status),
        current_period_start=row.current_period_start,
        current_period_end=row.current_period_end,
        trial_ends_at=row.trial_ends_at,
        cancel_at_period_end=row.cancel_at_period_end,
        grace_period_ends_at=row.grace_period_ends_at,
        provider_state_updated_at=row.provider_state_updated_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


class SqlPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[PlanVersion]:
        stmt = select(PlanVersionRow).where(PlanVersionRow.state == PlanState.ACTIVE.value)
        result = await self._session.execute(stmt)
        return [_plan_row_to_domain(r) for r in result.scalars().all()]

    async def get(self, plan_version_id: str) -> PlanVersion | None:
        row = await self._session.get(PlanVersionRow, plan_version_id)
        return _plan_row_to_domain(row) if row else None

    async def get_entitlements(self, plan_version_id: str) -> list[PlanEntitlement]:
        stmt = select(PlanEntitlementRow).where(
            PlanEntitlementRow.plan_version_id == plan_version_id
        )
        result = await self._session.execute(stmt)
        return [
            PlanEntitlement(
                plan_version_id=r.plan_version_id,
                feature_key=r.feature_key,
                limit_value=r.limit_value,
                enabled=r.enabled,
            )
            for r in result.scalars().all()
        ]

    async def find_by_code(self, code: str) -> PlanVersion | None:
        stmt = select(PlanVersionRow).where(PlanVersionRow.code == code).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _plan_row_to_domain(row) if row else None

    async def next_version_for_family(self, family: str) -> int:
        stmt = select(func.max(PlanVersionRow.version)).where(PlanVersionRow.family == family)
        current = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(current or 0) + 1

    async def create_draft(
        self, plan: PlanVersion, entitlements: list[PlanEntitlement]
    ) -> PlanVersion:
        self._session.add(
            PlanVersionRow(
                id=plan.id,
                code=plan.code,
                family=plan.family,
                name=plan.name,
                version=plan.version,
                billing_interval=plan.billing_interval.value,
                currency=plan.currency,
                price_minor_units=plan.price_minor_units,
                state=plan.state.value,
                effective_from=plan.effective_from,
                effective_to=plan.effective_to,
            )
        )
        for entitlement in entitlements:
            self._session.add(
                PlanEntitlementRow(
                    id=f"ent_{uuid.uuid4().hex[:16]}",
                    plan_version_id=plan.id,
                    feature_key=entitlement.feature_key,
                    limit_value=entitlement.limit_value,
                    enabled=entitlement.enabled,
                )
            )
        await self._session.flush()
        return plan

    async def activate(self, plan_version_id: str) -> PlanVersion:
        """Publish a draft version.

        The conditional update is what makes publication one-way: an already
        active or retired version matches nothing and the caller sees the
        immutability refusal.
        """
        result = await self._session.execute(
            update(PlanVersionRow)
            .where(
                PlanVersionRow.id == plan_version_id,
                PlanVersionRow.state == PlanState.DRAFT.value,
            )
            .values(state=PlanState.ACTIVE.value)
        )
        if _rowcount(result) != 1:
            raise PlanImmutableError()
        await self._session.flush()
        row = await self._session.get(PlanVersionRow, plan_version_id)
        if row is None:
            raise PlanImmutableError()
        await self._session.refresh(row)
        return _plan_row_to_domain(row)


class SqlSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> Subscription | None:
        stmt = select(SubscriptionRow).where(SubscriptionRow.user_id == user_id).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _sub_row_to_domain(row) if row else None

    async def get_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> Subscription | None:
        stmt = (
            select(SubscriptionRow)
            .where(SubscriptionRow.provider_subscription_id == provider_subscription_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _sub_row_to_domain(row) if row else None

    async def create(self, subscription: Subscription) -> Subscription:
        row = SubscriptionRow(
            id=subscription.id,
            user_id=subscription.user_id,
            plan_version_id=subscription.plan_version_id,
            provider=subscription.provider,
            provider_customer_id=subscription.provider_customer_id,
            provider_subscription_id=subscription.provider_subscription_id,
            status=subscription.status.value,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_ends_at=subscription.trial_ends_at,
            cancel_at_period_end=subscription.cancel_at_period_end,
            grace_period_ends_at=subscription.grace_period_ends_at,
            provider_state_updated_at=subscription.provider_state_updated_at,
            version=subscription.version,
        )
        self._session.add(row)
        await self._session.flush()
        return subscription

    async def update(self, subscription: Subscription, expected_version: int) -> Subscription:
        """Conditional update on the expected version.

        The version predicate is in the UPDATE statement, so two concurrent
        webhook deliveries cannot both win a read-then-write race.
        """
        result = await self._session.execute(
            update(SubscriptionRow)
            .where(
                SubscriptionRow.id == subscription.id,
                SubscriptionRow.version == expected_version,
            )
            .values(
                plan_version_id=subscription.plan_version_id,
                provider_customer_id=subscription.provider_customer_id,
                provider_subscription_id=subscription.provider_subscription_id,
                status=subscription.status.value,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                trial_ends_at=subscription.trial_ends_at,
                cancel_at_period_end=subscription.cancel_at_period_end,
                grace_period_ends_at=subscription.grace_period_ends_at,
                provider_state_updated_at=subscription.provider_state_updated_at,
                version=expected_version + 1,
            )
        )
        if _rowcount(result) != 1:
            raise ConcurrencyError()
        await self._session.flush()
        row = await self._session.get(SubscriptionRow, subscription.id)
        if row is None:
            raise ConcurrencyError()
        await self._session.refresh(row)
        return _sub_row_to_domain(row)


class SqlUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_aggregates_for_user(self, user_id: str) -> list[UsageAggregate]:
        stmt = select(UsageAggregateRow).where(UsageAggregateRow.user_id == user_id)
        result = await self._session.execute(stmt)
        return [
            UsageAggregate(
                user_id=r.user_id,
                metric=r.metric,
                quantity=r.quantity,
                period_start=r.period_start,
                period_end=r.period_end,
                updated_at=r.updated_at,
                version=r.version,
            )
            for r in result.scalars().all()
        ]

    async def get_aggregate(
        self, user_id: str, metric: str, period_start: datetime, period_end: datetime
    ) -> UsageAggregate | None:
        stmt = (
            select(UsageAggregateRow)
            .where(
                UsageAggregateRow.user_id == user_id,
                UsageAggregateRow.metric == metric,
                UsageAggregateRow.period_start == period_start,
                UsageAggregateRow.period_end == period_end,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UsageAggregate(
            user_id=row.user_id,
            metric=row.metric,
            quantity=row.quantity,
            period_start=row.period_start,
            period_end=row.period_end,
            updated_at=row.updated_at,
            version=row.version,
        )

    async def find_ledger_by_operation(
        self, user_id: str, metric: str, operation_id: str
    ) -> UsageLedgerEntry | None:
        stmt = (
            select(UsageLedgerEntryRow)
            .where(
                UsageLedgerEntryRow.user_id == user_id,
                UsageLedgerEntryRow.metric == metric,
                UsageLedgerEntryRow.operation_id == operation_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UsageLedgerEntry(
            id=row.id,
            user_id=row.user_id,
            metric=row.metric,
            quantity=row.quantity,
            period_start=row.period_start,
            period_end=row.period_end,
            operation_id=row.operation_id,
            state=UsageLedgerState(row.state),
            created_at=row.created_at,
        )

    async def get_ledger_entry(self, entry_id: str, user_id: str) -> UsageLedgerEntry | None:
        """Tenancy filter first: another user's reservation id resolves to None."""
        stmt = (
            select(UsageLedgerEntryRow)
            .where(
                UsageLedgerEntryRow.user_id == user_id,
                UsageLedgerEntryRow.id == entry_id,
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return UsageLedgerEntry(
            id=row.id,
            user_id=row.user_id,
            metric=row.metric,
            quantity=row.quantity,
            period_start=row.period_start,
            period_end=row.period_end,
            operation_id=row.operation_id,
            state=UsageLedgerState(row.state),
            created_at=row.created_at,
        )

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
        ledger = UsageLedgerEntryRow(
            id=entry_id,
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            period_start=period_start,
            period_end=period_end,
            operation_id=operation_id,
            state=UsageLedgerState.RESERVED.value,
        )
        self._session.add(ledger)
        await self._add_to_aggregate(
            user_id=user_id,
            metric=metric,
            period_start=period_start,
            period_end=period_end,
            delta=quantity,
        )
        await self._session.flush()
        return Reservation(
            id=entry_id,
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            operation_id=operation_id,
        )

    async def re_reserve(self, entry_id: str, user_id: str, quantity: int) -> Reservation:
        """Return a released ledger row to `reserved` for a retry.

        The operation id stays unique per user and metric, so a retry after a
        terminal failure reuses the same row instead of charging a second one.
        """
        row = await self._own_ledger_row(entry_id, user_id)
        row.quantity = quantity
        row.state = UsageLedgerState.RESERVED.value
        await self._add_to_aggregate(
            user_id=row.user_id,
            metric=row.metric,
            period_start=row.period_start,
            period_end=row.period_end,
            delta=quantity,
        )
        await self._session.flush()
        return Reservation(
            id=row.id,
            user_id=row.user_id,
            metric=row.metric,
            quantity=quantity,
            operation_id=row.operation_id,
        )

    async def consume(self, entry_id: str, user_id: str, actual_quantity: int) -> UsageLedgerEntry:
        row = await self._own_ledger_row(entry_id, user_id)
        delta = actual_quantity - row.quantity
        row.quantity = actual_quantity
        row.state = UsageLedgerState.CONSUMED.value
        if delta != 0:
            await self._add_to_aggregate(
                user_id=row.user_id,
                metric=row.metric,
                period_start=row.period_start,
                period_end=row.period_end,
                delta=delta,
            )
        await self._session.flush()
        return UsageLedgerEntry(
            id=row.id,
            user_id=row.user_id,
            metric=row.metric,
            quantity=row.quantity,
            period_start=row.period_start,
            period_end=row.period_end,
            operation_id=row.operation_id,
            state=UsageLedgerState.CONSUMED,
            created_at=row.created_at,
        )

    async def release(self, entry_id: str, user_id: str) -> UsageLedgerEntry:
        row = await self._own_ledger_row(entry_id, user_id)
        row.state = UsageLedgerState.RELEASED.value
        await self._add_to_aggregate(
            user_id=row.user_id,
            metric=row.metric,
            period_start=row.period_start,
            period_end=row.period_end,
            delta=-row.quantity,
        )
        await self._session.flush()
        return UsageLedgerEntry(
            id=row.id,
            user_id=row.user_id,
            metric=row.metric,
            quantity=row.quantity,
            period_start=row.period_start,
            period_end=row.period_end,
            operation_id=row.operation_id,
            state=UsageLedgerState.RELEASED,
            created_at=row.created_at,
        )

    async def _own_ledger_row(self, entry_id: str, user_id: str) -> UsageLedgerEntryRow:
        """Load a ledger row with the tenancy filter applied before anything else."""
        stmt = (
            select(UsageLedgerEntryRow)
            .where(
                UsageLedgerEntryRow.user_id == user_id,
                UsageLedgerEntryRow.id == entry_id,
            )
            .with_for_update()
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ConcurrencyError("Ledger entry not found.")
        return row

    async def _add_to_aggregate(
        self,
        *,
        user_id: str,
        metric: str,
        period_start: datetime,
        period_end: datetime,
        delta: int,
    ) -> None:
        """Apply a signed delta to the period aggregate as a conditional update.

        The `UPDATE … SET quantity = quantity + :delta` form is what makes
        concurrent reservations unable to overspend the same remaining
        allowance; the insert path is guarded by the period unique constraint.
        """
        result = await self._session.execute(
            update(UsageAggregateRow)
            .where(
                UsageAggregateRow.user_id == user_id,
                UsageAggregateRow.metric == metric,
                UsageAggregateRow.period_start == period_start,
                UsageAggregateRow.period_end == period_end,
            )
            .values(
                quantity=case(
                    (UsageAggregateRow.quantity + delta < 0, 0),
                    else_=UsageAggregateRow.quantity + delta,
                ),
                version=UsageAggregateRow.version + 1,
            )
        )
        if _rowcount(result) == 0:
            self._session.add(
                UsageAggregateRow(
                    id=f"uag_{uuid.uuid4().hex}",
                    user_id=user_id,
                    metric=metric,
                    quantity=max(delta, 0),
                    period_start=period_start,
                    period_end=period_end,
                    version=1,
                )
            )


class SqlBillingWebhookEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: BillingWebhookEventRow) -> BillingWebhookEvent:
        return BillingWebhookEvent(
            id=row.id,
            provider=row.provider,
            provider_event_id=row.provider_event_id,
            event_type=row.event_type,
            received_at=row.received_at,
            provider_occurred_at=row.provider_occurred_at,
            processed_at=row.processed_at,
            processing_state=WebhookProcessingState(row.processing_state),
            payload_hash=row.payload_hash,
            failure_code=row.failure_code,
        )

    async def get_by_provider_event(
        self, provider: str, provider_event_id: str
    ) -> BillingWebhookEvent | None:
        stmt = (
            select(BillingWebhookEventRow)
            .where(
                BillingWebhookEventRow.provider == provider,
                BillingWebhookEventRow.provider_event_id == provider_event_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

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
        now = datetime.now(tz=UTC)
        row = BillingWebhookEventRow(
            id=event_id,
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            received_at=now,
            provider_occurred_at=provider_occurred_at,
            processing_state=WebhookProcessingState.RECEIVED.value,
            payload_hash=payload_hash,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError:
            # Concurrent delivery of the same provider event; the unique
            # (provider, provider_event_id) constraint is the arbiter.
            raise ConcurrencyError("This provider event is already being processed.")
        return self._to_domain(row)

    async def mark_processed(self, event_id: str) -> BillingWebhookEvent:
        row = await self._session.get(BillingWebhookEventRow, event_id)
        if row is None:
            raise ConcurrencyError("Webhook event not found.")
        row.processing_state = WebhookProcessingState.PROCESSED.value
        row.processed_at = datetime.now(tz=UTC)
        await self._session.flush()
        return self._to_domain(row)

    async def mark_ignored(
        self, event_id: str, failure_code: str | None = None
    ) -> BillingWebhookEvent:
        row = await self._session.get(BillingWebhookEventRow, event_id)
        if row is None:
            raise ConcurrencyError("Webhook event not found.")
        row.processing_state = WebhookProcessingState.IGNORED.value
        row.failure_code = failure_code
        row.processed_at = datetime.now(tz=UTC)
        await self._session.flush()
        return self._to_domain(row)

    async def mark_failed(self, event_id: str, failure_code: str) -> BillingWebhookEvent:
        row = await self._session.get(BillingWebhookEventRow, event_id)
        if row is None:
            raise ConcurrencyError("Webhook event not found.")
        row.processing_state = WebhookProcessingState.FAILED.value
        row.failure_code = failure_code
        row.processed_at = datetime.now(tz=UTC)
        await self._session.flush()
        return self._to_domain(row)

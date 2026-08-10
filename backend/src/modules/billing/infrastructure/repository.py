"""SQLAlchemy repositories for billing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.domain.errors import ConcurrencyError
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
        row = await self._session.get(SubscriptionRow, subscription.id)
        if row is None:
            raise ConcurrencyError("Subscription not found.")
        if row.version != expected_version:
            raise ConcurrencyError("Subscription version mismatch.")
        row.plan_version_id = subscription.plan_version_id
        row.provider_customer_id = subscription.provider_customer_id
        row.provider_subscription_id = subscription.provider_subscription_id
        row.status = subscription.status.value
        row.current_period_start = subscription.current_period_start
        row.current_period_end = subscription.current_period_end
        row.trial_ends_at = subscription.trial_ends_at
        row.cancel_at_period_end = subscription.cancel_at_period_end
        row.grace_period_ends_at = subscription.grace_period_ends_at
        row.provider_state_updated_at = subscription.provider_state_updated_at
        row.version = expected_version + 1
        await self._session.flush()
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

    async def get_ledger_entry(self, entry_id: str) -> UsageLedgerEntry | None:
        row = await self._session.get(UsageLedgerEntryRow, entry_id)
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

        agg_stmt = (
            select(UsageAggregateRow)
            .where(
                UsageAggregateRow.user_id == user_id,
                UsageAggregateRow.metric == metric,
                UsageAggregateRow.period_start == period_start,
                UsageAggregateRow.period_end == period_end,
            )
            .limit(1)
        )
        result = await self._session.execute(agg_stmt)
        agg_row = result.scalar_one_or_none()
        if agg_row is None:
            agg_row = UsageAggregateRow(
                id=f"uag_{uuid.uuid4().hex}",
                user_id=user_id,
                metric=metric,
                quantity=quantity,
                period_start=period_start,
                period_end=period_end,
                version=1,
            )
            self._session.add(agg_row)
        else:
            agg_row.quantity += quantity
            agg_row.version += 1

        await self._session.flush()
        return Reservation(
            id=entry_id,
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            operation_id=operation_id,
        )

    async def consume(self, entry_id: str, actual_quantity: int) -> UsageLedgerEntry:
        row = await self._session.get(UsageLedgerEntryRow, entry_id)
        if row is None:
            raise ConcurrencyError("Ledger entry not found.")
        reserved = row.quantity
        delta = actual_quantity - reserved
        row.quantity = actual_quantity
        row.state = UsageLedgerState.CONSUMED.value

        agg_stmt = (
            select(UsageAggregateRow)
            .where(
                UsageAggregateRow.user_id == row.user_id,
                UsageAggregateRow.metric == row.metric,
                UsageAggregateRow.period_start == row.period_start,
                UsageAggregateRow.period_end == row.period_end,
            )
            .limit(1)
        )
        result = await self._session.execute(agg_stmt)
        agg_row = result.scalar_one_or_none()
        if agg_row is not None and delta != 0:
            agg_row.quantity += delta
            agg_row.version += 1

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

    async def release(self, entry_id: str) -> UsageLedgerEntry:
        row = await self._session.get(UsageLedgerEntryRow, entry_id)
        if row is None:
            raise ConcurrencyError("Ledger entry not found.")
        row.state = UsageLedgerState.RELEASED.value

        agg_stmt = (
            select(UsageAggregateRow)
            .where(
                UsageAggregateRow.user_id == row.user_id,
                UsageAggregateRow.metric == row.metric,
                UsageAggregateRow.period_start == row.period_start,
                UsageAggregateRow.period_end == row.period_end,
            )
            .limit(1)
        )
        result = await self._session.execute(agg_stmt)
        agg_row = result.scalar_one_or_none()
        if agg_row is not None:
            agg_row.quantity = max(0, agg_row.quantity - row.quantity)
            agg_row.version += 1

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
        await self._session.flush()
        return self._to_domain(row)

    async def mark_processed(self, event_id: str) -> BillingWebhookEvent:
        row = await self._session.get(BillingWebhookEventRow, event_id)
        if row is None:
            raise ConcurrencyError("Webhook event not found.")
        row.processing_state = WebhookProcessingState.PROCESSED.value
        row.processed_at = datetime.now(tz=UTC)
        await self._session.flush()
        return self._to_domain(row)

    async def mark_ignored(self, event_id: str, failure_code: str | None = None) -> BillingWebhookEvent:
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

"""SQLAlchemy repositories for notification preferences and deliveries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.notification.domain.models import (
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    NotificationLocale,
    NotificationPreference,
    PaginatedDeliveries,
    ProviderEvent,
    TemplateDeployment,
)
from src.modules.notification.infrastructure.orm import (
    NotificationConsumedEventRow,
    NotificationDeliveryRow,
    NotificationPreferenceRow,
    NotificationProviderEventRow,
    NotificationTemplateDeploymentRow,
)


def _pref_row_to_domain(row: NotificationPreferenceRow) -> NotificationPreference:
    return NotificationPreference(
        id=row.id,
        organisation_id=row.organisation_id,
        user_id=row.user_id,
        channel=NotificationChannel(row.channel),
        enabled=row.enabled,
        locale=NotificationLocale(row.locale),
        timezone=row.timezone,
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
        version=row.version,
    )


def _delivery_row_to_domain(row: NotificationDeliveryRow) -> NotificationDelivery:
    return NotificationDelivery(
        id=row.id,
        organisation_id=row.organisation_id,
        source_event_id=row.source_event_id,
        subject_ref=row.subject_ref,
        obligation_id=row.obligation_id,
        matter_id=row.matter_id,
        recipient_user_id=row.recipient_user_id,
        channel=NotificationChannel(row.channel),
        reminder_type=row.reminder_type,
        obligation_class=row.obligation_class,
        urgency=row.urgency,
        confidentiality_level=row.confidentiality_level,
        template_key=row.template_key,
        delivery_policy_key=row.delivery_policy_key,
        locale=NotificationLocale(row.locale),
        status=DeliveryStatus(row.status),
        attempt_count=row.attempt_count,
        created_at=row.created_at,
        correlation_id=row.correlation_id,
        version=row.version,
        next_attempt_at=row.next_attempt_at,
        attempted_at=row.attempted_at,
        delivered_at=row.delivered_at,
        provider_message_id=row.provider_message_id,
        provider_state=row.provider_state,
        failure_code=row.failure_code,
        failure_class=row.failure_class,
        read_at=row.read_at,
        preview_title=row.preview_title,
        preview_body=row.preview_body,
    )


class SqlPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self, *, organisation_id: str, user_id: str
    ) -> list[NotificationPreference]:
        stmt = select(NotificationPreferenceRow).where(
            NotificationPreferenceRow.organisation_id == organisation_id,
            NotificationPreferenceRow.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return [_pref_row_to_domain(r) for r in result.scalars().all()]

    async def get(
        self, *, organisation_id: str, user_id: str, channel: NotificationChannel
    ) -> NotificationPreference | None:
        stmt = select(NotificationPreferenceRow).where(
            NotificationPreferenceRow.organisation_id == organisation_id,
            NotificationPreferenceRow.user_id == user_id,
            NotificationPreferenceRow.channel == channel.value,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _pref_row_to_domain(row) if row else None

    async def upsert(self, preference: NotificationPreference) -> NotificationPreference:
        row = await self._session.get(NotificationPreferenceRow, preference.id)
        if row is None:
            row = NotificationPreferenceRow(
                id=preference.id,
                organisation_id=preference.organisation_id,
                user_id=preference.user_id,
                channel=preference.channel.value,
                enabled=preference.enabled,
                locale=preference.locale.value,
                timezone=preference.timezone,
                quiet_hours_start=preference.quiet_hours_start,
                quiet_hours_end=preference.quiet_hours_end,
                version=preference.version,
            )
            self._session.add(row)
        else:
            row.enabled = preference.enabled
            row.locale = preference.locale.value
            row.timezone = preference.timezone
            row.quiet_hours_start = preference.quiet_hours_start
            row.quiet_hours_end = preference.quiet_hours_end
            row.version = preference.version
        await self._session.flush()
        return _pref_row_to_domain(row)


class SqlDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, *, organisation_id: str, delivery_id: str
    ) -> NotificationDelivery | None:
        row = await self._session.get(NotificationDeliveryRow, delivery_id)
        if row is None or row.organisation_id != organisation_id:
            return None
        return _delivery_row_to_domain(row)

    async def get_idempotent(
        self,
        *,
        organisation_id: str,
        subject_ref: str,
        recipient_user_id: str,
        reminder_type: str,
        channel: NotificationChannel,
    ) -> NotificationDelivery | None:
        stmt = select(NotificationDeliveryRow).where(
            NotificationDeliveryRow.organisation_id == organisation_id,
            NotificationDeliveryRow.subject_ref == subject_ref,
            NotificationDeliveryRow.recipient_user_id == recipient_user_id,
            NotificationDeliveryRow.reminder_type == reminder_type,
            NotificationDeliveryRow.channel == channel.value,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _delivery_row_to_domain(row) if row else None

    async def create(self, delivery: NotificationDelivery) -> NotificationDelivery:
        row = NotificationDeliveryRow(
            id=delivery.id,
            organisation_id=delivery.organisation_id,
            source_event_id=delivery.source_event_id,
            subject_ref=delivery.subject_ref,
            obligation_id=delivery.obligation_id,
            matter_id=delivery.matter_id,
            recipient_user_id=delivery.recipient_user_id,
            channel=delivery.channel.value,
            reminder_type=delivery.reminder_type,
            obligation_class=delivery.obligation_class,
            urgency=delivery.urgency,
            confidentiality_level=delivery.confidentiality_level,
            template_key=delivery.template_key,
            delivery_policy_key=delivery.delivery_policy_key,
            locale=delivery.locale.value,
            status=delivery.status.value,
            attempt_count=delivery.attempt_count,
            next_attempt_at=delivery.next_attempt_at,
            attempted_at=delivery.attempted_at,
            delivered_at=delivery.delivered_at,
            provider_message_id=delivery.provider_message_id,
            provider_state=delivery.provider_state,
            failure_code=delivery.failure_code,
            failure_class=delivery.failure_class,
            correlation_id=delivery.correlation_id,
            preview_title=delivery.preview_title,
            preview_body=delivery.preview_body,
            read_at=delivery.read_at,
            version=delivery.version,
            created_at=delivery.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _delivery_row_to_domain(row)

    async def update(self, delivery: NotificationDelivery) -> NotificationDelivery:
        row = await self._session.get(NotificationDeliveryRow, delivery.id)
        if row is None:
            raise ValueError("delivery row missing")
        row.status = delivery.status.value
        row.attempt_count = delivery.attempt_count
        row.next_attempt_at = delivery.next_attempt_at
        row.attempted_at = delivery.attempted_at
        row.delivered_at = delivery.delivered_at
        row.provider_message_id = delivery.provider_message_id
        row.provider_state = delivery.provider_state
        row.failure_code = delivery.failure_code
        row.failure_class = delivery.failure_class
        row.read_at = delivery.read_at
        row.version = delivery.version
        await self._session.flush()
        return _delivery_row_to_domain(row)

    async def list_in_app_for_user(
        self,
        *,
        organisation_id: str,
        user_id: str,
        limit: int,
        cursor: str | None,
    ) -> PaginatedDeliveries:
        stmt = (
            select(NotificationDeliveryRow)
            .where(
                NotificationDeliveryRow.organisation_id == organisation_id,
                NotificationDeliveryRow.recipient_user_id == user_id,
                NotificationDeliveryRow.channel == NotificationChannel.IN_APP.value,
            )
            .order_by(NotificationDeliveryRow.created_at.desc(), NotificationDeliveryRow.id.desc())
            .limit(limit + 1)
        )
        if cursor:
            cursor_row = await self._session.get(NotificationDeliveryRow, cursor)
            if cursor_row is not None:
                stmt = stmt.where(
                    NotificationDeliveryRow.created_at < cursor_row.created_at,
                )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = rows[-1].id
        return PaginatedDeliveries(
            items=[_delivery_row_to_domain(r) for r in rows],
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            limit=limit,
        )

    async def find_by_provider_message_id(
        self, *, provider_message_id: str
    ) -> NotificationDelivery | None:
        stmt = select(NotificationDeliveryRow).where(
            NotificationDeliveryRow.provider_message_id == provider_message_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _delivery_row_to_domain(row) if row else None


class SqlConsumedEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def already_consumed(self, *, event_id: str) -> bool:
        stmt = select(NotificationConsumedEventRow.id).where(
            NotificationConsumedEventRow.event_id == event_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def record(
        self,
        *,
        event_id: str,
        event_name: str,
        organisation_id: str,
        outcome: str,
        correlation_id: str,
    ) -> bool:
        row = NotificationConsumedEventRow(
            id=f"nce_{uuid.uuid4().hex}",
            event_id=event_id,
            event_name=event_name,
            organisation_id=organisation_id,
            outcome=outcome,
            correlation_id=correlation_id,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            return False
        return True


class SqlProviderEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, *, provider: str, provider_event_id: str) -> ProviderEvent | None:
        stmt = select(NotificationProviderEventRow).where(
            NotificationProviderEventRow.provider == provider,
            NotificationProviderEventRow.provider_event_id == provider_event_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ProviderEvent(
            id=row.id,
            provider=row.provider,
            provider_event_id=row.provider_event_id,
            event_type=row.event_type,
            provider_message_id=row.provider_message_id,
            delivery_id=row.delivery_id,
            received_at=row.received_at,
        )

    async def record(self, event: ProviderEvent) -> ProviderEvent:
        row = NotificationProviderEventRow(
            id=event.id,
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            provider_message_id=event.provider_message_id,
            delivery_id=event.delivery_id,
            organisation_id=None,
            received_at=event.received_at,
        )
        self._session.add(row)
        await self._session.flush()
        return event


class SqlTemplateDeploymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self, *, environment: str, template_key: str, locale: NotificationLocale
    ) -> TemplateDeployment | None:
        stmt = select(NotificationTemplateDeploymentRow).where(
            NotificationTemplateDeploymentRow.environment == environment,
            NotificationTemplateDeploymentRow.template_key == template_key,
            NotificationTemplateDeploymentRow.locale == locale.value,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return TemplateDeployment(
            id=row.id,
            environment=row.environment,
            template_key=row.template_key,
            locale=NotificationLocale(row.locale),
            source_version=row.source_version,
            provider_template_id=row.provider_template_id,
            published_by=row.published_by,
            published_at=row.published_at,
        )

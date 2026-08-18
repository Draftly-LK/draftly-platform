"""SQL repositories for obligations."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.obligations.domain.models import (
    ConfidentialityLevel,
    LawyerConfirmation,
    LawyerConfirmationStatus,
    Obligation,
    ObligationClass,
    ObligationHardness,
    ObligationScope,
    ObligationStatus,
    ObligationType,
    ReminderOccurrence,
    ReminderType,
    SourceType,
    TriggerType,
)
from src.modules.obligations.infrastructure.orm import (
    LawyerConfirmationRow,
    ObligationRow,
    OutboxEventRow,
    ReminderOccurrenceRow,
)
from src.modules.obligations.ports import ObligationListFilters, OutboxEvent


def _confirmation_from_row(row: LawyerConfirmationRow | None) -> LawyerConfirmation:
    if row is None:
        return LawyerConfirmation(status=LawyerConfirmationStatus.NOT_REQUIRED)
    return LawyerConfirmation(
        status=LawyerConfirmationStatus(row.status),
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
        reason=row.reason,
        original_due_at=row.original_due_at,
    )


def _row_to_obligation(row: ObligationRow, confirmation: LawyerConfirmation) -> Obligation:
    return Obligation(
        id=row.id,
        organisation_id=row.organisation_id,
        scope=ObligationScope(row.scope),
        matter_id=row.matter_id,
        owner_user_id=row.owner_user_id,
        obligation_type=ObligationType(row.obligation_type),
        obligation_class=ObligationClass(row.obligation_class),
        label_key=row.label_key,
        source_type=SourceType(row.source_type),
        source_id=row.source_id,
        source_version=row.source_version,
        legal_authority_ref=row.legal_authority_ref,
        trigger_type=TriggerType(row.trigger_type),
        trigger_id=row.trigger_id,
        trigger_date=row.trigger_date,
        due_at=row.due_at,
        timezone=row.timezone,
        calculation_rule_id=row.calculation_rule_id,
        calculation_version=row.calculation_version,
        calculation_explanation=row.calculation_explanation,
        hardness=ObligationHardness(row.hardness),
        status=ObligationStatus(row.status),
        assignee_user_id=row.assignee_user_id,
        backup_assignee_user_id=row.backup_assignee_user_id,
        recurrence_rule=row.recurrence_rule,
        reminder_policy_id=row.reminder_policy_id,
        escalation_policy_id=row.escalation_policy_id,
        confidentiality_level=ConfidentialityLevel(row.confidentiality_level),
        lawyer_confirmation=confirmation,
        completion_evidence_ref=row.completion_evidence_ref,
        completed_at=row.completed_at,
        completed_by=row.completed_by,
        cancelled_at=row.cancelled_at,
        cancelled_by=row.cancelled_by,
        cancellation_reason=row.cancellation_reason,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlObligationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_confirmation(self, obligation_id: str) -> LawyerConfirmation:
        row = await self._session.get(LawyerConfirmationRow, obligation_id)
        return _confirmation_from_row(row)

    async def create(self, obligation: Obligation) -> Obligation:
        row = ObligationRow(
            id=obligation.id,
            organisation_id=obligation.organisation_id,
            scope=obligation.scope.value,
            matter_id=obligation.matter_id,
            owner_user_id=obligation.owner_user_id,
            obligation_type=obligation.obligation_type.value,
            obligation_class=obligation.obligation_class.value,
            label_key=obligation.label_key,
            source_type=obligation.source_type.value,
            source_id=obligation.source_id,
            source_version=obligation.source_version,
            legal_authority_ref=obligation.legal_authority_ref,
            trigger_type=obligation.trigger_type.value,
            trigger_id=obligation.trigger_id,
            trigger_date=obligation.trigger_date,
            due_at=obligation.due_at,
            timezone=obligation.timezone,
            calculation_rule_id=obligation.calculation_rule_id,
            calculation_version=obligation.calculation_version,
            calculation_explanation=obligation.calculation_explanation,
            hardness=obligation.hardness.value,
            status=obligation.status.value,
            assignee_user_id=obligation.assignee_user_id,
            backup_assignee_user_id=obligation.backup_assignee_user_id,
            recurrence_rule=obligation.recurrence_rule,
            reminder_policy_id=obligation.reminder_policy_id,
            escalation_policy_id=obligation.escalation_policy_id,
            confidentiality_level=obligation.confidentiality_level.value,
            completion_evidence_ref=obligation.completion_evidence_ref,
            completed_at=obligation.completed_at,
            completed_by=obligation.completed_by,
            cancelled_at=obligation.cancelled_at,
            cancelled_by=obligation.cancelled_by,
            cancellation_reason=obligation.cancellation_reason,
            version=obligation.version,
        )
        self._session.add(row)
        conf = LawyerConfirmationRow(
            obligation_id=obligation.id,
            organisation_id=obligation.organisation_id,
            status=obligation.lawyer_confirmation.status.value,
            confirmed_by=obligation.lawyer_confirmation.confirmed_by,
            confirmed_at=obligation.lawyer_confirmation.confirmed_at,
            reason=obligation.lawyer_confirmation.reason,
            original_due_at=obligation.lawyer_confirmation.original_due_at,
        )
        self._session.add(conf)
        await self._session.flush()
        return obligation

    async def update(self, obligation: Obligation) -> Obligation:
        row = await self._session.get(ObligationRow, obligation.id)
        if row is None:
            return obligation
        row.status = obligation.status.value
        row.due_at = obligation.due_at
        row.version = obligation.version
        row.updated_at = obligation.updated_at
        row.completion_evidence_ref = obligation.completion_evidence_ref
        row.completed_at = obligation.completed_at
        row.completed_by = obligation.completed_by
        row.cancelled_at = obligation.cancelled_at
        row.cancelled_by = obligation.cancelled_by
        row.cancellation_reason = obligation.cancellation_reason
        conf = await self._session.get(LawyerConfirmationRow, obligation.id)
        if conf is None:
            conf = LawyerConfirmationRow(
                obligation_id=obligation.id,
                organisation_id=obligation.organisation_id,
            )
            self._session.add(conf)
        conf.status = obligation.lawyer_confirmation.status.value
        conf.confirmed_by = obligation.lawyer_confirmation.confirmed_by
        conf.confirmed_at = obligation.lawyer_confirmation.confirmed_at
        conf.reason = obligation.lawyer_confirmation.reason
        conf.original_due_at = obligation.lawyer_confirmation.original_due_at
        await self._session.flush()
        return obligation

    async def get(self, organisation_id: str, obligation_id: str) -> Obligation | None:
        row = await self._session.get(ObligationRow, obligation_id)
        if row is None or row.organisation_id != organisation_id:
            return None
        confirmation = await self._load_confirmation(obligation_id)
        return _row_to_obligation(row, confirmation)

    async def list_for_organisation(
        self,
        organisation_id: str,
        filters: ObligationListFilters,
    ) -> tuple[list[Obligation], str | None, bool]:
        limit = min(filters.limit, 100)
        stmt = (
            select(ObligationRow)
            .where(ObligationRow.organisation_id == organisation_id)
            .order_by(ObligationRow.due_at.asc(), ObligationRow.id.asc())
            .limit(limit + 1)
        )
        if filters.assignee_user_id:
            stmt = stmt.where(ObligationRow.assignee_user_id == filters.assignee_user_id)
        if filters.matter_id:
            stmt = stmt.where(ObligationRow.matter_id == filters.matter_id)
        if filters.status:
            stmt = stmt.where(ObligationRow.status == filters.status)
        if filters.cursor:
            cursor_row = await self._session.get(ObligationRow, filters.cursor)
            if cursor_row is not None:
                stmt = stmt.where(
                    or_(
                        ObligationRow.due_at > cursor_row.due_at,
                        (ObligationRow.due_at == cursor_row.due_at)
                        & (ObligationRow.id > cursor_row.id),
                    )
                )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items: list[Obligation] = []
        for row in page_rows:
            confirmation = await self._load_confirmation(row.id)
            items.append(_row_to_obligation(row, confirmation))
        next_cursor = page_rows[-1].id if has_more and page_rows else None
        return items, next_cursor, has_more


class SqlReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, occurrence: ReminderOccurrence) -> ReminderOccurrence:
        row = ReminderOccurrenceRow(
            id=occurrence.id,
            organisation_id=occurrence.organisation_id,
            obligation_id=occurrence.obligation_id,
            recipient_user_id=occurrence.recipient_user_id,
            reminder_type=occurrence.reminder_type.value,
            scheduled_for=occurrence.scheduled_for,
            emitted_at=occurrence.emitted_at,
            event_id=occurrence.event_id,
        )
        self._session.add(row)
        await self._session.flush()
        return occurrence

    async def find_existing(
        self,
        obligation_id: str,
        recipient_user_id: str,
        reminder_type: str,
    ) -> ReminderOccurrence | None:
        stmt = select(ReminderOccurrenceRow).where(
            ReminderOccurrenceRow.obligation_id == obligation_id,
            ReminderOccurrenceRow.recipient_user_id == recipient_user_id,
            ReminderOccurrenceRow.reminder_type == reminder_type,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ReminderOccurrence(
            id=row.id,
            organisation_id=row.organisation_id,
            obligation_id=row.obligation_id,
            recipient_user_id=row.recipient_user_id,
            reminder_type=ReminderType(row.reminder_type),
            scheduled_for=row.scheduled_for,
            emitted_at=row.emitted_at,
            event_id=row.event_id,
        )

    async def list_for_obligation(self, obligation_id: str) -> list[ReminderOccurrence]:
        stmt = select(ReminderOccurrenceRow).where(
            ReminderOccurrenceRow.obligation_id == obligation_id
        )
        result = await self._session.execute(stmt)
        return [
            ReminderOccurrence(
                id=row.id,
                organisation_id=row.organisation_id,
                obligation_id=row.obligation_id,
                recipient_user_id=row.recipient_user_id,
                reminder_type=ReminderType(row.reminder_type),
                scheduled_for=row.scheduled_for,
                emitted_at=row.emitted_at,
                event_id=row.event_id,
            )
            for row in result.scalars().all()
        ]


class SqlObligationEventPort:
    def __init__(self, session: AsyncSession, organisation_id: str) -> None:
        self._session = session
        self._organisation_id = organisation_id

    async def append(self, event: OutboxEvent) -> None:
        row = OutboxEventRow(
            id=f"evt_{uuid.uuid4().hex}",
            organisation_id=self._organisation_id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            payload_json=json.dumps(event.payload),
            correlation_id=event.correlation_id,
        )
        self._session.add(row)
        await self._session.flush()


class SqlNotificationIntentPort:
    """Records reminder intents in-process; does not call notification_service."""

    def __init__(self) -> None:
        self.recorded: list[object] = []

    async def record_reminder_intent(self, intent: object) -> None:
        self.recorded.append(intent)

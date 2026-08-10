"""Obligations application service — core lifecycle (L3)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.obligations.domain.errors import (
    CancellationReasonRequiredError,
    CorrectionReasonRequiredError,
    ObligationNotFoundError,
    RestrictedComplianceAccessError,
)
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
    SourceType,
    TriggerType,
)
from src.modules.obligations.domain.policies import (
    assert_can_cancel,
    assert_can_complete,
    assert_can_confirm,
    can_view_obligation,
    initial_status_for_create,
    project_time_status,
    reminders_allowed,
    requires_lawyer_confirmation,
    solo_organisation_id,
)
from src.modules.obligations.ports import (
    ClockPort,
    DeadlineRulePort,
    EventPort,
    NotificationIntentPort,
    NotificationReminderIntent,
    ObligationListFilters,
    ObligationRepository,
    OutboxEvent,
    ReminderRepository,
)
from src.platform.request_context import RequestContext


@dataclass(frozen=True)
class CreateObligationCommand:
    scope: ObligationScope
    obligation_type: ObligationType
    obligation_class: ObligationClass
    label_key: str
    due_at: datetime
    timezone: str
    hardness: ObligationHardness
    assignee_user_id: str
    matter_id: str | None = None
    source_type: SourceType = SourceType.MANUAL
    source_id: str = "manual"
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_date: datetime | None = None
    legal_authority_ref: str | None = None
    confidentiality_level: ConfidentialityLevel = ConfidentialityLevel.STANDARD
    reminder_policy_id: str = "default-reminders-v1"


@dataclass(frozen=True)
class ConfirmDeadlineCommand:
    due_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CompleteObligationCommand:
    completion_evidence_ref: str | None = None


@dataclass(frozen=True)
class CancelObligationCommand:
    reason: str


class ObligationsService:
    def __init__(
        self,
        *,
        obligation_repo: ObligationRepository,
        reminder_repo: ReminderRepository,
        deadline_rules: DeadlineRulePort,
        events: EventPort,
        audit: AuditPort,
        clock: ClockPort,
        notification_intents: NotificationIntentPort,
        compliance_allowlist: frozenset[str] | None = None,
    ) -> None:
        self._obligations = obligation_repo
        self._reminders = reminder_repo
        self._deadline_rules = deadline_rules
        self._events = events
        self._audit = audit
        self._clock = clock
        self._notification_intents = notification_intents
        self._compliance_allowlist = compliance_allowlist or frozenset()

    def _organisation_id(self, ctx: RequestContext) -> str:
        return solo_organisation_id(ctx.actor_id)

    def _has_compliance_access(self, ctx: RequestContext) -> bool:
        return ctx.actor_id in self._compliance_allowlist

    async def _get_visible(
        self,
        ctx: RequestContext,
        obligation_id: str,
    ) -> Obligation:
        org_id = self._organisation_id(ctx)
        obligation = await self._obligations.get(org_id, obligation_id)
        if obligation is None:
            raise ObligationNotFoundError()
        if not can_view_obligation(
            obligation,
            actor_id=ctx.actor_id,
            actor_role=ctx.account_role,
            has_compliance_access=self._has_compliance_access(ctx),
        ):
            if obligation.confidentiality_level == ConfidentialityLevel.RESTRICTED_COMPLIANCE:
                raise RestrictedComplianceAccessError()
            raise ObligationNotFoundError()
        return obligation

    async def list_obligations(
        self,
        ctx: RequestContext,
        filters: ObligationListFilters,
    ) -> tuple[list[Obligation], str | None, bool]:
        org_id = self._organisation_id(ctx)
        items, cursor, has_more = await self._obligations.list_for_organisation(org_id, filters)
        now = self._clock.now()
        visible: list[Obligation] = []
        for item in items:
            if not can_view_obligation(
                item,
                actor_id=ctx.actor_id,
                actor_role=ctx.account_role,
                has_compliance_access=self._has_compliance_access(ctx),
            ):
                continue
            projected = self._with_projected_status(item, now)
            visible.append(projected)
        return visible, cursor, has_more

    async def create_obligation(
        self,
        ctx: RequestContext,
        command: CreateObligationCommand,
    ) -> Obligation:
        now = self._clock.now()
        trigger_date = command.trigger_date or now
        confirmation = LawyerConfirmation(
            status=LawyerConfirmationStatus.NOT_REQUIRED,
        )
        if requires_lawyer_confirmation(
            Obligation(
                id="",
                organisation_id="",
                scope=command.scope,
                obligation_type=command.obligation_type,
                obligation_class=command.obligation_class,
                label_key=command.label_key,
                source_type=command.source_type,
                source_id=command.source_id,
                trigger_type=command.trigger_type,
                trigger_date=trigger_date,
                due_at=command.due_at,
                timezone=command.timezone,
                hardness=command.hardness,
                status=ObligationStatus.DRAFT,
                assignee_user_id=command.assignee_user_id,
                reminder_policy_id=command.reminder_policy_id,
                confidentiality_level=command.confidentiality_level,
                lawyer_confirmation=confirmation,
                version=1,
                created_at=now,
                updated_at=now,
                matter_id=command.matter_id,
                owner_user_id=ctx.actor_id,
                legal_authority_ref=command.legal_authority_ref,
            )
        ):
            confirmation = LawyerConfirmation(status=LawyerConfirmationStatus.PENDING)

        obligation_id = f"obl_{uuid.uuid4().hex}"
        obligation = Obligation(
            id=obligation_id,
            organisation_id=self._organisation_id(ctx),
            scope=command.scope,
            obligation_type=command.obligation_type,
            obligation_class=command.obligation_class,
            label_key=command.label_key,
            source_type=command.source_type,
            source_id=command.source_id,
            trigger_type=command.trigger_type,
            trigger_date=trigger_date,
            due_at=command.due_at,
            timezone=command.timezone,
            hardness=command.hardness,
            status=ObligationStatus.DRAFT,
            assignee_user_id=command.assignee_user_id,
            reminder_policy_id=command.reminder_policy_id,
            confidentiality_level=command.confidentiality_level,
            lawyer_confirmation=confirmation,
            version=1,
            created_at=now,
            updated_at=now,
            matter_id=command.matter_id,
            owner_user_id=ctx.actor_id,
            legal_authority_ref=command.legal_authority_ref,
        )
        obligation.status = initial_status_for_create(obligation)
        obligation = await self._obligations.create(obligation)

        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="obligation.created",
                target_type="obligation",
                target_id=obligation.id,
                matter_id=obligation.matter_id,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.append(
            OutboxEvent(
                event_type="obligation.created",
                aggregate_id=obligation.id,
                payload={
                    "obligationId": obligation.id,
                    "organisationId": obligation.organisation_id,
                    "obligationClass": obligation.obligation_class.value,
                    "obligationType": obligation.obligation_type.value,
                },
                correlation_id=ctx.correlation_id,
            )
        )
        if reminders_allowed(obligation):
            await self.schedule_reminders(obligation)
        return self._with_projected_status(obligation, now)

    async def get_obligation(self, ctx: RequestContext, obligation_id: str) -> Obligation:
        obligation = await self._get_visible(ctx, obligation_id)
        return self._with_projected_status(obligation, self._clock.now())

    async def confirm_deadline(
        self,
        ctx: RequestContext,
        obligation_id: str,
        command: ConfirmDeadlineCommand,
    ) -> Obligation:
        obligation = await self._get_visible(ctx, obligation_id)
        assert_can_confirm(obligation, role=ctx.account_role)
        now = self._clock.now()
        before_status = obligation.status

        original_due = obligation.due_at
        corrected = command.due_at is not None and command.due_at != original_due
        if corrected:
            if not command.reason:
                raise CorrectionReasonRequiredError()
            assert command.due_at is not None
            obligation.lawyer_confirmation = LawyerConfirmation(
                status=LawyerConfirmationStatus.CORRECTED,
                confirmed_by=ctx.actor_id,
                confirmed_at=now,
                reason=command.reason,
                original_due_at=original_due,
            )
            obligation.due_at = command.due_at
            event_type = "obligation.deadline-corrected"
            audit_action = "obligation.corrected"
        else:
            obligation.lawyer_confirmation = LawyerConfirmation(
                status=LawyerConfirmationStatus.CONFIRMED,
                confirmed_by=ctx.actor_id,
                confirmed_at=now,
                reason=command.reason,
                original_due_at=original_due,
            )
            event_type = "obligation.deadline-confirmed"
            audit_action = "obligation.confirmed"

        obligation.status = ObligationStatus.UPCOMING
        obligation.version += 1
        obligation.updated_at = now
        obligation = await self._obligations.update(obligation)

        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action=audit_action,
                target_type="obligation",
                target_id=obligation.id,
                matter_id=obligation.matter_id,
                before_ref=before_status.value,
                after_ref=obligation.status.value,
                reason=command.reason,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.append(
            OutboxEvent(
                event_type=event_type,
                aggregate_id=obligation.id,
                payload={"obligationId": obligation.id},
                correlation_id=ctx.correlation_id,
            )
        )
        await self.schedule_reminders(obligation)
        return self._with_projected_status(obligation, now)

    async def complete_obligation(
        self,
        ctx: RequestContext,
        obligation_id: str,
        command: CompleteObligationCommand,
    ) -> Obligation:
        obligation = await self._get_visible(ctx, obligation_id)
        assert_can_complete(obligation)
        now = self._clock.now()
        before_status = obligation.status
        obligation.status = ObligationStatus.COMPLETE
        obligation.completed_at = now
        obligation.completed_by = ctx.actor_id
        obligation.completion_evidence_ref = command.completion_evidence_ref
        obligation.version += 1
        obligation.updated_at = now
        obligation = await self._obligations.update(obligation)

        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="obligation.completed",
                target_type="obligation",
                target_id=obligation.id,
                matter_id=obligation.matter_id,
                before_ref=before_status.value,
                after_ref=obligation.status.value,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.append(
            OutboxEvent(
                event_type="obligation.status-changed",
                aggregate_id=obligation.id,
                payload={
                    "obligationId": obligation.id,
                    "beforeStatus": before_status.value,
                    "afterStatus": obligation.status.value,
                },
                correlation_id=ctx.correlation_id,
            )
        )
        return obligation

    async def cancel_obligation(
        self,
        ctx: RequestContext,
        obligation_id: str,
        command: CancelObligationCommand,
    ) -> Obligation:
        if not command.reason.strip():
            raise CancellationReasonRequiredError()
        obligation = await self._get_visible(ctx, obligation_id)
        assert_can_cancel(obligation)
        now = self._clock.now()
        before_status = obligation.status
        obligation.status = ObligationStatus.CANCELLED
        obligation.cancelled_at = now
        obligation.cancelled_by = ctx.actor_id
        obligation.cancellation_reason = command.reason
        obligation.version += 1
        obligation.updated_at = now
        obligation = await self._obligations.update(obligation)

        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                action="obligation.cancelled",
                target_type="obligation",
                target_id=obligation.id,
                matter_id=obligation.matter_id,
                before_ref=before_status.value,
                after_ref=obligation.status.value,
                reason=command.reason,
                correlation_id=ctx.correlation_id,
            )
        )
        await self._events.append(
            OutboxEvent(
                event_type="obligation.cancelled",
                aggregate_id=obligation.id,
                payload={"obligationId": obligation.id},
                correlation_id=ctx.correlation_id,
            )
        )
        return obligation

    async def schedule_reminders(self, obligation: Obligation) -> int:
        if not reminders_allowed(obligation):
            return 0
        specs = await self._deadline_rules.reminder_schedule(obligation.reminder_policy_id)
        created = 0
        for spec in specs:
            existing = await self._reminders.find_existing(
                obligation.id,
                obligation.assignee_user_id,
                spec.reminder_type.value,
            )
            if existing is not None:
                continue
            scheduled_for = obligation.due_at + timedelta(days=spec.offset_days)
            occurrence_id = f"rem_{uuid.uuid4().hex}"
            occurrence = ReminderOccurrence(
                id=occurrence_id,
                organisation_id=obligation.organisation_id,
                obligation_id=obligation.id,
                recipient_user_id=obligation.assignee_user_id,
                reminder_type=spec.reminder_type,
                scheduled_for=scheduled_for,
            )
            await self._reminders.create(occurrence)
            await self._notification_intents.record_reminder_intent(
                NotificationReminderIntent(
                    obligation_id=obligation.id,
                    recipient_user_id=obligation.assignee_user_id,
                    reminder_type=spec.reminder_type.value,
                    scheduled_for=scheduled_for,
                    template_key="obligation.reminder.neutral",
                )
            )
            created += 1
        return created

    def _with_projected_status(self, obligation: Obligation, now: datetime) -> Obligation:
        projected = project_time_status(obligation, now)
        if projected == obligation.status:
            return obligation
        obligation.status = projected
        return obligation

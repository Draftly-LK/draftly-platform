"""Unit tests for ObligationsService — confirmation gate, state machine, isolation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.auth.domain.models import Role
from src.modules.auth.ports import AuditEventInput
from src.modules.obligations.application.obligations_service import (
    CancelObligationCommand,
    CompleteObligationCommand,
    ConfirmDeadlineCommand,
    CreateObligationCommand,
    ObligationsService,
)
from src.modules.obligations.domain.errors import (
    ConfirmationRequiredError,
    LawyerConfirmationDeniedError,
    ObligationNotFoundError,
)
from src.modules.obligations.domain.models import (
    LawyerConfirmationStatus,
    ObligationClass,
    ObligationHardness,
    ObligationScope,
    ObligationStatus,
    ObligationType,
)
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
from src.modules.obligations.infrastructure.stubs import (
    FixedClockPort,
    InMemoryObligationRepository,
    InMemoryReminderRepository,
    RecordingEventPort,
    RecordingNotificationIntentPort,
)
from src.platform.request_context import RequestContext


class RecordingAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)


def _ctx(actor_id: str, role: Role = Role.APPROVER) -> RequestContext:
    return RequestContext(actor_id=actor_id, account_role=role, correlation_id="corr-1")


def _service(
    repo: InMemoryObligationRepository | None = None,
    *,
    clock: datetime | None = None,
) -> ObligationsService:
    return ObligationsService(
        obligation_repo=repo or InMemoryObligationRepository(),
        reminder_repo=InMemoryReminderRepository(),
        deadline_rules=FixtureDeadlineRulePort(),
        events=RecordingEventPort(),
        audit=RecordingAuditPort(),
        clock=FixedClockPort(clock or datetime(2026, 3, 1, tzinfo=UTC)),
        notification_intents=RecordingNotificationIntentPort(),
    )


@pytest.mark.asyncio
async def test_hard_deadline_starts_awaiting_confirmation() -> None:
    service = _service()
    obligation = await service.create_obligation(
        _ctx("usr_a"),
        CreateObligationCommand(
            scope=ObligationScope.MATTER,
            obligation_type=ObligationType.NOTARIAL_REGISTRATION,
            obligation_class=ObligationClass.LEGAL_DEADLINE,
            label_key="obligation.test.registration",
            due_at=datetime(2026, 4, 30, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.HARD,
            assignee_user_id="usr_a",
        ),
    )
    assert obligation.status == ObligationStatus.AWAITING_CONFIRMATION
    assert obligation.lawyer_confirmation.status == LawyerConfirmationStatus.PENDING


@pytest.mark.asyncio
async def test_complete_hard_deadline_requires_confirmation() -> None:
    service = _service()
    created = await service.create_obligation(
        _ctx("usr_a"),
        CreateObligationCommand(
            scope=ObligationScope.MATTER,
            obligation_type=ObligationType.NOTARIAL_REGISTRATION,
            obligation_class=ObligationClass.LEGAL_DEADLINE,
            label_key="obligation.test.registration",
            due_at=datetime(2026, 4, 30, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.HARD,
            assignee_user_id="usr_a",
        ),
    )
    with pytest.raises(ConfirmationRequiredError):
        await service.complete_obligation(
            _ctx("usr_a"),
            created.id,
            CompleteObligationCommand(),
        )


@pytest.mark.asyncio
async def test_reviewer_cannot_confirm_deadline() -> None:
    service = _service()
    created = await service.create_obligation(
        _ctx("usr_a"),
        CreateObligationCommand(
            scope=ObligationScope.MATTER,
            obligation_type=ObligationType.NOTARIAL_REGISTRATION,
            obligation_class=ObligationClass.LEGAL_DEADLINE,
            label_key="obligation.test.registration",
            due_at=datetime(2026, 4, 30, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.HARD,
            assignee_user_id="usr_a",
        ),
    )
    with pytest.raises(LawyerConfirmationDeniedError):
        await service.confirm_deadline(
            _ctx("usr_a", Role.REVIEWER),
            created.id,
            ConfirmDeadlineCommand(),
        )


@pytest.mark.asyncio
async def test_confirm_then_complete_and_schedule_reminders() -> None:
    reminders = InMemoryReminderRepository()
    notifications = RecordingNotificationIntentPort()
    service = ObligationsService(
        obligation_repo=InMemoryObligationRepository(),
        reminder_repo=reminders,
        deadline_rules=FixtureDeadlineRulePort(),
        events=RecordingEventPort(),
        audit=RecordingAuditPort(),
        clock=FixedClockPort(datetime(2026, 3, 1, tzinfo=UTC)),
        notification_intents=notifications,
    )
    created = await service.create_obligation(
        _ctx("usr_a"),
        CreateObligationCommand(
            scope=ObligationScope.USER,
            obligation_type=ObligationType.CLIENT_FOLLOW_UP,
            obligation_class=ObligationClass.FOLLOW_UP,
            label_key="obligation.test.follow-up",
            due_at=datetime(2026, 4, 15, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.SOFT,
            assignee_user_id="usr_a",
        ),
    )
    assert len(await reminders.list_for_obligation(created.id)) == 3
    completed = await service.complete_obligation(
        _ctx("usr_a"),
        created.id,
        CompleteObligationCommand(completion_evidence_ref="evidence:demo"),
    )
    assert completed.status == ObligationStatus.COMPLETE


@pytest.mark.asyncio
async def test_cross_user_isolation() -> None:
    repo = InMemoryObligationRepository()
    service = _service(repo)
    created = await service.create_obligation(
        _ctx("usr_a"),
        CreateObligationCommand(
            scope=ObligationScope.USER,
            obligation_type=ObligationType.INTERNAL_ADMIN,
            obligation_class=ObligationClass.INTERNAL_TARGET,
            label_key="obligation.test.internal",
            due_at=datetime(2026, 5, 1, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.SOFT,
            assignee_user_id="usr_a",
        ),
    )
    with pytest.raises(ObligationNotFoundError):
        await service.get_obligation(_ctx("usr_b"), created.id)


@pytest.mark.asyncio
async def test_cancel_requires_reason() -> None:
    service = _service()
    created = await service.create_obligation(
        _ctx("usr_a"),
        CreateObligationCommand(
            scope=ObligationScope.USER,
            obligation_type=ObligationType.INTERNAL_ADMIN,
            obligation_class=ObligationClass.INTERNAL_TARGET,
            label_key="obligation.test.internal",
            due_at=datetime(2026, 5, 1, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.SOFT,
            assignee_user_id="usr_a",
        ),
    )
    cancelled = await service.cancel_obligation(
        _ctx("usr_a"),
        created.id,
        CancelObligationCommand(reason="No longer applicable"),
    )
    assert cancelled.status == ObligationStatus.CANCELLED

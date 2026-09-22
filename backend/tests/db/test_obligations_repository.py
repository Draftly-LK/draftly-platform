"""Obligations through the real service and SQL repositories on Postgres.

A deadline read back must keep its lawyer-confirmation state, and one
caller must never see another's deadlines.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.auth.domain.models import Role
from src.modules.obligations.application.obligations_service import (
    CreateObligationCommand,
    ObligationsService,
)
from src.modules.obligations.domain.errors import ObligationNotFoundError
from src.modules.obligations.domain.models import (
    LawyerConfirmationStatus,
    ObligationClass,
    ObligationHardness,
    ObligationScope,
    ObligationStatus,
    ObligationType,
)
from src.modules.obligations.infrastructure.deadline_rule_fixture import FixtureDeadlineRulePort
from src.modules.obligations.infrastructure.repository import (
    SqlNotificationIntentPort,
    SqlObligationEventPort,
    SqlObligationRepository,
    SqlReminderRepository,
)
from src.modules.obligations.infrastructure.stubs import SystemClockPort
from src.platform.request_context import RequestContext
from tests.factories.constants import USER_A, USER_B

pytestmark = pytest.mark.integration


def _service(session: AsyncSession, ctx: RequestContext) -> ObligationsService:
    """Wired the way api/deps.get_obligations_service wires it."""
    return ObligationsService(
        obligation_repo=SqlObligationRepository(session),
        reminder_repo=SqlReminderRepository(session),
        deadline_rules=FixtureDeadlineRulePort(),
        events=SqlObligationEventPort(session, f"org_{ctx.actor_id}"),
        audit=AuditService(repository=SqlAuditRepository(session)),
        clock=SystemClockPort(),
        notification_intents=SqlNotificationIntentPort(),
    )


def _ctx(user_id: str) -> RequestContext:
    return RequestContext(actor_id=user_id, account_role=Role.APPROVER)


HARD_DEADLINE = CreateObligationCommand(
    scope=ObligationScope.MATTER,
    obligation_type=ObligationType.NOTARIAL_REGISTRATION,
    obligation_class=ObligationClass.LEGAL_DEADLINE,
    label_key="obligation.synthetic.registration",
    due_at=datetime(2026, 12, 31, tzinfo=UTC),
    timezone="Asia/Colombo",
    hardness=ObligationHardness.HARD,
    assignee_user_id=USER_A,
)


async def test_a_hard_deadline_reads_back_awaiting_confirmation(
    db_session: AsyncSession,
) -> None:
    ctx = _ctx(USER_A)
    created = await _service(db_session, ctx).create_obligation(ctx, HARD_DEADLINE)

    stored = await _service(db_session, ctx).get_obligation(ctx, created.id)

    assert stored.id == created.id
    assert stored.status is ObligationStatus.AWAITING_CONFIRMATION
    assert stored.lawyer_confirmation.status is LawyerConfirmationStatus.PENDING
    assert stored.due_at == HARD_DEADLINE.due_at


async def test_another_caller_cannot_read_a_deadline(db_session: AsyncSession) -> None:
    owner, other = _ctx(USER_A), _ctx(USER_B)
    created = await _service(db_session, owner).create_obligation(owner, HARD_DEADLINE)

    with pytest.raises(ObligationNotFoundError):
        await _service(db_session, other).get_obligation(other, created.id)

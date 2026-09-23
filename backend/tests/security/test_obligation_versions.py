"""The obligation actions demand the version they change (api-conventions.md §3).

These routes load the obligation before comparing versions, so they need a
real one: created through the real service on Postgres, then acted on over
HTTP without If-Match (428), with a stale one (412), and with the right one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.auth.domain.models import Role
from src.modules.obligations.application.obligations_service import (
    CreateObligationCommand,
    ObligationsService,
)
from src.modules.obligations.domain.models import (
    ObligationClass,
    ObligationHardness,
    ObligationScope,
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
from src.platform.db.session import get_db
from src.platform.request_context import RequestContext
from tests.factories.constants import USER_A
from tests.security.harness import Harness

pytestmark = pytest.mark.integration

SUBJECT = "user_synthetic_obligations"
ACTIONS: list[tuple[str, dict[str, Any]]] = [
    ("confirm", {"reason": "Synthetic confirmation"}),
    ("complete", {}),
    ("cancel", {"reason": "Synthetic cancellation"}),
]


@pytest.fixture
async def obligation(harness: Harness, db_session: AsyncSession) -> AsyncIterator[str]:
    """A soft internal deadline owned by USER_A, served through the harness."""
    ctx = RequestContext(actor_id=USER_A, account_role=Role.APPROVER)
    service = ObligationsService(
        obligation_repo=SqlObligationRepository(db_session),
        reminder_repo=SqlReminderRepository(db_session),
        deadline_rules=FixtureDeadlineRulePort(),
        events=SqlObligationEventPort(db_session, f"org_{USER_A}"),
        audit=AuditService(repository=SqlAuditRepository(db_session)),
        clock=SystemClockPort(),
        notification_intents=SqlNotificationIntentPort(),
    )
    created = await service.create_obligation(
        ctx,
        CreateObligationCommand(
            scope=ObligationScope.USER,
            obligation_type=ObligationType.INTERNAL_ADMIN,
            obligation_class=ObligationClass.INTERNAL_TARGET,
            label_key="obligation.synthetic.internal",
            due_at=datetime(2026, 12, 31, tzinfo=UTC),
            timezone="Asia/Colombo",
            hardness=ObligationHardness.SOFT,
            assignee_user_id=USER_A,
        ),
    )
    await db_session.commit()

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db_session

    harness.app.dependency_overrides[get_db] = _session
    await harness.link(SUBJECT, USER_A)
    yield created.id


@pytest.mark.parametrize(("action", "body"), ACTIONS)
async def test_an_obligation_action_without_if_match_is_428(
    harness: Harness, obligation: str, action: str, body: dict[str, Any]
) -> None:
    response = await harness.client.post(
        f"/api/v1/obligations/{obligation}/{action}", json=body, headers=harness.signed_in(SUBJECT)
    )

    assert response.status_code == 428, response.text


@pytest.mark.parametrize(("action", "body"), ACTIONS)
async def test_an_obligation_action_from_a_stale_version_is_412(
    harness: Harness, obligation: str, action: str, body: dict[str, Any]
) -> None:
    response = await harness.client.post(
        f"/api/v1/obligations/{obligation}/{action}",
        json=body,
        headers={**harness.signed_in(SUBJECT), "If-Match": '"99"'},
    )

    assert response.status_code == 412, response.text


async def test_the_listed_version_lets_the_action_through(
    harness: Harness, obligation: str
) -> None:
    """The list is where a client reads the version; there is no single GET."""
    listed = await harness.client.get("/api/v1/obligations", headers=harness.signed_in(SUBJECT))
    version = next(item["version"] for item in listed.json()["items"] if item["id"] == obligation)

    response = await harness.client.post(
        f"/api/v1/obligations/{obligation}/complete",
        json={},
        headers={**harness.signed_in(SUBJECT), "If-Match": f'"{version}"'},
    )

    assert response.status_code == 200, response.text

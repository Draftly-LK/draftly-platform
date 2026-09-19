"""SqlPlanRepository and SqlSubscriptionRepository against Postgres."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.domain.errors import PlanImmutableError
from src.modules.billing.domain.models import (
    BillingInterval,
    PlanEntitlement,
    PlanState,
    PlanVersion,
)
from src.modules.billing.infrastructure.repository import SqlPlanRepository
from tests.factories.constants import NOW

pytestmark = pytest.mark.integration


def _plan(plan_id: str = "pv_synthetic", state: PlanState = PlanState.DRAFT) -> PlanVersion:
    return PlanVersion(
        id=plan_id,
        code=f"{plan_id}-code",
        family="synthetic",
        name="Synthetic plan",
        version=1,
        billing_interval=BillingInterval.MONTHLY,
        currency="LKR",
        price_minor_units=100000,
        state=state,
        effective_from=NOW - timedelta(days=1),
        effective_to=None,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_a_draft_plan_is_stored_with_its_entitlements(db_session: AsyncSession) -> None:
    """POST /admin/plans writes a plan and its entitlements in one call.

    Postgres enforces the entitlement's foreign key to its plan, so the plan
    row must reach the database first.
    """
    repository = SqlPlanRepository(db_session)
    entitlements = [
        PlanEntitlement("pv_synthetic", "document_pages.monthly", 500, True),
        PlanEntitlement("pv_synthetic", "research.enabled", None, False),
    ]

    await repository.create_draft(_plan(), entitlements)

    stored = await repository.get("pv_synthetic")
    assert stored is not None and stored.state is PlanState.DRAFT
    assert sorted(
        (e.feature_key, e.limit_value, e.enabled)
        for e in await repository.get_entitlements("pv_synthetic")
    ) == [("document_pages.monthly", 500, True), ("research.enabled", None, False)]


async def test_activating_a_draft_makes_it_offered(db_session: AsyncSession) -> None:
    repository = SqlPlanRepository(db_session)
    await repository.create_draft(_plan(), [])

    activated = await repository.activate("pv_synthetic")

    assert activated.state is PlanState.ACTIVE
    assert "pv_synthetic" in {p.id for p in await repository.list_active()}


async def test_publication_is_one_way(db_session: AsyncSession) -> None:
    """An active plan cannot be activated again: prices are immutable once offered."""
    repository = SqlPlanRepository(db_session)
    await repository.create_draft(_plan(), [])
    await repository.activate("pv_synthetic")

    with pytest.raises(PlanImmutableError):
        await repository.activate("pv_synthetic")

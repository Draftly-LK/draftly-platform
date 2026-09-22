"""Quota reserve, consume and release through the real billing service (Rule 7).

Reserve, consume, release. Over-quota is refused, and a failed operation
returns its reservation rather than burning it. The concurrent cases matter
most: two requests at once must not both slip under the limit, and one
reservation must not be refunded twice.

Real commits (``db_committing``), so concurrent sessions see each other.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.deps import build_billing_service
from src.modules.auth.domain.models import Role
from src.modules.auth.infrastructure.repository import SqlUserRepository
from src.modules.billing.application.billing_service import BillingService
from src.modules.billing.domain.errors import QuotaExceededError
from src.modules.billing.domain.models import (
    BillingInterval,
    PlanEntitlement,
    PlanState,
    PlanVersion,
    Subscription,
    SubscriptionStatus,
)
from src.modules.billing.infrastructure.repository import (
    SqlPlanRepository,
    SqlSubscriptionRepository,
)
from src.platform.request_context import RequestContext
from tests.factories.auth import active_user
from tests.factories.constants import USER_A

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
METRIC = "document_pages.monthly"
LIMIT = 5


@pytest.fixture
async def subscribed(db_committing: Sessions) -> Sessions:
    """USER_A on an active plan allowing LIMIT pages this period."""
    now = datetime.now(tz=UTC)
    async with db_committing() as session:
        await SqlUserRepository(session).create(active_user(USER_A))
        await SqlPlanRepository(session).create_draft(
            PlanVersion(
                id="pv_synthetic",
                code="synthetic-pages",
                family="synthetic",
                name="Synthetic pages",
                version=1,
                billing_interval=BillingInterval.MONTHLY,
                currency="LKR",
                price_minor_units=100000,
                state=PlanState.ACTIVE,
                effective_from=now - timedelta(days=1),
                effective_to=None,
                created_at=now,
                updated_at=now,
            ),
            [PlanEntitlement("pv_synthetic", METRIC, LIMIT, True)],
        )
        await SqlSubscriptionRepository(session).create(
            Subscription(
                id="sub_synthetic",
                user_id=USER_A,
                plan_version_id="pv_synthetic",
                provider="stub",
                provider_customer_id=None,
                provider_subscription_id=None,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now - timedelta(days=1),
                current_period_end=now + timedelta(days=29),
                trial_ends_at=None,
                cancel_at_period_end=False,
                grace_period_ends_at=None,
                provider_state_updated_at=now,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        await session.commit()
    return db_committing


async def _in_session(
    sessions: Sessions, act: Callable[[BillingService], Awaitable[Any]], *, hold: float = 0
) -> Any:
    """One request: its own session and service, committed at the end.

    ``hold`` keeps the transaction open after the work, so a concurrent
    request overlaps it the way two real requests would.
    """
    async with sessions() as session:
        result = await act(build_billing_service(session))
        await asyncio.sleep(hold)
        await session.commit()
        return result


async def _used(sessions: Sessions) -> int:
    async def read(service: BillingService) -> int:
        usage = await service.get_usage(RequestContext(actor_id=USER_A, account_role=Role.APPROVER))
        return next((u.quantity for u in usage if u.metric == METRIC), 0)

    return int(await _in_session(sessions, read))


def _reserve(quantity: int, operation: str) -> Callable[[BillingService], Awaitable[Any]]:
    return lambda service: service.reserve_usage(USER_A, METRIC, quantity, operation)


# ── One request at a time ───────────────────────────────────────────────────


async def test_reserving_past_the_limit_is_refused(subscribed: Sessions) -> None:
    await _in_session(subscribed, _reserve(3, "op_1"))

    with pytest.raises(QuotaExceededError):
        await _in_session(subscribed, _reserve(3, "op_2"))

    assert await _used(subscribed) == 3


async def test_a_released_reservation_returns_its_quota(subscribed: Sessions) -> None:
    reservation = await _in_session(subscribed, _reserve(4, "op_1"))
    await _in_session(subscribed, lambda s: s.release_usage(USER_A, reservation.id))

    await _in_session(subscribed, _reserve(LIMIT, "op_2"))

    assert await _used(subscribed) == LIMIT


async def test_retrying_an_operation_charges_once(subscribed: Sessions) -> None:
    first = await _in_session(subscribed, _reserve(2, "op_1"))
    again = await _in_session(subscribed, _reserve(2, "op_1"))

    assert again.id == first.id
    assert await _used(subscribed) == 2


async def test_consuming_less_than_reserved_returns_the_difference(subscribed: Sessions) -> None:
    reservation = await _in_session(subscribed, _reserve(4, "op_1"))

    await _in_session(subscribed, lambda s: s.consume_usage(USER_A, reservation.id, 1))

    assert await _used(subscribed) == 1


async def test_releasing_twice_refunds_once(subscribed: Sessions) -> None:
    await _in_session(subscribed, _reserve(2, "op_keep"))
    reservation = await _in_session(subscribed, _reserve(3, "op_1"))

    for _ in range(2):
        await _in_session(subscribed, lambda s: s.release_usage(USER_A, reservation.id))

    assert await _used(subscribed) == 2


# ── Two requests at once ────────────────────────────────────────────────────


async def test_two_concurrent_reservations_cannot_both_slip_under_the_limit(
    subscribed: Sessions,
) -> None:
    await _in_session(subscribed, _reserve(LIMIT - 1, "op_base"))

    outcomes = await asyncio.gather(
        _in_session(subscribed, _reserve(1, "op_a"), hold=0.3),
        _in_session(subscribed, _reserve(1, "op_b"), hold=0.3),
        return_exceptions=True,
    )

    refused = [o for o in outcomes if isinstance(o, QuotaExceededError)]
    assert len(refused) == 1, outcomes
    assert await _used(subscribed) == LIMIT


async def test_one_reservation_released_concurrently_is_refunded_once(
    subscribed: Sessions,
) -> None:
    await _in_session(subscribed, _reserve(2, "op_keep"))
    reservation = await _in_session(subscribed, _reserve(3, "op_1"))

    await asyncio.gather(
        _in_session(subscribed, lambda s: s.release_usage(USER_A, reservation.id), hold=0.3),
        _in_session(subscribed, lambda s: s.release_usage(USER_A, reservation.id), hold=0.3),
    )

    assert await _used(subscribed) == 2

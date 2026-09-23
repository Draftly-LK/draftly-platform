"""Notification consumes each event and each provider webhook once (§9.1).

Events are delivered at least once and providers retry webhooks, so the
database is what turns "at least once" into "once": a unique key per
consumed event and per provider event.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.notification.domain.models import ProviderEvent
from src.modules.notification.infrastructure.repository import (
    SqlConsumedEventRepository,
    SqlProviderEventRepository,
)
from tests.factories.constants import NOW, USER_A

pytestmark = pytest.mark.integration


async def _record(repository: SqlConsumedEventRepository, event_id: str) -> bool:
    return await repository.record(
        event_id=event_id,
        event_name="obligation.escalated",
        organisation_id=USER_A,
        outcome="processed",
        correlation_id="corr_synthetic",
    )


async def test_an_event_is_consumed_once(db_session: AsyncSession) -> None:
    repository = SqlConsumedEventRepository(db_session)

    first = await _record(repository, "evt_synthetic_1")
    again = await _record(repository, "evt_synthetic_1")

    assert (first, again) == (True, False)
    assert await repository.already_consumed(event_id="evt_synthetic_1")
    assert not await repository.already_consumed(event_id="evt_synthetic_2")


async def test_a_duplicate_leaves_the_session_usable(db_session: AsyncSession) -> None:
    """The duplicate is caught in a savepoint, so the handler's work survives."""
    repository = SqlConsumedEventRepository(db_session)
    await _record(repository, "evt_synthetic_1")
    await _record(repository, "evt_synthetic_1")

    assert await _record(repository, "evt_synthetic_2") is True


def _provider_event(**overrides: object) -> ProviderEvent:
    event = ProviderEvent(
        id="npe_synthetic_1",
        provider="resend",
        provider_event_id="msg_synthetic_1",
        event_type="email.delivered",
        provider_message_id="re_synthetic_1",
        delivery_id=None,
        received_at=NOW,
    )
    return replace(event, **overrides)  # type: ignore[arg-type]


async def test_a_provider_event_reads_back(db_session: AsyncSession) -> None:
    repository = SqlProviderEventRepository(db_session)
    await repository.record(_provider_event())

    assert await repository.find(provider="resend", provider_event_id="msg_synthetic_1") == (
        _provider_event()
    )
    assert await repository.find(provider="other", provider_event_id="msg_synthetic_1") is None


async def test_a_replayed_provider_event_is_refused_by_the_table(
    db_session: AsyncSession,
) -> None:
    """A retried webhook cannot land twice, whatever the handler checked first."""
    repository = SqlProviderEventRepository(db_session)
    await repository.record(_provider_event())

    with pytest.raises(IntegrityError):
        await repository.record(_provider_event(id="npe_synthetic_2"))

"""The per-user audit hash chain, written by the real service (Rule 2, §5.3).

``AuditService.record`` links each event to the one before it in the same
user's chain. These write through the service and the SQL repository on
Postgres, then walk the stored rows with the verification function.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.domain.chain import first_broken_link
from src.modules.audit.infrastructure.orm import AuditEventRow
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.auth.ports import AuditEventInput
from tests.factories.constants import MATTER_A, USER_A, USER_B

pytestmark = pytest.mark.integration


def _event(user_id: str, n: int) -> AuditEventInput:
    return AuditEventInput(
        user_id=user_id,
        action="matter.updated",
        target_type="matter",
        target_id=MATTER_A,
        matter_id=MATTER_A,
        actor=user_id,
        after_ref=f"synthetic-change-{n}",
        correlation_id=f"corr_synthetic_{n}",
    )


async def _record(session: AsyncSession, user_id: str, n: int) -> None:
    await AuditService(repository=SqlAuditRepository(session)).record(_event(user_id, n))


async def _chain(session: AsyncSession, user_id: str) -> list[AuditEventRow]:
    """One user's events in chain order: follow prev_hash from the genesis."""
    rows = list(
        (await session.execute(select(AuditEventRow).where(AuditEventRow.user_id == user_id)))
        .scalars()
        .all()
    )
    by_prev = {row.prev_hash: row for row in rows}
    ordered: list[AuditEventRow] = []
    link = ""
    while link in by_prev:
        ordered.append(by_prev[link])
        link = by_prev[link].hash
    assert len(ordered) == len(rows), "the chain forks or has an orphan"
    return ordered


async def test_ten_events_form_one_verifiable_chain(db_session: AsyncSession) -> None:
    for n in range(10):
        await _record(db_session, USER_A, n)

    chain = await _chain(db_session, USER_A)

    assert len(chain) == 10
    assert chain[0].prev_hash == ""
    assert [row.after_ref for row in chain] == [f"synthetic-change-{n}" for n in range(10)]
    assert first_broken_link(chain) is None


async def test_two_users_keep_independent_chains(db_session: AsyncSession) -> None:
    for n in range(3):
        await _record(db_session, USER_A, n)
        await _record(db_session, USER_B, n)

    chain_a = await _chain(db_session, USER_A)
    chain_b = await _chain(db_session, USER_B)

    assert chain_a[0].prev_hash == chain_b[0].prev_hash == ""
    assert {row.hash for row in chain_a}.isdisjoint({row.prev_hash for row in chain_b})
    assert first_broken_link(chain_a) is None
    assert first_broken_link(chain_b) is None


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("action", "matter.deleted"),
        ("after_ref", "synthetic-rewritten-history"),
        ("actor", "usr_synthetic_someone_else"),
        ("prev_hash", "0" * 64),
    ],
)
async def test_an_out_of_band_edit_is_detected_at_the_edited_event(
    db_session: AsyncSession, column: str, value: str
) -> None:
    for n in range(5):
        await _record(db_session, USER_A, n)
    chain = await _chain(db_session, USER_A)
    target = chain[2]

    await db_session.execute(
        update(AuditEventRow).where(AuditEventRow.id == target.id).values({column: value})
    )
    await db_session.flush()
    await db_session.refresh(target)

    assert first_broken_link(chain) == target.id


async def test_a_deleted_event_is_detected_at_the_next_one(db_session: AsyncSession) -> None:
    for n in range(5):
        await _record(db_session, USER_A, n)
    chain = await _chain(db_session, USER_A)

    survivors = chain[:2] + chain[3:]

    assert first_broken_link(survivors) == chain[3].id


async def test_concurrent_writes_for_one_user_stay_one_chain(
    db_committing: async_sessionmaker[AsyncSession],
) -> None:
    """Two transactions recording for one user at once must not both link to
    the same previous event: that would fork the chain into two branches."""
    async with db_committing() as seed:
        await _record(seed, USER_A, 0)
        await seed.commit()

    async def writer(n: int) -> None:
        async with db_committing() as session:
            await _record(session, USER_A, n)
            # Hold the transaction open so the two writers overlap.
            await asyncio.sleep(0.3)
            await session.commit()

    await asyncio.gather(writer(1), writer(2))

    async with db_committing() as session:
        chain = await _chain(session, USER_A)

    assert len(chain) == 3
    assert first_broken_link(chain) is None

"""The ``db_session`` fixture keeps every test's writes to itself.

These guard the harness the repository, audit-chain and privacy suites will
stand on. A leak here would make those suites order-dependent without saying
so, so the isolation is asserted rather than assumed.
"""

from __future__ import annotations

import os

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.platform.db.idempotency import IdempotencyKeyRow
from tests.db.conftest import BACKEND_ROOT
from tests.factories.constants import NOW, USER_A

pytestmark = pytest.mark.integration

#: Every isolation test inserts this same primary key, so a write that
#: survived its test makes the next one fail on a unique violation. The
#: committing test runs first: a leak from it is the one the fixture exists
#: to stop.
SHARED_ROW_ID = "idem_db_fixture_isolation"


def _row() -> IdempotencyKeyRow:
    return IdempotencyKeyRow(
        id=SHARED_ROW_ID,
        user_id=USER_A,
        route="POST /synthetic",
        idempotency_key="synthetic-key",
        request_hash="0" * 64,
        response={"status": 201},
        created_at=NOW,
    )


async def _count_from_another_connection(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        result = await connection.execute(
            select(func.count())
            .select_from(IdempotencyKeyRow)
            .where(IdempotencyKeyRow.id == SHARED_ROW_ID)
        )
        return int(result.scalar_one())


async def test_a_commit_inside_a_test_is_still_rolled_back(
    db_session: AsyncSession, db_engine: AsyncEngine
) -> None:
    db_session.add(_row())
    await db_session.commit()

    # The commit released a savepoint; the outer transaction is still open.
    assert await db_session.get(IdempotencyKeyRow, SHARED_ROW_ID) is not None
    assert await _count_from_another_connection(db_engine) == 0


async def test_schema_is_migrated_to_the_single_head(db_session: AsyncSession) -> None:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()

    version = (
        await db_session.execute(text("SELECT version_num FROM alembic_version"))
    ).scalar_one()

    assert version == head


async def test_a_write_is_visible_inside_its_own_test(db_session: AsyncSession) -> None:
    db_session.add(_row())
    await db_session.flush()

    stored = await db_session.get(IdempotencyKeyRow, SHARED_ROW_ID)

    assert stored is not None
    assert stored.response == {"status": 201}


async def test_an_uncommitted_write_is_invisible_to_other_connections(
    db_session: AsyncSession, db_engine: AsyncEngine
) -> None:
    db_session.add(_row())
    await db_session.flush()

    assert await _count_from_another_connection(db_engine) == 0

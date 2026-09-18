"""A migrated, rolled-back Postgres session per test (TESTING_PLAN.md §5.2).

Once per run: create a throwaway schema, run ``alembic upgrade head`` into it,
and drop it at the end. Per test: open one outer transaction, hand the test a
session bound to it, and roll the transaction back afterwards. A test may call
``commit()``: with ``join_transaction_mode="create_savepoint"`` that commits a
savepoint, and the outer rollback still discards it. Nothing a test writes
survives it, so tests stay independent of their order.

The outbox worker commits across two sessions by design, so it cannot use this
fixture; it gets a committing one when its tests land.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import src.platform.config as settings_module
from tests.db.postgres import database_url, skip_or_fail

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_asyncio_loop_factories(config: pytest.Config, item: pytest.Item) -> dict[str, Any]:
    """psycopg's async mode cannot run on the Windows proactor loop.

    A pytest-asyncio hook, so every loop in this directory is built by it.
    Setting the policy inside a test fixture is too late: the test's loop may
    already exist by then, and the test fails or passes by collection order.
    """
    if os.name == "nt":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}


def _sync_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)


def _upgrade_head(url: str, schema: str) -> None:
    """Run the real migration chain into ``schema``, not a metadata shortcut.

    ``migrations/env.py`` reads ``DATABASE_URL_DIRECT`` through the cached
    settings, so both are swapped for the call and restored after.
    """
    scoped = f"{url}{'&' if '?' in url else '?'}options=-csearch_path%3D{schema}"
    previous = os.environ.get("DATABASE_URL_DIRECT")
    os.environ["DATABASE_URL_DIRECT"] = scoped
    settings_module._settings = None
    try:
        config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
        config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "migrations"))
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL_DIRECT", None)
        else:
            os.environ["DATABASE_URL_DIRECT"] = previous
        settings_module._settings = None


@pytest.fixture(scope="session")
def db_schema() -> Iterator[tuple[str, str]]:
    """``(url, schema)`` for a freshly migrated schema, dropped after the run."""
    url = database_url()
    schema = f"test_{uuid.uuid4().hex[:10]}"
    admin = create_engine(_sync_url(url), poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except Exception as exc:  # noqa: BLE001 - an unreachable database is a skip
        admin.dispose()
        skip_or_fail(f"postgres unavailable: {type(exc).__name__}")
    try:
        _upgrade_head(url, schema)
        yield url, schema
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def db_engine(db_schema: tuple[str, str]) -> AsyncEngine:
    """An engine on the migrated schema.

    NullPool because each test runs on its own event loop, and a pooled async
    connection is tied to the loop that opened it.
    """
    url, schema = db_schema
    return create_async_engine(
        url, connect_args={"options": f"-csearch_path={schema}"}, poolclass=NullPool
    )


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose every write is rolled back when the test ends."""
    async with db_engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()
    await db_engine.dispose()


@pytest.fixture
async def db_committing(db_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions that really commit, then an emptied schema after the test.

    For code that commits across sessions by design — the outbox worker claims
    in one transaction and processes in another — which ``db_session`` cannot
    hold inside a single rolled-back transaction. Every table except the
    migration version is truncated afterwards, so the next test starts empty.
    """
    yield async_sessionmaker(db_engine, expire_on_commit=False)
    async with db_engine.begin() as connection:
        tables = (
            await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
                    " AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        names = ", ".join(f'"{name}"' for name in tables)
        if names:
            await connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    await db_engine.dispose()

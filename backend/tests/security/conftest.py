"""Shared fixtures for the security suites.

``harness`` is the HTTP harness. The real-Postgres fixtures come too, for the
tenancy sweep; a suite that does not request them never touches a database.
"""

from tests.db.fixtures import (
    db_engine,
    db_schema,
    db_session,
    pytest_asyncio_loop_factories,
)
from tests.security.harness import harness

__all__ = [
    "db_engine",
    "db_schema",
    "db_session",
    "harness",
    "pytest_asyncio_loop_factories",
]

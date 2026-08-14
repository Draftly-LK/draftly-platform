"""Shared test configuration.

Unit tests must not depend on a developer's local ``.env``. Settings are
constructed once and cached in ``src.platform.config``, so the required
variables are placed in the environment before any test imports trigger that
construction, and the cache is reset so a stale singleton from an earlier
import cannot leak in.

The database URLs point at a non-routable placeholder: unit tests never open a
connection, and a wrong-but-present value is safer than accidentally reading a
real one.
"""

from __future__ import annotations

import os

import pytest

_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/draftly_test",
    "DATABASE_URL_DIRECT": "postgresql+asyncpg://test:test@localhost:5432/draftly_test",
    "ENVIRONMENT": "test",
}

for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Drop the cached Settings between tests so env overrides take effect."""
    import src.platform.config as config

    config._settings = None
    yield
    config._settings = None

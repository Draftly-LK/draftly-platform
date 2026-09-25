"""How the real-Postgres suites find their database.

Opt-in, never accidental: ``tests/conftest.py`` pins ``DATABASE_URL`` to a
placeholder, and these suites only touch the database named in
``DRAFTLY_E2E_DATABASE_URL``. CI also sets ``DRAFTLY_E2E_REQUIRE_DATABASE=1``
so a missing database fails the run instead of quietly skipping.

    DRAFTLY_E2E_DATABASE_URL="postgresql+psycopg://..." uv run pytest -m integration
"""

from __future__ import annotations

import os
from typing import NoReturn

import pytest

E2E_URL_VAR = "DRAFTLY_E2E_DATABASE_URL"
REQUIRE_VAR = "DRAFTLY_E2E_REQUIRE_DATABASE"


def skip_or_fail(reason: str) -> NoReturn:
    """Skip locally; fail when the run has declared it needs the database."""
    if os.environ.get(REQUIRE_VAR) == "1":
        pytest.fail(f"{reason} ({REQUIRE_VAR}=1)")
    pytest.skip(reason)


def database_url() -> str:
    """The opt-in URL, normalised to the psycopg async driver.

    Use the **unpooled** endpoint: Neon's pooler rejects ``search_path`` as a
    startup parameter, and these suites isolate themselves in a schema.
    """
    url = os.environ.get(E2E_URL_VAR, "").strip()
    if not url:
        skip_or_fail(f"{E2E_URL_VAR} is not set; real-database tests are opt-in")
    if url.startswith("postgresql+asyncpg://"):
        pytest.skip("asyncpg is not a dependency; use the psycopg driver")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

"""Another tenant cannot reach a matter, or learn that it exists (Rule 1, §8.3).

Lawyer A owns a matter seeded through the real services. For every operation
the OpenAPI description scopes to a matter, lawyer B asks for A's matter and
for a matter that does not exist. The two answers must be indistinguishable:
same status, same error code, nothing of A's in the body. A 403 would already
be a leak, because it confirms there is something to be forbidden.

Real Postgres, real routes and services, the real token path.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

import src.platform.config as settings_module
from scripts.seed_synthetic_matter import SMOKE_MATTER_REFERENCE, seed
from src.main import create_app
from src.modules.auth.domain.models import Role
from src.platform.db.session import get_db
from tests.factories.constants import USER_B
from tests.security.harness import Harness

pytestmark = pytest.mark.integration

SUBJECT_A = "user_synthetic_owner"
SUBJECT_B = "user_synthetic_other_tenant"
MISSING_MATTER = "mat_synthetic_does_not_exist"


def _matter_scoped_operations() -> list[tuple[str, str]]:
    spec = create_app().openapi()
    return sorted(
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if operation.get("security") and "{matter_id}" in path
    )


MATTER_SCOPED = _matter_scoped_operations()


@dataclass(frozen=True)
class Tenancy:
    matter_id: str
    owner_id: str


@pytest.fixture
async def tenancy(
    harness: Harness,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Tenancy]:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    # Off by default, and while off every agent route refuses before its matter
    # check. On here, so the sweep reaches the check it exists to test.
    monkeypatch.setenv("MATTER_AGENT_ENABLED", "true")
    settings_module._settings = None
    report = await seed(db_session)
    # Commit the seed's savepoint, so a request that rolls back its own unit of
    # work cannot take the seeded matter with it. db_session still discards
    # everything when the test ends.
    await db_session.commit()

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db_session

    harness.app.dependency_overrides[get_db] = _session
    await harness.link(SUBJECT_A, report.lawyer_id, role=Role.APPROVER)
    await harness.link(SUBJECT_B, USER_B, role=Role.APPROVER)
    yield Tenancy(matter_id=report.matter_id, owner_id=report.lawyer_id)


async def _ask(harness: Harness, subject: str, method: str, path: str, matter_id: str) -> Response:
    url = re.sub(r"\{[^}]+\}", "synthetic", path.replace("{matter_id}", matter_id))
    headers = harness.signed_in(subject)
    body: dict[str, Any] | None = None
    if method in {"POST", "PUT", "PATCH"}:
        # Past the body and version checks where the route allows it, so the
        # answer comes from the tenancy check rather than from validation.
        headers["If-Match"] = '"1"'
        body = {}
    return await harness.client.request(method, url, json=body, headers=headers)


def _error_code(response: Response) -> str | None:
    try:
        return str(response.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return None


def test_the_sweep_found_the_matter_scoped_surface() -> None:
    assert len(MATTER_SCOPED) >= 30
    assert ("GET", "/api/v1/matters/{matter_id}") in MATTER_SCOPED


async def test_the_owner_can_read_the_seeded_matter(harness: Harness, tenancy: Tenancy) -> None:
    """Without this, every 404 below could just mean nothing was seeded."""
    response = await _ask(
        harness, SUBJECT_A, "GET", "/api/v1/matters/{matter_id}", tenancy.matter_id
    )

    assert response.status_code == 200
    assert response.json()["id"] == tenancy.matter_id


@pytest.mark.parametrize(("method", "path"), MATTER_SCOPED)
async def test_another_tenant_cannot_tell_the_matter_exists(
    harness: Harness, tenancy: Tenancy, method: str, path: str
) -> None:
    real = await _ask(harness, SUBJECT_B, method, path, tenancy.matter_id)
    missing = await _ask(harness, SUBJECT_B, method, path, MISSING_MATTER)

    assert not 200 <= real.status_code < 300, real.text
    assert real.status_code != 403, real.text
    assert (real.status_code, _error_code(real)) == (missing.status_code, _error_code(missing))
    assert tenancy.owner_id not in real.text
    assert SMOKE_MATTER_REFERENCE not in real.text
    if method == "GET" and path.count("{") == 1:
        assert real.status_code == 404


@pytest.mark.parametrize(
    ("conversation", "key"),
    [
        ("synthetic", ""),
        ("synthetic", "x" * 256),
        ("not/a/current/conversation", "synthetic-key"),
    ],
)
async def test_receipt_metadata_does_not_precede_tenancy(
    harness: Harness, tenancy: Tenancy, conversation: str, key: str
) -> None:
    responses = []
    for matter_id in [tenancy.matter_id, MISSING_MATTER]:
        response = await harness.client.get(
            f"/api/v1/matters/{matter_id}/agent/send-receipt",
            params={"conversationId": conversation},
            headers={**harness.signed_in(SUBJECT_B), "Idempotency-Key": key},
        )
        assert response.status_code == 404
        assert tenancy.owner_id not in response.text
        responses.append(_error_code(response))
    assert responses[0] == responses[1]

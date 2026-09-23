"""SqlMatterRepository against Postgres: the §5.3 repository baseline.

Matters are created through the real service, so every column the service
writes is exercised; the assertions are on what the repository stores and
returns.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import seed
from src.bootstrap import build_matter_service
from src.modules.auth.domain.models import Role
from src.modules.matter.application.matter_service import CreateMatterInput
from src.modules.matter.domain.errors import MatterStaleError
from src.modules.matter.domain.models import InstrumentLanguage, Matter
from src.modules.matter.infrastructure.repository import SqlMatterRepository
from src.platform.errors import ConflictError, DraftlyError
from src.platform.request_context import RequestContext
from tests.factories.constants import USER_B

pytestmark = pytest.mark.integration


@pytest.fixture
async def owner(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> RequestContext:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    report = await seed(db_session)
    return RequestContext(actor_id=report.lawyer_id, account_role=Role.APPROVER)


async def _create(session: AsyncSession, ctx: RequestContext, reference: str) -> Matter:
    return await build_matter_service(session).create_matter(
        ctx,
        CreateMatterInput(
            reference=reference,
            client_reference=f"{reference}-client (synthetic)",
            instrument_language=InstrumentLanguage.SI,
        ),
    )


async def test_a_created_matter_reads_back_whole(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    created = await _create(db_session, owner, "SYN/REPO/0001")

    stored = await SqlMatterRepository(db_session).get(owner.actor_id, created.id)

    assert stored == created
    assert stored is not None
    assert stored.instrument_language is InstrumentLanguage.SI
    assert stored.created_at.tzinfo is not None


async def test_another_user_reads_nothing(db_session: AsyncSession, owner: RequestContext) -> None:
    created = await _create(db_session, owner, "SYN/REPO/0002")

    assert await SqlMatterRepository(db_session).get(USER_B, created.id) is None


async def test_an_update_bumps_the_version_by_exactly_one(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    repository = SqlMatterRepository(db_session)
    created = await _create(db_session, owner, "SYN/REPO/0003")

    updated = await repository.update(
        replace(created, client_reference="changed (synthetic)"), created.version
    )

    assert updated.version == created.version + 1
    assert updated.client_reference == "changed (synthetic)"


async def test_an_update_from_a_stale_version_changes_nothing(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    repository = SqlMatterRepository(db_session)
    created = await _create(db_session, owner, "SYN/REPO/0004")
    await repository.update(replace(created, client_reference="first"), created.version)

    with pytest.raises(MatterStaleError):
        await repository.update(replace(created, client_reference="second"), created.version)

    stored = await repository.get(owner.actor_id, created.id)
    assert stored is not None
    assert (stored.client_reference, stored.version) == ("first", created.version + 1)


async def test_another_users_update_is_refused_as_stale(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    repository = SqlMatterRepository(db_session)
    created = await _create(db_session, owner, "SYN/REPO/0005")

    with pytest.raises(MatterStaleError):
        await repository.update(replace(created, user_id=USER_B), created.version)


async def test_a_reference_is_unique_per_owner(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    await _create(db_session, owner, "SYN/REPO/0006")

    with pytest.raises(ConflictError):
        await _create(db_session, owner, "SYN/REPO/0006")


async def test_paging_is_stable_when_a_matter_lands_between_pages(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    repository = SqlMatterRepository(db_session)
    for n in range(4):
        await _create(db_session, owner, f"SYN/PAGE/{n}")

    first, cursor = await repository.list_for_user(owner.actor_id, limit=2, cursor=None)
    await _create(db_session, owner, "SYN/PAGE/new")
    second, _ = await repository.list_for_user(owner.actor_id, limit=2, cursor=cursor)

    first_ids = [m.id for m in first]
    second_ids = [m.id for m in second]
    assert cursor is not None
    assert len(first_ids) == len(second_ids) == 2
    assert set(first_ids).isdisjoint(second_ids)
    assert all(m.reference != "SYN/PAGE/new" for m in first + second)


async def test_a_forged_list_cursor_is_refused(
    db_session: AsyncSession, owner: RequestContext
) -> None:
    with pytest.raises(DraftlyError) as caught:
        await SqlMatterRepository(db_session).list_for_user(
            owner.actor_id, limit=2, cursor="eyJ0IjogIjIwMjYtMDEtMDEiLCAiaWQiOiAieCJ9"
        )

    assert caught.value.http_status == 400

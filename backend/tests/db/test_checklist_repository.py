"""SqlChecklistRepository against Postgres: the §5.3 repository baseline.

Snapshots and items hang off a matter seeded through the real services.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.modules.content_governance.contracts import CollectionStatus, ResolutionStatus
from src.modules.task.domain.errors import ChecklistItemStaleError
from src.modules.task.infrastructure.repository import SqlChecklistRepository
from tests.factories.checklist import checklist_item, checklist_snapshot
from tests.factories.constants import NOW, USER_B

pytestmark = pytest.mark.integration


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


def _owned(matter: SeedReport) -> dict[str, str]:
    return {"user_id": matter.lawyer_id, "matter_id": matter.matter_id}


async def _snapshot_with_items(
    repository: SqlChecklistRepository, matter: SeedReport, count: int = 2
) -> list[str]:
    await repository.create_snapshot(
        checklist_snapshot(**_owned(matter), created_by=matter.lawyer_id)
    )
    items = [
        checklist_item(
            id=f"cli_synthetic_{n}",
            requirement_definition_id=f"R_SYNTHETIC_{n}",
            created_at=NOW + timedelta(seconds=n),
            **_owned(matter),
        )
        for n in range(count)
    ]
    await repository.create_items(items)
    return [item.id for item in items]


async def test_a_snapshot_reads_back_whole(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlChecklistRepository(db_session)
    created = await repository.create_snapshot(
        checklist_snapshot(
            **_owned(matter), created_by=matter.lawyer_id, module_definition_ids=("M_A", "M_B")
        )
    )

    stored = await repository.get_snapshot(matter.lawyer_id, created.id)

    assert stored == created
    assert stored is not None and stored.module_definition_ids == ("M_A", "M_B")


async def test_the_latest_snapshot_is_the_newest_and_fingerprints_find_theirs(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlChecklistRepository(db_session)
    await repository.create_snapshot(
        checklist_snapshot(**_owned(matter), created_by=matter.lawyer_id)
    )
    newer = await repository.create_snapshot(
        checklist_snapshot(
            **_owned(matter),
            id="cls_synthetic_0002",
            fingerprint="fp_synthetic_0002",
            created_at=NOW + timedelta(minutes=1),
            created_by=matter.lawyer_id,
            supersedes_id="cls_synthetic_0001",
        )
    )

    latest = await repository.latest_snapshot(matter.lawyer_id, matter.matter_id)
    by_fingerprint = await repository.find_snapshot_by_fingerprint(
        matter.lawyer_id, matter.matter_id, "fp_synthetic_0001"
    )

    assert latest == newer
    assert by_fingerprint is not None and by_fingerprint.id == "cls_synthetic_0001"


async def test_items_read_back_whole_and_in_order(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlChecklistRepository(db_session)
    ids = await _snapshot_with_items(repository, matter, count=3)

    items = await repository.list_items(matter.lawyer_id, "cls_synthetic_0001")

    assert [item.id for item in items] == ids
    assert items[0] == checklist_item(
        id=ids[0], requirement_definition_id="R_SYNTHETIC_0", **_owned(matter)
    )


async def test_another_user_reads_no_snapshot_and_no_item(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlChecklistRepository(db_session)
    ids = await _snapshot_with_items(repository, matter)

    assert await repository.get_snapshot(USER_B, "cls_synthetic_0001") is None
    assert await repository.latest_snapshot(USER_B, matter.matter_id) is None
    assert await repository.list_items(USER_B, "cls_synthetic_0001") == []
    assert await repository.get_item(USER_B, ids[0]) is None


async def test_an_item_update_bumps_the_version_by_exactly_one(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlChecklistRepository(db_session)
    ids = await _snapshot_with_items(repository, matter)
    item = await repository.get_item(matter.lawyer_id, ids[0])
    assert item is not None

    updated = await repository.update_item(
        replace(item, collection=CollectionStatus.RECEIVED), item.version
    )

    assert updated.version == item.version + 1
    assert updated.collection is CollectionStatus.RECEIVED


async def test_a_stale_item_update_changes_nothing(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlChecklistRepository(db_session)
    ids = await _snapshot_with_items(repository, matter)
    item = await repository.get_item(matter.lawyer_id, ids[0])
    assert item is not None
    await repository.update_item(replace(item, collection=CollectionStatus.RECEIVED), item.version)

    with pytest.raises(ChecklistItemStaleError):
        await repository.update_item(
            replace(item, resolution=ResolutionStatus.SATISFIED), item.version
        )

    stored = await repository.get_item(matter.lawyer_id, ids[0])
    assert stored is not None
    assert (stored.collection, stored.resolution, stored.version) == (
        CollectionStatus.RECEIVED,
        ResolutionStatus.OPEN,
        item.version + 1,
    )


async def test_another_user_cannot_update_an_item(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlChecklistRepository(db_session)
    ids = await _snapshot_with_items(repository, matter)
    item = await repository.get_item(matter.lawyer_id, ids[0])
    assert item is not None

    with pytest.raises(ChecklistItemStaleError):
        await repository.update_item(replace(item, user_id=USER_B), item.version)

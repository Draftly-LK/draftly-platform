"""The smoke seed writes through the real services, once, and only synthetic data.

Each test runs the seed inside ``db_session``, so its writes are rolled back.
The seed's own commit is the script's job, not ``seed()``'s.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SMOKE_MATTER_REFERENCE, seed
from src.modules.audit.infrastructure.orm import AuditEventRow
from src.modules.document.infrastructure.orm import SourceFileRow
from src.modules.matter.infrastructure.orm import MatterRow
from src.modules.party.infrastructure.orm import PartyRow

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _local_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploaded bytes land in the test's own directory, never in .data/."""
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))


async def _count(session: AsyncSession, row: type, **where: str) -> int:
    query = select(func.count()).select_from(row)
    for column, value in where.items():
        query = query.where(getattr(row, column) == value)
    return int((await session.execute(query)).scalar_one())


async def test_smoke_profile_writes_one_matter_two_parties_one_document(
    db_session: AsyncSession,
) -> None:
    report = await seed(db_session)

    owner = {"user_id": report.lawyer_id}
    assert report.created is True
    assert await _count(db_session, MatterRow, **owner) == 1
    assert await _count(db_session, PartyRow, **owner) == 2
    assert await _count(db_session, SourceFileRow, **owner, matter_id=report.matter_id) == 1


async def test_a_second_run_changes_nothing(db_session: AsyncSession) -> None:
    first = await seed(db_session)
    audit_after_first = await _count(db_session, AuditEventRow)

    second = await seed(db_session)

    assert second.created is False
    assert (second.lawyer_id, second.matter_id) == (first.lawyer_id, first.matter_id)
    assert await _count(db_session, MatterRow, user_id=first.lawyer_id) == 1
    assert await _count(db_session, PartyRow, user_id=first.lawyer_id) == 2
    assert await _count(db_session, AuditEventRow) == audit_after_first


async def test_every_seeded_write_is_audited_like_a_real_request(
    db_session: AsyncSession,
) -> None:
    report = await seed(db_session)

    rows = await db_session.execute(
        select(AuditEventRow.action).where(AuditEventRow.user_id == report.lawyer_id)
    )
    actions = sorted(rows.scalars())

    assert actions == sorted(
        [
            "user.provisioned",
            "matter.created",
            "party.created",
            "party.created",
            "rta.source-file.uploaded",
        ]
    )


async def test_seeded_values_are_labelled_synthetic(db_session: AsyncSession) -> None:
    report = await seed(db_session)

    names = (
        await db_session.execute(
            select(PartyRow.display_name).where(PartyRow.user_id == report.lawyer_id)
        )
    ).scalars()
    reference = (
        await db_session.execute(
            select(MatterRow.reference).where(MatterRow.id == report.matter_id)
        )
    ).scalar_one()

    assert all("(synthetic)" in name or "(demo)" in name for name in names)
    assert reference == SMOKE_MATTER_REFERENCE
    assert "(synthetic)" in reference


@pytest.mark.parametrize("environment", ["production", "staging", "preview"])
async def test_refuses_outside_local_test_and_ci(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ENVIRONMENT", environment)

    with pytest.raises(SystemExit, match="Refusing to seed"):
        await seed(db_session)

    assert await _count(db_session, MatterRow) == 0

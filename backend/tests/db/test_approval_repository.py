"""SqlApprovalRepository against Postgres: approvals are append-only records.

An approval is never edited; a new one revokes the old by pointing at it.
These hold the rules that make that trustworthy: the current approval skips
revoked ones, a revocation cannot be rewritten or aimed at itself, every
approval carries its hashes, and no one reads another user's approvals.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.modules.approval.domain.models import Approval
from src.modules.approval.infrastructure.repository import SqlApprovalRepository
from src.modules.approval.tests.fakes import approval_record
from tests.factories.constants import NOW, USER_B

pytestmark = pytest.mark.integration

TARGET = "frm_synthetic"


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


def _approval(matter: SeedReport, n: int, **overrides: object) -> Approval:
    record = replace(
        approval_record(approval_id=f"apr_synthetic_{n}"),
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        approver_id=matter.lawyer_id,
        target_id=TARGET,
        created_at=NOW + timedelta(seconds=n),
    )
    return replace(record, **overrides)  # type: ignore[arg-type]


async def test_an_approval_reads_back_whole(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlApprovalRepository(db_session)
    created = await repository.create(_approval(matter, 1))

    assert await repository.current_for_target(matter.lawyer_id, TARGET) == created


async def test_the_current_approval_skips_a_revoked_one(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlApprovalRepository(db_session)
    await repository.create(_approval(matter, 1))
    newer = await repository.create(_approval(matter, 2))

    await repository.revoke(matter.lawyer_id, "apr_synthetic_1", newer.id)

    assert await repository.current_for_target(matter.lawyer_id, TARGET) == newer


async def test_a_revocation_cannot_be_rewritten(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    """The first successor is the one that revoked it; a later call changes nothing."""
    repository = SqlApprovalRepository(db_session)
    for n in (1, 2, 3):
        await repository.create(_approval(matter, n))

    await repository.revoke(matter.lawyer_id, "apr_synthetic_1", "apr_synthetic_2")
    await repository.revoke(matter.lawyer_id, "apr_synthetic_1", "apr_synthetic_3")

    approvals, _ = await repository.list_for_target(matter.lawyer_id, TARGET, limit=10, cursor=None)
    first = next(a for a in approvals if a.id == "apr_synthetic_1")
    assert first.revoked_by_approval_id == "apr_synthetic_2"


async def test_another_user_cannot_revoke(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlApprovalRepository(db_session)
    created = await repository.create(_approval(matter, 1))

    await repository.revoke(USER_B, created.id, "apr_synthetic_forged")

    assert await repository.current_for_target(matter.lawyer_id, TARGET) == created


async def test_another_user_reads_no_approval(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlApprovalRepository(db_session)
    await repository.create(_approval(matter, 1))

    assert await repository.current_for_target(USER_B, TARGET) is None
    assert await repository.list_for_target(USER_B, TARGET, limit=10, cursor=None) == ([], None)


async def test_an_approval_cannot_revoke_itself(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlApprovalRepository(db_session)
    created = await repository.create(_approval(matter, 1))

    with pytest.raises(IntegrityError, match="ck_approval_revocation_is_another_approval"):
        await repository.revoke(matter.lawyer_id, created.id, created.id)


@pytest.mark.parametrize(
    "hash_field", ["declaration_text_hash", "snapshot_hash", "confirmed_fact_hash"]
)
async def test_an_approval_without_its_hashes_is_refused(
    db_session: AsyncSession, matter: SeedReport, hash_field: str
) -> None:
    """An approval that pins nothing proves nothing about what was approved."""
    with pytest.raises(IntegrityError, match="ck_approval_hashes_present"):
        await SqlApprovalRepository(db_session).create(_approval(matter, 1, **{hash_field: ""}))

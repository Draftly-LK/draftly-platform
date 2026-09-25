"""SqlGeneratedFormRepository against Postgres: the §5.3 baseline.

A generated form is what a lawyer approves. A lost version check here would
let a stale draft overwrite an approved one.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.modules.content_governance.contracts import GeneratedFormState
from src.modules.draft.domain.errors import GeneratedFormStaleError
from src.modules.draft.domain.models import GeneratedForm
from src.modules.draft.infrastructure.repository import SqlGeneratedFormRepository
from tests.factories.constants import NOW, USER_B

pytestmark = pytest.mark.integration

TEMPLATE = "rta.reg.2022.form.08"


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


def _form(matter: SeedReport, n: int = 1) -> GeneratedForm:
    at = NOW + timedelta(seconds=n)
    return GeneratedForm(
        id=f"frm_synthetic_{n}",
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        template_id=TEMPLATE,
        template_version="synthetic",
        form_version=n,
        state=GeneratedFormState.GENERATED_DRAFT,
        subtype_id="lk.rta.instrument.transfer_sale",
        rule_pack_version="synthetic",
        created_by=matter.lawyer_id,
        created_at=at,
        updated_at=at,
    )


async def test_a_form_reads_back_whole(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    created = await repository.create_form(_form(matter))

    assert await repository.get_form(matter.lawyer_id, created.id) == created


async def test_another_user_reads_no_form(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    await repository.create_form(_form(matter))

    assert await repository.get_form(USER_B, "frm_synthetic_1") is None
    assert await repository.list_forms(USER_B, matter.matter_id, limit=10, cursor=None) == (
        [],
        None,
    )


async def test_the_next_form_version_follows_the_highest(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    assert await repository.next_form_version(matter.lawyer_id, matter.matter_id, TEMPLATE) == 1
    await repository.create_form(_form(matter, 1))
    await repository.create_form(_form(matter, 2))

    assert await repository.next_form_version(matter.lawyer_id, matter.matter_id, TEMPLATE) == 3


async def test_a_form_update_bumps_the_version_by_exactly_one(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    created = await repository.create_form(_form(matter))

    updated = await repository.update_form(
        replace(created, state=GeneratedFormState.REVIEW_READY), created.version
    )

    assert updated.version == created.version + 1
    assert updated.state is GeneratedFormState.REVIEW_READY


async def test_a_stale_form_update_changes_nothing(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    created = await repository.create_form(_form(matter))
    await repository.update_form(
        replace(
            created,
            state=GeneratedFormState.APPROVED,
            approval_id="apr_synthetic",
            # The table refuses an APPROVED form without the approved hash.
            approved_artifact_hash="0" * 64,
        ),
        created.version,
    )

    with pytest.raises(GeneratedFormStaleError):
        await repository.update_form(
            replace(created, state=GeneratedFormState.GENERATED_DRAFT), created.version
        )

    stored = await repository.get_form(matter.lawyer_id, created.id)
    assert stored is not None
    assert (stored.state, stored.approval_id) == (GeneratedFormState.APPROVED, "apr_synthetic")


async def test_another_user_cannot_update_a_form(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    created = await repository.create_form(_form(matter))

    with pytest.raises(GeneratedFormStaleError):
        await repository.update_form(
            replace(created, user_id=USER_B, state=GeneratedFormState.APPROVED), created.version
        )


async def test_forms_page_without_repeating(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlGeneratedFormRepository(db_session)
    for n in range(1, 6):
        await repository.create_form(_form(matter, n))

    first, cursor = await repository.list_forms(
        matter.lawyer_id, matter.matter_id, limit=2, cursor=None
    )
    second, _ = await repository.list_forms(
        matter.lawyer_id, matter.matter_id, limit=2, cursor=cursor
    )

    assert cursor is not None
    assert len(first) == len(second) == 2
    assert {f.id for f in first}.isdisjoint({f.id for f in second})

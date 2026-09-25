"""Party repositories against Postgres (§5.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.bootstrap import build_party_field_encryption
from src.modules.party.domain.models import (
    ConfidentialityLevel,
    ScreeningMatchDetail,
    ScreeningOutcome,
    ScreeningResult,
)
from src.modules.party.infrastructure.orm import PartyRow, ScreeningMatchDetailRow
from src.modules.party.infrastructure.repository import SqlIdentityEvidenceRepository
from tests.factories.constants import NOW

pytestmark = pytest.mark.integration


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


async def test_a_screening_is_stored_with_its_match_detail(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    """The detail row's foreign key points at the result, so the result must
    reach Postgres first."""
    party_id = (
        await db_session.execute(
            select(PartyRow.id).where(PartyRow.user_id == matter.lawyer_id).limit(1)
        )
    ).scalar_one()
    repository = SqlIdentityEvidenceRepository(db_session, build_party_field_encryption())
    result = ScreeningResult(
        id="scr_synthetic_1",
        party_id=party_id,
        list_version="synthetic-list-v1",
        provider_ref="manual",
        outcome=ScreeningOutcome.POTENTIAL_MATCH,
        match_count=1,
        reviewed_by=None,
        reviewed_at=None,
        disposition_reason=None,
        confidentiality_level=ConfidentialityLevel.STANDARD,
        created_at=NOW,
    )

    await repository.append_screening(
        matter.lawyer_id,
        result,
        ScreeningMatchDetail(
            screening_result_id=result.id,
            match_narrative="Synthetic name overlap (synthetic)",
            list_entry_ref="SYN-LIST-0001",
        ),
    )

    detail = (
        await db_session.execute(
            select(ScreeningMatchDetailRow).where(
                ScreeningMatchDetailRow.screening_result_id == result.id
            )
        )
    ).scalar_one()
    assert detail.list_entry_ref == "SYN-LIST-0001"

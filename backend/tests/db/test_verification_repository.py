"""SqlVerificationRepository against Postgres: facts are versioned, never edited.

Facts are what drafts are filled from. A fact's value is never changed in
place; a correction supersedes it. And the confirmed tier only ever holds
what a lawyer confirmed: no machine confidence is enough (Appendix A,
refusal 5).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.modules.content_governance.contracts import FactStatus
from src.modules.verification.domain.models import ExtractedFact
from src.modules.verification.infrastructure.repository import (
    SqlConfirmedFactReader,
    SqlVerificationRepository,
)
from tests.factories.constants import NOW, USER_B

pytestmark = pytest.mark.integration

BUYER = "rta.party.transferee_name"
EXTENT = "rta.parcel.extent"


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


def _fact(matter: SeedReport, n: int, **overrides: Any) -> ExtractedFact:
    fact = ExtractedFact(
        id=f"fact_synthetic_{n}",
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        fact_type_id=BUYER,
        value="Synthetic Buyer Two",
        status=FactStatus.EXTRACTED_CANDIDATE,
        created_at=NOW + timedelta(seconds=n),
        evidence_reference_ids=(f"ev_synthetic_{n}",),
    )
    fact = replace(fact, **overrides)
    if fact.status in {FactStatus.LAWYER_CONFIRMED, FactStatus.LOCKED_FOR_FORM}:
        fact = replace(fact, reviewed_by=matter.lawyer_id, reviewed_at=fact.created_at)
    return fact


async def test_a_fact_reads_back_whole_whatever_its_value_shape(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlVerificationRepository(db_session)
    structured = {"hectares": "0.0500", "perches": None}
    created = await repository.create_fact(
        _fact(matter, 1, fact_type_id=EXTENT, value=structured, model_reported_confidence=0.91)
    )

    stored = await repository.get_fact(matter.lawyer_id, created.id)

    assert stored == created
    assert stored is not None and stored.value == structured


async def test_another_user_reads_no_fact(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlVerificationRepository(db_session)
    await repository.create_fact(_fact(matter, 1))

    assert await repository.get_fact(USER_B, "fact_synthetic_1") is None
    assert await repository.list_all_facts(USER_B, matter.matter_id) == []


async def test_superseding_keeps_the_old_value_and_hides_it_from_live_facts(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlVerificationRepository(db_session)
    await repository.create_fact(_fact(matter, 1))
    await repository.create_fact(
        _fact(
            matter,
            2,
            value="Corrected Buyer (synthetic)",
            version=2,
            supersedes_fact_id="fact_synthetic_1",
        )
    )

    await repository.mark_superseded(
        matter.lawyer_id, "fact_synthetic_1", superseded_by_fact_id="fact_synthetic_2"
    )

    old = await repository.get_fact(matter.lawyer_id, "fact_synthetic_1")
    live = await repository.list_live_facts(matter.lawyer_id, matter.matter_id)
    history = await repository.list_all_facts(matter.lawyer_id, matter.matter_id)
    assert old is not None
    assert (old.value, old.status) == ("Synthetic Buyer Two", FactStatus.SUPERSEDED)
    assert [f.id for f in live] == ["fact_synthetic_2"]
    assert {f.id for f in history} == {"fact_synthetic_1", "fact_synthetic_2"}


async def test_another_user_cannot_supersede_or_lock_a_fact(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlVerificationRepository(db_session)
    created = await repository.create_fact(_fact(matter, 1, status=FactStatus.LAWYER_CONFIRMED))

    await repository.mark_superseded(USER_B, created.id, superseded_by_fact_id="fact_forged")
    await repository.lock_for_form(USER_B, created.id, form_id="frm_forged")

    assert await repository.get_fact(matter.lawyer_id, created.id) == created


async def test_the_next_version_follows_the_highest_for_its_type(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlVerificationRepository(db_session)
    await repository.create_fact(_fact(matter, 1, version=1))
    await repository.create_fact(_fact(matter, 2, version=2))
    await repository.create_fact(_fact(matter, 3, fact_type_id=EXTENT, version=1))

    assert await repository.next_version(matter.lawyer_id, matter.matter_id, BUYER) == 3
    assert await repository.next_version(matter.lawyer_id, matter.matter_id, EXTENT) == 2


@pytest.mark.parametrize(
    "status",
    [
        FactStatus.EXTRACTED_CANDIDATE,
        FactStatus.CORROBORATED,
        FactStatus.REVIEW_REQUIRED,
    ],
)
async def test_no_machine_confidence_makes_an_unreviewed_fact_confirmed(
    db_session: AsyncSession, matter: SeedReport, status: FactStatus
) -> None:
    """Refusal 5: a 0.99-confidence candidate is still a candidate."""
    await SqlVerificationRepository(db_session).create_fact(
        _fact(matter, 1, status=status, model_reported_confidence=0.99)
    )

    summary = await SqlConfirmedFactReader(db_session).summarise(matter.lawyer_id, matter.matter_id)

    assert BUYER not in summary.confirmed


async def test_the_confirmed_tier_holds_the_latest_lawyer_confirmed_version(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlVerificationRepository(db_session)
    await repository.create_fact(_fact(matter, 1, status=FactStatus.LAWYER_CONFIRMED, version=1))
    await repository.create_fact(
        _fact(
            matter,
            2,
            value="Later Buyer (synthetic)",
            status=FactStatus.LAWYER_CONFIRMED,
            version=2,
        )
    )
    await repository.create_fact(
        _fact(matter, 3, fact_type_id=EXTENT, value="0.1", status=FactStatus.CONFLICTED)
    )

    summary = await SqlConfirmedFactReader(db_session).summarise(matter.lawyer_id, matter.matter_id)

    assert summary.confirmed[BUYER].fact_id == "fact_synthetic_2"
    assert summary.confirmed[BUYER].value == "Later Buyer (synthetic)"
    assert summary.conflicted_fact_type_ids == (EXTENT,)
    assert EXTENT not in summary.confirmed


@pytest.mark.parametrize("status", [FactStatus.LAWYER_CONFIRMED, FactStatus.LOCKED_FOR_FORM])
async def test_a_confirmed_fact_without_a_reviewer_is_refused(
    db_session: AsyncSession, matter: SeedReport, status: FactStatus
) -> None:
    """Nothing reaches a confirmed status anonymously, not even a direct write."""
    anonymous = replace(_fact(matter, 1), status=status)

    with pytest.raises(IntegrityError, match="ck_extracted_fact_confirmation_requires_reviewer"):
        await SqlVerificationRepository(db_session).create_fact(anonymous)

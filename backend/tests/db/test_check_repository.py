"""SqlCheckRepository's legal issues against Postgres: the §5.3 baseline.

Issues are what gate draft generation and approval, so a lost version check
or a cross-tenant read here would let a blocker be decided twice or seen by
the wrong lawyer.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.modules.check.domain.errors import LegalIssueStaleError
from src.modules.check.domain.models import LegalIssue
from src.modules.check.infrastructure.repository import SqlCheckRepository
from src.modules.content_governance.contracts import BlockerKind, IssueSeverity, IssueState
from tests.factories.constants import NOW, USER_B

pytestmark = pytest.mark.integration


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


def _issue(matter: SeedReport, n: int = 0, **overrides: object) -> LegalIssue:
    at = NOW + timedelta(seconds=n)
    issue = LegalIssue(
        id=f"iss_synthetic_{n}",
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        issue_type_id="rta.issue.synthetic",
        severity=IssueSeverity.BLOCKING,
        blocker_kind=BlockerKind.STATUTORY,
        state=IssueState.OPEN,
        summary_key="rta.issue.synthetic.summary",
        created_at=at,
        updated_at=at,
        source_record_ids=("fact_synthetic_1",),
        evidence_reference_ids=("ev_synthetic_1", "ev_synthetic_2"),
    )
    return replace(issue, **overrides)  # type: ignore[arg-type]


async def test_an_issue_reads_back_whole(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlCheckRepository(db_session)
    created = await repository.create_issue(_issue(matter))

    stored = await repository.get_issue(matter.lawyer_id, created.id)

    assert stored == created
    assert stored is not None and stored.evidence_reference_ids == (
        "ev_synthetic_1",
        "ev_synthetic_2",
    )


async def test_another_user_reads_no_issue(db_session: AsyncSession, matter: SeedReport) -> None:
    repository = SqlCheckRepository(db_session)
    await repository.create_issue(_issue(matter))

    assert await repository.get_issue(USER_B, "iss_synthetic_0") is None
    assert await repository.list_all_issues(USER_B, matter.matter_id) == []


async def test_an_issue_update_bumps_the_version_by_exactly_one(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlCheckRepository(db_session)
    created = await repository.create_issue(_issue(matter))

    updated = await repository.update_issue(
        replace(created, state=IssueState.TRIAGED), created.version
    )

    assert updated.version == created.version + 1
    assert updated.state is IssueState.TRIAGED


async def test_a_stale_issue_update_changes_nothing(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    """Two lawyers deciding one blocker: the second decision must not land."""
    repository = SqlCheckRepository(db_session)
    created = await repository.create_issue(_issue(matter))
    await repository.update_issue(replace(created, state=IssueState.TRIAGED), created.version)

    with pytest.raises(LegalIssueStaleError):
        await repository.update_issue(
            replace(created, state=IssueState.RESOLVED, resolution_reason="late"), created.version
        )

    stored = await repository.get_issue(matter.lawyer_id, created.id)
    assert stored is not None
    assert (stored.state, stored.resolution_reason) == (IssueState.TRIAGED, None)


async def test_another_user_cannot_update_an_issue(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlCheckRepository(db_session)
    created = await repository.create_issue(_issue(matter))

    with pytest.raises(LegalIssueStaleError):
        await repository.update_issue(
            replace(created, user_id=USER_B, state=IssueState.RESOLVED), created.version
        )


async def test_issue_lists_filter_and_page_without_repeating(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    repository = SqlCheckRepository(db_session)
    for n in range(5):
        severity = IssueSeverity.BLOCKING if n % 2 == 0 else IssueSeverity.WARNING
        await repository.create_issue(_issue(matter, n, severity=severity))

    first, cursor = await repository.list_issues(
        matter.lawyer_id, matter.matter_id, severity=None, state=None, limit=2, cursor=None
    )
    second, _ = await repository.list_issues(
        matter.lawyer_id, matter.matter_id, severity=None, state=None, limit=2, cursor=cursor
    )
    blocking, _ = await repository.list_issues(
        matter.lawyer_id,
        matter.matter_id,
        severity=IssueSeverity.BLOCKING,
        state=None,
        limit=10,
        cursor=None,
    )

    assert cursor is not None
    assert {i.id for i in first}.isdisjoint({i.id for i in second})
    assert len(first) == len(second) == 2
    assert {i.id for i in blocking} == {"iss_synthetic_0", "iss_synthetic_2", "iss_synthetic_4"}

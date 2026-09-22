"""ChecklistService on Postgres: compiling, deciding, and what still blocks (F8).

The checklist is compiled from the routed modules and decided by a lawyer
item by item. These drive the real service over the real repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.bootstrap import build_checklist_service
from src.modules.audit.infrastructure.orm import AuditEventRow
from src.modules.content_governance.contracts import (
    TRANSFER_SALE_SUBTYPE_ID,
    ApplicabilityStatus,
    CompilerInput,
    ResolutionStatus,
    require_requirement,
)
from src.modules.matter.domain import routing
from src.modules.task.application.checklist_service import ChecklistService
from src.modules.task.domain.errors import (
    ChecklistItemStaleError,
    SatisfactionIsComputedError,
    StatutoryRequirementNotWaivableError,
)

pytestmark = pytest.mark.integration

TRANSFER = CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID)
WITH_MORTGAGE = CompilerInput(
    subtype_id=TRANSFER_SALE_SUBTYPE_ID,
    activated_conditional_module_ids=frozenset({routing.MODULE_MORTGAGE}),
)


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


async def _compile(
    service: ChecklistService, matter: SeedReport, compiler_input: CompilerInput = TRANSFER
) -> str:
    snapshot_id, _ = await service.compile_snapshot(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        compiler_input=compiler_input,
        actor_id=matter.lawyer_id,
        correlation_id="corr_synthetic",
    )
    return snapshot_id


async def _compiled_audits(session: AsyncSession, matter: SeedReport) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(AuditEventRow)
                .where(
                    AuditEventRow.matter_id == matter.matter_id,
                    AuditEventRow.action == "rta.checklist.compiled",
                )
            )
        ).scalar_one()
    )


# ── Compiling ───────────────────────────────────────────────────────────────


async def test_compiling_the_same_inputs_twice_keeps_one_snapshot(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    service = build_checklist_service(db_session)

    first = await _compile(service, matter)
    again = await _compile(service, matter)

    assert again == first
    assert await _compiled_audits(db_session, matter) == 1


async def test_a_new_module_compiles_a_new_snapshot_that_supersedes_the_old(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    service = build_checklist_service(db_session)
    first = await _compile(service, matter)

    second = await _compile(service, matter, WITH_MORTGAGE)

    before = await service.get_checklist(
        user_id=matter.lawyer_id, matter_id=matter.matter_id, snapshot_id=first
    )
    after = await service.get_checklist(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    assert second != first
    assert after.snapshot.id == second
    assert after.snapshot.supersedes_id == first
    assert len(after.items) > len(before.items)
    assert await _compiled_audits(db_session, matter) == 2


# ── Deciding ────────────────────────────────────────────────────────────────


async def _first_item(
    service: ChecklistService, matter: SeedReport, *, waivable: bool
) -> tuple[str, int, str]:
    """(item id, version, requirement id) of the first item of the wanted kind."""
    view = await service.get_checklist(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    for entry in view.items:
        requirement = require_requirement(entry.item.requirement_definition_id)
        if requirement.waivable is waivable:
            return entry.item.id, entry.item.version, requirement.id
    raise AssertionError(f"no {'waivable' if waivable else 'statutory'} item compiled")


async def test_a_statutory_item_cannot_be_waived_through_the_service(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    service = build_checklist_service(db_session)
    await _compile(service, matter)
    item_id, version, _ = await _first_item(service, matter, waivable=False)

    with pytest.raises(StatutoryRequirementNotWaivableError):
        await service.decide_satisfaction(
            user_id=matter.lawyer_id,
            matter_id=matter.matter_id,
            item_id=item_id,
            actor_id=matter.lawyer_id,
            correlation_id="c",
            expected_version=version,
            applicability=ApplicabilityStatus.WAIVED_BY_LAWYER,
            reason="Synthetic reason",
        )


async def test_satisfied_cannot_be_chosen_through_the_service(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    service = build_checklist_service(db_session)
    await _compile(service, matter)
    item_id, version, _ = await _first_item(service, matter, waivable=True)

    with pytest.raises(SatisfactionIsComputedError):
        await service.decide_satisfaction(
            user_id=matter.lawyer_id,
            matter_id=matter.matter_id,
            item_id=item_id,
            actor_id=matter.lawyer_id,
            correlation_id="c",
            expected_version=version,
            resolution=ResolutionStatus.SATISFIED,
        )


@pytest.mark.parametrize(
    "resolution", [ResolutionStatus.CLOSED, ResolutionStatus.EXCEPTION_ACCEPTED]
)
async def test_a_hand_set_resolution_does_not_unblock_a_statutory_item(
    db_session: AsyncSession, matter: SeedReport, resolution: ResolutionStatus
) -> None:
    """Blocking is computed from the evidence, not read from a stored label."""
    service = build_checklist_service(db_session)
    await _compile(service, matter)
    item_id, version, requirement_id = await _first_item(service, matter, waivable=False)
    blocking_before = await service.blocking_requirement_ids(
        user_id=matter.lawyer_id, matter_id=matter.matter_id
    )

    await service.decide_satisfaction(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        item_id=item_id,
        actor_id=matter.lawyer_id,
        correlation_id="c",
        expected_version=version,
        resolution=resolution,
        reason="Synthetic reason",
    )

    blocking_after = await service.blocking_requirement_ids(
        user_id=matter.lawyer_id, matter_id=matter.matter_id
    )
    if requirement_id in blocking_before:
        assert requirement_id in blocking_after
    assert set(blocking_before) <= set(blocking_after)


async def test_a_decision_from_a_stale_version_is_refused(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    service = build_checklist_service(db_session)
    await _compile(service, matter)
    item_id, version, _ = await _first_item(service, matter, waivable=True)
    await service.decide_satisfaction(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        item_id=item_id,
        actor_id=matter.lawyer_id,
        correlation_id="c",
        expected_version=version,
        applicability=ApplicabilityStatus.WAIVED_BY_LAWYER,
        reason="Synthetic reason",
    )

    with pytest.raises(ChecklistItemStaleError):
        await service.decide_satisfaction(
            user_id=matter.lawyer_id,
            matter_id=matter.matter_id,
            item_id=item_id,
            actor_id=matter.lawyer_id,
            correlation_id="c",
            expected_version=version,
            applicability=ApplicabilityStatus.REQUIRED,
        )


async def test_a_fresh_checklist_has_blocking_requirements(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    """Nothing has been collected, so the statutory items must block approval."""
    service = build_checklist_service(db_session)
    await _compile(service, matter)

    blocking = await service.blocking_requirement_ids(
        user_id=matter.lawyer_id, matter_id=matter.matter_id
    )

    assert blocking

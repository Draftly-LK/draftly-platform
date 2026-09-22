"""MatterService on Postgres: intake, answers and the exact-instrument decision (F8).

The service had no test file. It runs here with its real repositories, audit
and checklist wiring, as bootstrap builds it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.bootstrap import build_matter_service
from src.modules.audit.infrastructure.orm import AuditEventRow
from src.modules.auth.domain.models import Role
from src.modules.content_governance.contracts import (
    TRANSFER_SALE_SUBTYPE_ID,
    MatterState,
    SubtypeDecisionStatus,
    TriState,
)
from src.modules.matter.application.matter_service import CreateMatterInput, MatterService
from src.modules.matter.domain.errors import (
    InvalidAnswerValueError,
    LegalBasisRequiredError,
    MatterNotFoundError,
    MatterStaleError,
    UnknownQuestionError,
    UnknownSubtypeError,
)
from src.platform.errors import NotFoundError
from src.platform.request_context import RequestContext
from tests.factories.constants import USER_B

pytestmark = pytest.mark.integration

DECLARED_INSTRUMENT = "lk.rta.instrument.other_declared_instrument"


@pytest.fixture
async def owner(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[MatterService, RequestContext, SeedReport]:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    report = await seed(db_session)
    ctx = RequestContext(actor_id=report.lawyer_id, account_role=Role.APPROVER, correlation_id="c")
    return build_matter_service(db_session), ctx, report


async def _actions(session: AsyncSession, matter_id: str) -> list[str]:
    rows = await session.execute(
        select(AuditEventRow.action)
        .where(AuditEventRow.matter_id == matter_id)
        .order_by(AuditEventRow.timestamp)
    )
    return list(rows.scalars())


# ── Creating a matter ───────────────────────────────────────────────────────


async def test_a_new_matter_starts_in_intake_with_no_subtype_chosen(
    db_session: AsyncSession, owner: tuple[MatterService, RequestContext, SeedReport]
) -> None:
    """Creation never defaults the exact instrument (§12.4)."""
    service, ctx, _ = owner

    matter = await service.create_matter(ctx, CreateMatterInput(reference="SYN/SVC/0001"))

    assert matter.rta_state is MatterState.INTAKE_DRAFT
    assert matter.subtype_id is None
    assert matter.subtype_decision_status is SubtypeDecisionStatus.PROVISIONAL
    assert matter.responsible_lawyer_id == ctx.actor_id
    assert await _actions(db_session, matter.id) == ["matter.created"]


async def test_another_user_cannot_read_a_matter(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, _, report = owner
    other = RequestContext(actor_id=USER_B, account_role=Role.APPROVER)

    with pytest.raises(MatterNotFoundError):
        await service.get_matter(other, report.matter_id)


# ── Answers ─────────────────────────────────────────────────────────────────


async def test_a_new_answer_supersedes_the_old_one_without_erasing_it(
    db_session: AsyncSession, owner: tuple[MatterService, RequestContext, SeedReport]
) -> None:
    service, ctx, report = owner
    first = await service.save_answer(
        ctx, report.matter_id, "Q10_MORTGAGE", value=TriState.UNKNOWN.value, lawyer_confirmed=False
    )

    second = await service.save_answer(
        ctx, report.matter_id, "Q10_MORTGAGE", value=TriState.YES.value, lawyer_confirmed=True
    )

    assert second.supersedes_id == first.id
    live = await service.list_answers(ctx, report.matter_id)
    assert [(a.id, a.value) for a in live if a.question_definition_id == "Q10_MORTGAGE"] == [
        (second.id, TriState.YES.value)
    ]
    actions = await _actions(db_session, report.matter_id)
    assert "rta.intake.answer-superseded" in actions


async def test_an_unknown_question_is_refused(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, ctx, report = owner

    with pytest.raises(UnknownQuestionError):
        await service.save_answer(
            ctx, report.matter_id, "Q99_SYNTHETIC", value="YES", lawyer_confirmed=True
        )


async def test_a_value_the_question_does_not_offer_is_refused(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, ctx, report = owner

    with pytest.raises(InvalidAnswerValueError):
        await service.save_answer(
            ctx, report.matter_id, "Q10_MORTGAGE", value="PROBABLY", lawyer_confirmed=True
        )


async def test_another_user_cannot_answer(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, _, report = owner
    other = RequestContext(actor_id=USER_B, account_role=Role.APPROVER)

    with pytest.raises(NotFoundError):
        await service.save_answer(
            other, report.matter_id, "Q10_MORTGAGE", value="YES", lawyer_confirmed=True
        )


# ── Confirming the exact instrument ─────────────────────────────────────────


async def test_the_responsible_lawyer_confirms_the_subtype(
    db_session: AsyncSession, owner: tuple[MatterService, RequestContext, SeedReport]
) -> None:
    service, ctx, report = owner
    matter = await service.get_matter(ctx, report.matter_id)

    confirmed = await service.confirm_subtype(
        ctx, report.matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=matter.version
    )

    assert confirmed.subtype_id == TRANSFER_SALE_SUBTYPE_ID
    assert confirmed.subtype_decision_status is SubtypeDecisionStatus.LAWYER_CONFIRMED
    assert confirmed.version == matter.version + 1
    assert "rta.matter.subtype-confirmed" in await _actions(db_session, report.matter_id)


async def test_confirming_from_a_stale_version_changes_nothing(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, ctx, report = owner
    matter = await service.get_matter(ctx, report.matter_id)
    await service.confirm_subtype(
        ctx, report.matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=matter.version
    )

    with pytest.raises(MatterStaleError):
        await service.confirm_subtype(
            ctx,
            report.matter_id,
            subtype_id=DECLARED_INSTRUMENT,
            declared_legal_basis="Synthetic basis",
            expected_version=matter.version,
        )

    assert (await service.get_matter(ctx, report.matter_id)).subtype_id == TRANSFER_SALE_SUBTYPE_ID


async def test_an_unknown_subtype_is_refused(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, ctx, report = owner
    matter = await service.get_matter(ctx, report.matter_id)

    with pytest.raises(UnknownSubtypeError):
        await service.confirm_subtype(
            ctx,
            report.matter_id,
            subtype_id="lk.rta.instrument.synthetic",
            expected_version=matter.version,
        )


@pytest.mark.parametrize("basis", [None, "", "   "])
async def test_a_declared_instrument_needs_its_legal_basis(
    owner: tuple[MatterService, RequestContext, SeedReport], basis: str | None
) -> None:
    service, ctx, report = owner
    matter = await service.get_matter(ctx, report.matter_id)

    with pytest.raises(LegalBasisRequiredError):
        await service.confirm_subtype(
            ctx,
            report.matter_id,
            subtype_id=DECLARED_INSTRUMENT,
            declared_legal_basis=basis,
            expected_version=matter.version,
        )


async def test_another_user_cannot_confirm_the_subtype(
    owner: tuple[MatterService, RequestContext, SeedReport],
) -> None:
    service, ctx, report = owner
    matter = await service.get_matter(ctx, report.matter_id)
    other = RequestContext(actor_id=USER_B, account_role=Role.APPROVER)

    with pytest.raises(NotFoundError):
        await service.confirm_subtype(
            other,
            report.matter_id,
            subtype_id=TRANSFER_SALE_SUBTYPE_ID,
            expected_version=matter.version,
        )


# ── State transitions ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "target", [MatterState.APPROVED, MatterState.EXPORTED, MatterState.REGISTERED]
)
async def test_intake_cannot_jump_to_a_late_state(
    owner: tuple[MatterService, RequestContext, SeedReport], target: MatterState
) -> None:
    from src.modules.matter.domain.errors import IllegalMatterTransitionError

    service, ctx, report = owner
    matter = await service.get_matter(ctx, report.matter_id)

    with pytest.raises(IllegalMatterTransitionError):
        await service.transition(
            ctx, report.matter_id, target=target, expected_version=matter.version
        )

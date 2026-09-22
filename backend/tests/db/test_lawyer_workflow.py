"""Appendix A's refusals, through the real services on Postgres (§4.2).

Each test asserts that the system stops, not that it finds a workaround. The
services are wired as bootstrap wires them, over one seeded matter.

The happy path cannot reach a registration-ready export today: every
template in this repository is an unverified transcription, so preflight
always reports registration_ready false (draft_service.generate_form, §9.5).
Verifying the templates' legal wording is a human gate, so these cover the
refusals, which do not depend on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import SeedReport, seed
from src.bootstrap import build_approval_service, build_draft_service
from src.modules.approval.domain.models import ExportFormat
from src.modules.check.domain.models import LegalIssue
from src.modules.check.infrastructure.repository import SqlCheckRepository
from src.modules.content_governance.contracts import (
    TRANSFER_SALE_SUBTYPE_ID,
    BlockerKind,
    FactStatus,
    IssueSeverity,
    IssueState,
    RtaWorkflowRole,
    SubtypeDecisionStatus,
)
from src.modules.draft.application.draft_service import FormView
from src.modules.verification.domain.models import ExtractedFact
from src.modules.verification.infrastructure.repository import SqlVerificationRepository
from src.platform.errors import DraftlyError
from tests.factories.constants import NOW

pytestmark = pytest.mark.integration

BUYER_NAME = "rta.party.transferee_name"


@pytest.fixture
async def matter(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SeedReport:
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    return await seed(db_session)


async def _generate(
    session: AsyncSession,
    matter: SeedReport,
    status: SubtypeDecisionStatus = SubtypeDecisionStatus.LAWYER_CONFIRMED,
) -> FormView:
    return await build_draft_service(session).generate_form(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        actor_id=matter.lawyer_id,
        correlation_id="corr_workflow",
        subtype_id=TRANSFER_SALE_SUBTYPE_ID,
        subtype_decision_status=status,
    )


async def _open_statutory_blocker(session: AsyncSession, matter: SeedReport) -> None:
    await SqlCheckRepository(session).create_issue(
        LegalIssue(
            id="iss_synthetic_encumbrance",
            user_id=matter.lawyer_id,
            matter_id=matter.matter_id,
            issue_type_id="rta.issue.synthetic_encumbrance",
            severity=IssueSeverity.BLOCKING,
            blocker_kind=BlockerKind.STATUTORY,
            state=IssueState.OPEN,
            summary_key="rta.issue.synthetic_encumbrance.summary",
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _refusal(caught: pytest.ExceptionInfo[DraftlyError]) -> str:
    return caught.value.code


# ── Before any draft ────────────────────────────────────────────────────────


async def test_no_draft_before_the_lawyer_confirms_the_instrument(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    with pytest.raises(DraftlyError) as caught:
        await _generate(db_session, matter, SubtypeDecisionStatus.PROVISIONAL)

    assert "subtype" in _refusal(caught)


async def test_refusal_1_an_open_statutory_blocker_stops_draft_generation(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    """There is no override: the lawyer resolves the encumbrance outside the system."""
    await _open_statutory_blocker(db_session, matter)

    with pytest.raises(DraftlyError) as caught:
        await _generate(db_session, matter)

    assert "blocked" in _refusal(caught)


# ── Refusal 5: machine confidence is never sufficient ───────────────────────


async def test_refusal_5_an_unreviewed_value_never_fills_the_draft(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    await SqlVerificationRepository(db_session).create_fact(
        ExtractedFact(
            id="fact_synthetic_machine",
            user_id=matter.lawyer_id,
            matter_id=matter.matter_id,
            fact_type_id=BUYER_NAME,
            value="Machine Read Buyer (synthetic)",
            status=FactStatus.EXTRACTED_CANDIDATE,
            model_reported_confidence=0.99,
            created_at=NOW,
            evidence_reference_ids=("ev_synthetic_machine",),
        )
    )

    view = await _generate(db_session, matter)

    machine = "Machine Read Buyer (synthetic)"
    # Nothing binds the machine value into the draft...
    assert all(v.field.rendered_value != machine for v in view.fields)
    assert all(v.field.fact_id != "fact_synthetic_machine" for v in view.fields)
    # ...and where the screen offers it, it is flagged as a suggestion.
    assert all(v.ai_suggested for v in view.fields if v.display_value == machine)
    assert not view.preflight.registration_ready


async def test_refusal_5_an_unresolved_draft_cannot_be_approved(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    view = await _generate(db_session, matter)
    service = build_approval_service(db_session)

    with pytest.raises(DraftlyError):
        await service.approve_form(
            user_id=matter.lawyer_id,
            form_id=view.form.id,
            actor_id=matter.lawyer_id,
            workflow_role=RtaWorkflowRole.RESPONSIBLE_LAWYER,
            correlation_id="corr_workflow",
            disposed_warning_ids=(),
        )

    assert await service.current_approval(matter.lawyer_id, view.form.id) is None


# ── Refusal 3: no approved export before approval ───────────────────────────


async def test_refusal_3_an_approved_manifest_needs_an_approval(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    view = await _generate(db_session, matter)

    with pytest.raises(DraftlyError) as caught:
        await build_approval_service(db_session).export_form(
            user_id=matter.lawyer_id,
            form_id=view.form.id,
            actor_id=matter.lawyer_id,
            correlation_id="corr_workflow",
            export_format=ExportFormat.APPROVED_MANIFEST,
        )

    assert "approval" in _refusal(caught)


async def test_a_working_draft_export_is_allowed_and_watermarked(
    db_session: AsyncSession, matter: SeedReport
) -> None:
    """Refusal 3 is about the approved artifact; a marked working copy is fine."""
    view = await _generate(db_session, matter)

    export = await build_approval_service(db_session).export_form(
        user_id=matter.lawyer_id,
        form_id=view.form.id,
        actor_id=matter.lawyer_id,
        correlation_id="corr_workflow",
        export_format=ExportFormat.WORKING_DRAFT_MANIFEST,
    )

    assert export.watermarked is True

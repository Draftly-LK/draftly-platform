"""Approving, exporting, and recording registry events end to end.

Fakes only, no database. All fixture content is synthetic. The acceptance
criteria that live here:

- an approval pins the server's own snapshot, its template version, its
  confirmed critical facts, and a declaration hash, and never a client value;
- an unclean preflight refuses the approval;
- a second approval of a changed snapshot revokes the first, and the revoked one
  cannot be reused for an export;
- a correction after approval marks the form stale and refuses reuse (§17);
- export does not change the matter to ``REGISTERED``;
- recording a presentation does not register the matter;
- only a recorded registration event, with evidence, reaches ``REGISTERED``;
- a confirmed attestation date — and nothing else — starts the seven-working-day
  forwarding task, and its answer says it is provisional.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modules.approval.application.approval_service import (
    ApprovalService,
    ApprovalView,
    RegistrationEventView,
)
from src.modules.approval.domain.errors import (
    ApprovalAlreadyCurrentError,
    ApprovalDeclarationUnknownError,
    ApprovalPreflightUncleanError,
    ApprovalSupersededError,
    ApprovalTargetNotFoundError,
    ExportRequiresApprovalError,
    RegistrationEvidenceRequiredError,
)
from src.modules.approval.domain.models import ExportFormat
from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    GeneratedFormState,
    MatterState,
    RegistrationEventType,
    RtaWorkflowRole,
)
from src.modules.draft.contracts import FormSnapshot
from src.modules.verification.contracts import FactTierSummary

from .fakes import (
    CORRELATION,
    FORM_08,
    FORM_ID,
    LAWYER_ID,
    MATTER_ID,
    NOW,
    USER_ID,
    FakeApprovalRepository,
    FakeAudit,
    FakeChecklistBlockers,
    FakeExportRepository,
    FakeFactReader,
    FakeFormCommands,
    FakeFormReader,
    FakeIssueGates,
    FakeMatterCommands,
    FakeRegistrationEventRepository,
    bindings,
    fact_tier,
    form_snapshot,
)


class _Harness:
    """One service and every double it was built from."""

    def __init__(
        self,
        *,
        snapshot: FormSnapshot | None = None,
        facts: FactTierSummary | None = None,
        gates: IssueGateSummary | None = None,
        requirements: tuple[str, ...] = (),
        wire_commands: bool = True,
    ) -> None:
        self.approvals = FakeApprovalRepository()
        self.exports = FakeExportRepository()
        self.events = FakeRegistrationEventRepository()
        self.forms = FakeFormReader(snapshot)
        self.facts = FakeFactReader(facts)
        self.audit = FakeAudit()
        self.form_commands = FakeFormCommands()
        self.matter_commands = FakeMatterCommands()
        self.service = ApprovalService(
            approvals=self.approvals,
            exports=self.exports,
            events=self.events,
            forms=self.forms,
            facts=self.facts,
            issues=FakeIssueGates(gates),
            checklist=FakeChecklistBlockers(requirements),
            audit=self.audit,
            form_commands=self.form_commands if wire_commands else None,
            matter_commands=self.matter_commands if wire_commands else None,
            clock=lambda: NOW,
        )

    async def gate_warning_ids(self) -> list[str]:
        """The warnings the interface would have shown the lawyer."""
        gate = await self.service.approval_gate(user_id=USER_ID, form_id=FORM_ID)
        return list(gate.warning_ids)

    async def approve(self) -> ApprovalView:
        return await self.service.approve_form(
            user_id=USER_ID,
            form_id=FORM_ID,
            actor_id=LAWYER_ID,
            workflow_role=RtaWorkflowRole.RESPONSIBLE_LAWYER,
            correlation_id=CORRELATION,
            disposed_warning_ids=await self.gate_warning_ids(),
        )


# ── Approval (§9.6) ──────────────────────────────────────────────────────────


async def test_an_approval_pins_the_servers_own_snapshot() -> None:
    harness = _Harness()
    view = await harness.approve()
    approval = view.approval

    assert approval.target_id == FORM_ID
    # Read from the form record, never from the request body.
    assert approval.target_version == "1"
    assert approval.template_id == FORM_08.id
    assert approval.template_version == FORM_08.version
    assert approval.approver_id == LAWYER_ID
    assert approval.approver_workflow_role is RtaWorkflowRole.RESPONSIBLE_LAWYER
    assert approval.snapshot_hash.startswith("sha256:")
    assert approval.confirmed_fact_hash.startswith("sha256:")
    assert approval.declaration_text_hash.startswith("pending-sha256:")
    assert approval.revoked_by_approval_id is None


async def test_approval_records_the_form_freeze_and_the_matter_state() -> None:
    harness = _Harness()
    view = await harness.approve()

    assert harness.form_commands.approvals == [
        {
            "form_id": FORM_ID,
            "approval_id": view.approval.id,
            "approved_artifact_hash": view.approval.snapshot_hash,
            "expected_version": 3,
        }
    ]
    assert harness.matter_commands.states == [MatterState.APPROVED]


async def test_approval_writes_one_audit_event_naming_the_approval() -> None:
    harness = _Harness()
    view = await harness.approve()

    event = harness.audit.events[-1]
    assert event.action == AuditAction.RTA_FORM_APPROVED.value
    assert event.target_type == AuditTargetType.APPROVAL.value
    assert event.target_id == view.approval.id
    assert event.matter_id == MATTER_ID
    assert event.actor == LAWYER_ID


async def test_an_unclean_preflight_refuses_the_approval() -> None:
    harness = _Harness(snapshot=form_snapshot(unresolved_field_ids=("transferee_nic",)))
    with pytest.raises(ApprovalPreflightUncleanError):
        await harness.approve()
    assert harness.approvals.approvals == {}
    assert harness.matter_commands.states == []


async def test_an_open_blocking_issue_refuses_the_approval() -> None:
    harness = _Harness(gates=IssueGateSummary(open_blocking_issue_ids=("iss_synthetic",)))
    with pytest.raises(ApprovalPreflightUncleanError):
        await harness.approve()


async def test_an_unregistered_declaration_version_is_refused() -> None:
    harness = _Harness()
    with pytest.raises(ApprovalDeclarationUnknownError):
        await harness.service.approve_form(
            user_id=USER_ID,
            form_id=FORM_ID,
            actor_id=LAWYER_ID,
            workflow_role=RtaWorkflowRole.RESPONSIBLE_LAWYER,
            correlation_id=CORRELATION,
            disposed_warning_ids=await harness.gate_warning_ids(),
            declaration_version="99",
        )


async def test_approving_the_same_unchanged_snapshot_twice_is_a_conflict() -> None:
    harness = _Harness()
    await harness.approve()
    with pytest.raises(ApprovalAlreadyCurrentError):
        await harness.approve()


async def test_a_form_belonging_to_someone_else_is_not_found() -> None:
    harness = _Harness()
    with pytest.raises(ApprovalTargetNotFoundError):
        await harness.service.matter_id_for_form(user_id="usr_synthetic_other", form_id=FORM_ID)


# ── Rule 6: a correction after approval (§17) ────────────────────────────────


async def test_a_correction_after_approval_marks_the_form_stale_and_blocks_reuse() -> None:
    harness = _Harness()
    await harness.approve()

    # The lawyer corrects a critical fact: a new fact id at a new version (§10.5).
    harness.facts.summary = fact_tier(suffix="b", version=2)

    with pytest.raises(ApprovalSupersededError) as excinfo:
        await harness.service.export_form(
            user_id=USER_ID,
            form_id=FORM_ID,
            actor_id=LAWYER_ID,
            correlation_id=CORRELATION,
            export_format=ExportFormat.APPROVED_MANIFEST,
        )
    assert excinfo.value.details["movedFieldIds"]
    assert harness.form_commands.stale == [{"form_id": FORM_ID, "reason": "FACT_SUPERSEDED"}]
    assert harness.exports.exports == {}


async def test_a_second_approval_revokes_the_first() -> None:
    harness = _Harness()
    first = await harness.approve()

    # A new form version rebinds the corrected fact, and the lawyer approves it.
    harness.facts.summary = fact_tier(suffix="b", version=2)
    harness.forms.snapshot = form_snapshot(
        critical_fact_bindings=bindings(suffix="b", version=2),
        draft_artifact_hash="sha256:synthetic-draft-hash-2",
        form_version=2,
    )
    second = await harness.approve()

    stored_first = harness.approvals.approvals[first.approval.id]
    assert stored_first.revoked_by_approval_id == second.approval.id
    assert stored_first.is_revoked
    current = await harness.service.current_approval(USER_ID, FORM_ID)
    assert current is not None
    assert current.id == second.approval.id


async def test_the_revoked_approval_stays_readable() -> None:
    """§17 needs the superseded signature to remain in the history."""
    harness = _Harness()
    await harness.approve()
    harness.facts.summary = fact_tier(suffix="b", version=2)
    harness.forms.snapshot = form_snapshot(
        critical_fact_bindings=bindings(suffix="b", version=2),
        draft_artifact_hash="sha256:synthetic-draft-hash-2",
        form_version=2,
    )
    await harness.approve()

    approvals, _ = await harness.service.list_approvals(user_id=USER_ID, form_id=FORM_ID)
    assert len(approvals) == 2
    assert sum(1 for approval in approvals if approval.is_revoked) == 1


async def test_the_form_moving_under_an_approval_also_blocks_reuse() -> None:
    """A field decision rewrites `draft_artifact_hash`; the approval is spent."""
    harness = _Harness()
    await harness.approve()
    harness.forms.snapshot = form_snapshot(draft_artifact_hash="sha256:rewritten")

    with pytest.raises(ApprovalSupersededError):
        await harness.service.export_form(
            user_id=USER_ID,
            form_id=FORM_ID,
            actor_id=LAWYER_ID,
            correlation_id=CORRELATION,
            export_format=ExportFormat.APPROVED_MANIFEST,
        )
    assert harness.form_commands.stale


# ── Export (§9.4, §9.6, §17) ─────────────────────────────────────────────────


async def test_a_working_draft_export_is_watermarked_and_moves_nothing() -> None:
    harness = _Harness(snapshot=form_snapshot(state=GeneratedFormState.UNRESOLVED))
    export = await harness.service.export_form(
        user_id=USER_ID,
        form_id=FORM_ID,
        actor_id=LAWYER_ID,
        correlation_id=CORRELATION,
        export_format=ExportFormat.WORKING_DRAFT_MANIFEST,
    )
    assert export.watermarked is True
    assert export.registration_ready is False
    assert export.approval_id is None
    assert export.artifact_key.startswith("inline:manifest/")
    assert harness.matter_commands.states == []


async def test_an_approved_export_does_not_register_the_matter() -> None:
    """§17 — exported drafts and approved instruments are distinct, and export
    does not mark the matter registered."""
    harness = _Harness()
    approval = await harness.approve()
    harness.matter_commands.states.clear()

    export = await harness.service.export_form(
        user_id=USER_ID,
        form_id=FORM_ID,
        actor_id=LAWYER_ID,
        correlation_id=CORRELATION,
        export_format=ExportFormat.APPROVED_MANIFEST,
    )
    assert export.approval_id == approval.approval.id
    assert export.watermarked is False
    # No template in this repository is a lawyer-approved production rendering.
    assert export.registration_ready is False
    assert export.manifest["registrationReadyBlockedBy"]
    assert harness.matter_commands.states == [MatterState.EXPORTED]
    assert MatterState.REGISTERED not in harness.matter_commands.states


async def test_an_approved_export_without_an_approval_is_refused() -> None:
    harness = _Harness()
    with pytest.raises(ExportRequiresApprovalError):
        await harness.service.export_form(
            user_id=USER_ID,
            form_id=FORM_ID,
            actor_id=LAWYER_ID,
            correlation_id=CORRELATION,
            export_format=ExportFormat.APPROVED_MANIFEST,
        )


async def test_the_evidence_schedule_carries_the_field_to_evidence_chain() -> None:
    """§9.6 — the file's own audit schedule, not normally submitted."""
    harness = _Harness()
    export = await harness.service.export_form(
        user_id=USER_ID,
        form_id=FORM_ID,
        actor_id=LAWYER_ID,
        correlation_id=CORRELATION,
        export_format=ExportFormat.EVIDENCE_SCHEDULE,
    )
    schedule = export.manifest["evidenceSchedule"]
    assert len(schedule) == len(bindings())
    assert all(entry["evidenceReferenceIds"] for entry in schedule)
    assert export.registration_ready is False


async def test_export_writes_an_audit_event_naming_the_export() -> None:
    harness = _Harness()
    export = await harness.service.export_form(
        user_id=USER_ID,
        form_id=FORM_ID,
        actor_id=LAWYER_ID,
        correlation_id=CORRELATION,
        export_format=ExportFormat.WORKING_DRAFT_MANIFEST,
    )
    event = harness.audit.events[-1]
    assert event.action == AuditAction.RTA_FORM_EXPORTED.value
    assert event.target_type == AuditTargetType.EXPORT.value
    assert event.target_id == export.id
    assert "registrationReady=false" in (event.after_ref or "")


# ── Registration events (§10.1, §17) ─────────────────────────────────────────


async def _record(
    harness: _Harness,
    event_type: RegistrationEventType,
    *,
    event_date: date = date(2026, 8, 10),
    evidence: tuple[str, ...] = ("ev_registry_synthetic",),
    day_book_reference: str | None = None,
    result_note: str | None = None,
) -> RegistrationEventView:
    return await harness.service.record_registration_event(
        user_id=USER_ID,
        matter_id=MATTER_ID,
        actor_id=LAWYER_ID,
        correlation_id=CORRELATION,
        event_type=event_type,
        event_date=event_date,
        evidence_reference_ids=evidence,
        generated_form_id=FORM_ID,
        day_book_reference=day_book_reference,
        result_note=result_note,
    )


async def test_recording_a_presentation_does_not_register_the_matter() -> None:
    harness = _Harness()
    view = await _record(harness, RegistrationEventType.PRESENTED)

    assert view.implied_matter_state is MatterState.SUBMITTED
    assert harness.matter_commands.states == [MatterState.SUBMITTED]
    summary = await harness.service.registration_summary(USER_ID, MATTER_ID)
    assert summary.presented_on == date(2026, 8, 10)
    assert summary.is_registered is False


async def test_only_a_recorded_registration_with_evidence_reaches_registered() -> None:
    harness = _Harness()
    await _record(harness, RegistrationEventType.PRESENTED)

    with pytest.raises(RegistrationEvidenceRequiredError):
        await _record(harness, RegistrationEventType.REGISTERED, evidence=())
    assert MatterState.REGISTERED not in harness.matter_commands.states

    view = await _record(harness, RegistrationEventType.REGISTERED, event_date=date(2026, 8, 12))
    assert view.implied_matter_state is MatterState.REGISTERED
    assert harness.matter_commands.states[-1] is MatterState.REGISTERED
    summary = await harness.service.registration_summary(USER_ID, MATTER_ID)
    assert summary.is_registered is True
    assert summary.registered_on == date(2026, 8, 12)


async def test_an_attestation_starts_the_provisional_seven_working_day_task() -> None:
    harness = _Harness()
    view = await _record(harness, RegistrationEventType.ATTESTED)

    deadline = view.deadline
    assert deadline is not None
    assert deadline.due_on == date(2026, 8, 19)
    assert deadline.provisional is True
    # An attestation is an act on the instrument, not a registry act: §10.1 has
    # no matter state for it.
    assert view.implied_matter_state is None
    assert harness.matter_commands.states == []


async def test_no_other_event_starts_the_forwarding_clock() -> None:
    harness = _Harness()
    view = await _record(harness, RegistrationEventType.PRESENTED)
    assert view.deadline is None
    summary = await harness.service.registration_summary(USER_ID, MATTER_ID)
    assert summary.forwarding_due_on is None


async def test_a_registration_event_writes_an_audit_event() -> None:
    harness = _Harness()
    view = await _record(harness, RegistrationEventType.PRESENTED)

    event = harness.audit.events[-1]
    assert event.action == AuditAction.RTA_REGISTRATION_EVENT_RECORDED.value
    assert event.target_type == AuditTargetType.REGISTRATION_EVENT.value
    assert event.target_id == view.event.id
    assert "matterState=SUBMITTED" in (event.after_ref or "")


async def test_a_registration_event_naming_another_matters_form_is_not_found() -> None:
    harness = _Harness()
    with pytest.raises(ApprovalTargetNotFoundError):
        await harness.service.record_registration_event(
            user_id=USER_ID,
            matter_id="mat_synthetic_other",
            actor_id=LAWYER_ID,
            correlation_id=CORRELATION,
            event_type=RegistrationEventType.PRESENTED,
            event_date=date(2026, 8, 10),
            evidence_reference_ids=("ev_registry_synthetic",),
            generated_form_id=FORM_ID,
        )


# ── Degrading without the two command ports ──────────────────────────────────


async def test_the_legal_record_is_still_written_without_the_command_ports() -> None:
    """Neither `draft` nor `matter` exposes its command port yet.

    The approval, the export, and the registration event are all recorded
    regardless; the two aggregates this module does not own simply do not move.
    """
    harness = _Harness(wire_commands=False)
    view = await harness.approve()
    assert view.approval.id in harness.approvals.approvals

    await _record(harness, RegistrationEventType.PRESENTED)
    await _record(harness, RegistrationEventType.REGISTERED, event_date=date(2026, 8, 12))
    summary = await harness.service.registration_summary(USER_ID, MATTER_ID)
    assert summary.is_registered is True
    assert harness.matter_commands.states == []

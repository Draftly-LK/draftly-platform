"""The approval, export, and registration rules, tested where they live.

All fixture content is synthetic. The acceptance criteria that live here:

- only the responsible lawyer for the matter may approve, and each of the other
  five §12.5 roles is refused with the right status;
- an approval pins the server's own snapshot, and the hash moves when the
  bindings move but not when the form's state does;
- an unclean preflight refuses approval, and a statutory blocker refuses it with
  a code that says nobody can override it;
- an export is not registration: `registration_ready` is false for every
  template in this repository, and `matter_state_for_export` cannot say
  ``REGISTERED``;
- attestation, presentation, and registration are three separate events, each
  needing a human, a date, and evidence, and only a confirmed attestation date
  starts the seven-working-day clock;
- a correction after approval is detected from the fact tier itself.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modules.approval.domain.declarations import (
    CURRENT_DECLARATION_VERSION,
    DeclarationRecord,
    declaration_text_hash,
    get_declaration,
)
from src.modules.approval.domain.errors import (
    ApprovalFormNotReviewableError,
    ApprovalFormStaleError,
    ApprovalPreflightUncleanError,
    ApprovalStatutoryBlockerError,
    ApprovalWarningsNotDisposedError,
    ApproverNotResponsibleLawyerError,
    RegistrationAlreadyRecordedError,
    RegistrationDayBookReferenceRequiredError,
    RegistrationEventDateInFutureError,
    RegistrationEventFormRequiredError,
    RegistrationEvidenceRequiredError,
    RegistrationOutOfOrderError,
    RegistrationResultNoteRequiredError,
)
from src.modules.approval.domain.models import ExportFormat
from src.modules.approval.domain.policies import (
    FORWARDING_WORKING_DAYS,
    ApprovalGateCode,
    ApprovalGateResult,
    add_working_days,
    approval_snapshot_hash,
    build_manifest,
    confirmed_fact_hash,
    evaluate_approval_gate,
    export_registration_ready,
    export_watermarked,
    guard_approval,
    guard_registration_event,
    matter_state_for_event,
    matter_state_for_export,
    presentation_deadline,
    registration_status,
    require_responsible_lawyer,
    source_reverification_required,
    superseded_bindings,
)
from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    FORM_TEMPLATES,
    GeneratedFormState,
    MatterState,
    RegistrationEventType,
    RtaWorkflowRole,
)
from src.modules.draft.contracts import FormSnapshot
from src.modules.verification.contracts import FactTierSummary
from src.platform.errors import NotFoundError

from .fakes import (
    FORM_08,
    LAWYER_ID,
    TODAY,
    USER_ID,
    approval_record,
    bindings,
    fact_tier,
    form_snapshot,
    matter_summary,
    registration_event,
)

_OTHER_LAWYER = "usr_synthetic_other"


def _gate(
    *,
    snapshot: FormSnapshot | None = None,
    facts: FactTierSummary | None = None,
    gates: IssueGateSummary | None = None,
    requirements: tuple[str, ...] = (),
) -> ApprovalGateResult:
    return evaluate_approval_gate(
        snapshot=snapshot if snapshot is not None else form_snapshot(),
        template=FORM_08,
        facts=facts if facts is not None else fact_tier(),
        issue_gates=gates or IssueGateSummary(),
        blocking_requirement_ids=requirements,
    )


# ── Rule 1: only the responsible lawyer may approve (§12.5) ──────────────────


def test_the_responsible_lawyer_may_approve() -> None:
    role = require_responsible_lawyer(
        account_role="approver", actor_id=LAWYER_ID, matter=matter_summary()
    )
    assert role is RtaWorkflowRole.RESPONSIBLE_LAWYER


def test_a_case_assistant_may_not_approve() -> None:
    """A reviewer-tier account on the matter is a case assistant (§12.5)."""
    with pytest.raises(ApproverNotResponsibleLawyerError) as excinfo:
        require_responsible_lawyer(
            account_role="reviewer",
            actor_id=USER_ID,
            matter=matter_summary(responsible_lawyer_id=_OTHER_LAWYER),
        )
    assert excinfo.value.http_status == 403
    assert excinfo.value.details["workflowRole"] == RtaWorkflowRole.CASE_ASSISTANT.value


def test_an_approver_who_is_not_the_responsible_lawyer_may_not_approve() -> None:
    """An approver-tier account is a lawyer reviewer on someone else's file."""
    with pytest.raises(ApproverNotResponsibleLawyerError) as excinfo:
        require_responsible_lawyer(
            account_role="approver",
            actor_id=USER_ID,
            matter=matter_summary(responsible_lawyer_id=_OTHER_LAWYER),
        )
    assert excinfo.value.details["workflowRole"] == RtaWorkflowRole.LAWYER_REVIEWER.value


def test_template_counsel_cannot_see_the_matter_at_all() -> None:
    """§12.5 — governed content is validated without reading client files: 404."""
    with pytest.raises(NotFoundError) as excinfo:
        require_responsible_lawyer(
            account_role="maintainer", actor_id="usr_synthetic_counsel", matter=matter_summary()
        )
    assert excinfo.value.http_status == 404


def test_an_office_admin_may_not_approve() -> None:
    with pytest.raises(ApproverNotResponsibleLawyerError) as excinfo:
        require_responsible_lawyer(
            account_role="administrator",
            actor_id=USER_ID,
            matter=matter_summary(responsible_lawyer_id=_OTHER_LAWYER),
        )
    assert excinfo.value.details["workflowRole"] == RtaWorkflowRole.OFFICE_ADMIN.value


def test_an_actor_with_no_standing_gets_404_not_403() -> None:
    """The matter's existence is never leaked to a stranger."""
    with pytest.raises(NotFoundError):
        require_responsible_lawyer(
            account_role="approver",
            actor_id="usr_synthetic_stranger",
            matter=matter_summary(),
        )


# ── Rule 2: an approval pins an exact snapshot (§9.6) ────────────────────────


def test_the_snapshot_hash_moves_when_a_binding_moves() -> None:
    before = approval_snapshot_hash(form_snapshot())
    after = approval_snapshot_hash(
        form_snapshot(critical_fact_bindings=bindings(suffix="b", version=2))
    )
    assert before != after


def test_the_snapshot_hash_survives_the_form_becoming_approved() -> None:
    """The hash must keep matching after the approval it records is written."""
    before = approval_snapshot_hash(form_snapshot())
    after = approval_snapshot_hash(
        form_snapshot(
            state=GeneratedFormState.APPROVED,
            approved_artifact_hash="sha256:whatever",
            approval_id="apr_synthetic",
        )
    )
    assert before == after


def test_the_confirmed_fact_hash_covers_only_the_pinned_facts() -> None:
    assert confirmed_fact_hash(form_snapshot()) == confirmed_fact_hash(
        form_snapshot(unresolved_field_ids=(), draft_artifact_hash="sha256:different")
    )
    assert confirmed_fact_hash(form_snapshot()) != confirmed_fact_hash(
        form_snapshot(critical_fact_bindings=bindings(version=7))
    )


def test_the_declaration_text_is_not_authored_in_this_repository() -> None:
    """The wording is human-owned; what is registered is the record of it."""
    record = get_declaration(CURRENT_DECLARATION_VERSION)
    assert record is not None
    assert record.text_sha256 is None
    assert declaration_text_hash(record).startswith("pending-sha256:")
    written = DeclarationRecord(
        version="9", text_key="rta.approval.declaration.v9", text_sha256="ab"
    )
    assert declaration_text_hash(written) == "sha256:ab"


# ── Rule 3: approval is refused while preflight is unclean (§9.4, §14.6) ─────


def test_a_clean_form_8_draft_is_approval_ready() -> None:
    result = _gate()
    assert result.approval_ready
    assert not result.blocking


def test_an_unresolved_required_field_blocks_approval() -> None:
    result = _gate(snapshot=form_snapshot(unresolved_field_ids=("transferee_nic",)))
    assert not result.approval_ready
    with pytest.raises(ApprovalPreflightUncleanError):
        guard_approval(result, disposed_warning_ids=list(result.warning_ids))


def test_an_unresolved_optional_field_is_only_a_warning() -> None:
    result = _gate(snapshot=form_snapshot(unresolved_field_ids=("village",)))
    assert result.approval_ready
    assert any(item.code is ApprovalGateCode.UNRESOLVED_OPTIONAL_FIELD for item in result.warnings)


def test_a_critical_field_with_no_binding_blocks_approval() -> None:
    result = _gate(snapshot=form_snapshot(critical_fact_bindings=bindings(omit=("extent",))))
    assert any(
        item.code is ApprovalGateCode.CRITICAL_FIELD_UNPOPULATED and item.subject_id == "extent"
        for item in result.blocking
    )


def test_a_critical_binding_with_no_evidence_blocks_approval() -> None:
    result = _gate(
        snapshot=form_snapshot(critical_fact_bindings=bindings(without_evidence=("extent",)))
    )
    assert any(
        item.code is ApprovalGateCode.CRITICAL_FIELD_EVIDENCE_MISSING for item in result.blocking
    )


def test_an_unconfirmed_critical_fact_blocks_approval() -> None:
    result = _gate(facts=fact_tier(unconfirmed_critical=("rta.parcel.extent",)))
    assert any(item.code is ApprovalGateCode.CRITICAL_FACT_UNCONFIRMED for item in result.blocking)


def test_a_statutory_blocker_cannot_be_overridden() -> None:
    """§7.3, §10.6 — no role inside Draftly may waive one."""
    result = _gate(gates=IssueGateSummary(open_statutory_blocker_ids=("iss_synthetic",)))
    with pytest.raises(ApprovalStatutoryBlockerError) as excinfo:
        guard_approval(result, disposed_warning_ids=list(result.warning_ids))
    assert excinfo.value.details["openStatutoryBlockerIds"] == ["iss_synthetic"]


def test_a_blocking_checklist_requirement_blocks_approval() -> None:
    result = _gate(requirements=("R_C20_SEVEN_WORKING_DAY_FORWARDING",))
    assert any(
        item.code is ApprovalGateCode.CHECKLIST_REQUIREMENT_BLOCKING for item in result.blocking
    )


def test_a_high_risk_issue_blocks_approval_without_naming_an_issue_id() -> None:
    result = _gate(gates=IssueGateSummary(blocks_approval=True))
    assert any(item.code is ApprovalGateCode.ISSUE_BLOCKS_APPROVAL for item in result.blocking)


def test_a_stale_form_is_refused_with_its_own_code() -> None:
    result = _gate(
        snapshot=form_snapshot(
            state=GeneratedFormState.STALE_TEMPLATE, stale_reason="TEMPLATE_VERSION_CHANGED"
        )
    )
    with pytest.raises(ApprovalFormStaleError):
        guard_approval(result, disposed_warning_ids=list(result.warning_ids))


def test_an_unreviewed_draft_cannot_be_approved() -> None:
    result = _gate(snapshot=form_snapshot(state=GeneratedFormState.GENERATED_DRAFT))
    with pytest.raises(ApprovalFormNotReviewableError):
        guard_approval(result, disposed_warning_ids=list(result.warning_ids))


def test_every_warning_must_be_disposed_of() -> None:
    """§9.6 — the approval carries the warnings the lawyer accepted."""
    result = _gate()
    assert result.warning_ids
    with pytest.raises(ApprovalWarningsNotDisposedError) as excinfo:
        guard_approval(result, disposed_warning_ids=[])
    assert excinfo.value.details["missing"] == sorted(result.warning_ids)


def test_a_disposition_for_a_warning_that_does_not_exist_is_refused() -> None:
    result = _gate()
    with pytest.raises(ApprovalWarningsNotDisposedError) as excinfo:
        guard_approval(result, disposed_warning_ids=[*result.warning_ids, "INVENTED_CODE:whatever"])
    assert excinfo.value.details["unknown"] == ["INVENTED_CODE:whatever"]


def test_the_unvalidated_template_is_a_warning_at_approval_and_a_bar_at_export() -> None:
    """§9.5 — a lawyer may approve the content of a transcription; a registry
    may not receive one."""
    result = _gate()
    assert result.approval_ready
    assert not result.registration_ready
    assert any(item.code is ApprovalGateCode.TEMPLATE_NOT_VALIDATED for item in result.warnings)


# ── Rule 4: export is not registration (§9.4, §9.6, §17) ─────────────────────


def test_no_template_in_this_repository_can_back_a_registration_ready_export() -> None:
    for template in FORM_TEMPLATES:
        assert template.registration_ready_capable is False
        assert source_reverification_required(template) is True


def test_a_working_draft_is_watermarked_and_never_registration_ready() -> None:
    result = _gate()
    assert export_watermarked(ExportFormat.WORKING_DRAFT_MANIFEST, None) is True
    assert (
        export_registration_ready(
            export_format=ExportFormat.WORKING_DRAFT_MANIFEST, approval=None, result=result
        )
        is False
    )


def test_the_working_draft_manifest_carries_the_notice_on_every_page() -> None:
    """§9.4 — the draft notice is a property of the record, not a convention."""
    result = _gate()
    manifest = build_manifest(
        snapshot=form_snapshot(),
        template=FORM_08,
        export_format=ExportFormat.WORKING_DRAFT_MANIFEST,
        approval=None,
        result=result,
        watermarked=True,
        registration_ready=False,
    )
    assert manifest["watermark"] == {
        "key": "rta.form.watermark.draft_not_approved",
        "everyPage": True,
    }
    assert manifest["registrationReady"] is False
    assert manifest["registrationReadyBlockedBy"]
    assert manifest["noticeKey"] == "rta.form.export.internal_review_artifact_only"


def test_export_can_never_imply_registration() -> None:
    """§17 — export does not mark the matter registered."""
    approval = approval_record()
    for export_format in ExportFormat:
        # Without an approval nothing moves at all…
        assert matter_state_for_export(export_format, None) is None
        # …and with one, the furthest an export can reach is EXPORTED.
        assert matter_state_for_export(export_format, approval) is not MatterState.REGISTERED
    assert matter_state_for_export(ExportFormat.APPROVED_MANIFEST, approval) is MatterState.EXPORTED
    assert matter_state_for_export(ExportFormat.EVIDENCE_SCHEDULE, approval) is None


def test_the_manifest_is_stable_across_two_exports_of_one_snapshot() -> None:
    result = _gate()
    first = build_manifest(
        snapshot=form_snapshot(),
        template=FORM_08,
        export_format=ExportFormat.WORKING_DRAFT_MANIFEST,
        approval=None,
        result=result,
        watermarked=True,
        registration_ready=False,
    )
    second = build_manifest(
        snapshot=form_snapshot(),
        template=FORM_08,
        export_format=ExportFormat.WORKING_DRAFT_MANIFEST,
        approval=None,
        result=result,
        watermarked=True,
        registration_ready=False,
    )
    assert first == second


# ── Rule 5: three separate recorded events (§10.1, §17) ──────────────────────


def test_presentation_submits_and_only_registration_registers() -> None:
    assert matter_state_for_event(RegistrationEventType.ATTESTED) is None
    assert matter_state_for_event(RegistrationEventType.PRESENTED) is MatterState.SUBMITTED
    assert matter_state_for_event(RegistrationEventType.DAY_BOOK_ENTERED) is MatterState.SUBMITTED
    assert matter_state_for_event(RegistrationEventType.REGISTERED) is MatterState.REGISTERED
    assert matter_state_for_event(RegistrationEventType.REFUSED) is None
    assert matter_state_for_event(RegistrationEventType.RETURNED) is None


def _guard(event_type: RegistrationEventType, **overrides: object) -> None:
    kwargs: dict[str, object] = {
        "event_type": event_type,
        "event_date": date(2026, 8, 10),
        "today": TODAY,
        "evidence_reference_ids": ("ev_synthetic",),
        "generated_form_id": "frm_synthetic",
        "day_book_reference": None,
        "result_note": None,
        "existing": (),
    }
    kwargs.update(overrides)
    guard_registration_event(**kwargs)  # type: ignore[arg-type]


def test_a_registry_event_without_evidence_is_refused() -> None:
    with pytest.raises(RegistrationEvidenceRequiredError):
        _guard(RegistrationEventType.PRESENTED, evidence_reference_ids=())


def test_a_registry_event_cannot_be_dated_in_the_future() -> None:
    with pytest.raises(RegistrationEventDateInFutureError):
        _guard(RegistrationEventType.PRESENTED, event_date=date(2026, 9, 1))


def test_an_attestation_names_the_instrument_it_was_performed_on() -> None:
    with pytest.raises(RegistrationEventFormRequiredError):
        _guard(RegistrationEventType.ATTESTED, generated_form_id=None)


def test_a_day_book_entry_carries_the_registry_reference() -> None:
    with pytest.raises(RegistrationDayBookReferenceRequiredError):
        _guard(RegistrationEventType.DAY_BOOK_ENTERED)


def test_a_refusal_carries_the_reason_the_registry_gave() -> None:
    with pytest.raises(RegistrationResultNoteRequiredError):
        _guard(RegistrationEventType.REFUSED)


def test_registration_follows_a_recorded_presentation() -> None:
    """§10.1 — ``EXPORTED -> SUBMITTED -> REGISTERED``, on human evidence."""
    with pytest.raises(RegistrationOutOfOrderError):
        _guard(RegistrationEventType.REGISTERED)
    _guard(
        RegistrationEventType.REGISTERED,
        existing=(registration_event(RegistrationEventType.PRESENTED),),
    )


def test_an_instrument_cannot_be_registered_twice() -> None:
    with pytest.raises(RegistrationAlreadyRecordedError):
        _guard(
            RegistrationEventType.REGISTERED,
            existing=(
                registration_event(RegistrationEventType.PRESENTED, event_id="reg_one"),
                registration_event(RegistrationEventType.REGISTERED, event_id="reg_two"),
            ),
        )


def test_the_seven_working_day_clock_skips_the_weekend() -> None:
    """Monday attestation plus seven working days is the following Wednesday."""
    monday = date(2026, 8, 10)
    assert monday.weekday() == 0
    assert add_working_days(monday, FORWARDING_WORKING_DAYS) == date(2026, 8, 19)


def test_the_forwarding_deadline_is_always_provisional() -> None:
    """§16.4 — the Sri Lankan public-holiday calendar is unverified."""
    deadline = presentation_deadline(date(2026, 8, 10))
    assert deadline.provisional is True
    assert deadline.working_days == FORWARDING_WORKING_DAYS
    assert deadline.unverified_reason_key.endswith("holiday_calendar_unverified")


def test_only_a_confirmed_attestation_date_starts_the_clock() -> None:
    presented_only = registration_status((registration_event(RegistrationEventType.PRESENTED),))
    assert presented_only.deadline is None
    assert presented_only.is_registered is False

    attested = registration_status(
        (
            registration_event(RegistrationEventType.ATTESTED, event_id="reg_one"),
            registration_event(RegistrationEventType.PRESENTED, event_id="reg_two"),
        )
    )
    assert attested.deadline is not None
    assert attested.deadline.attested_on == date(2026, 8, 10)


def test_a_matter_is_registered_only_by_a_recorded_registration() -> None:
    events = (
        registration_event(RegistrationEventType.ATTESTED, event_id="reg_one"),
        registration_event(RegistrationEventType.PRESENTED, event_id="reg_two"),
    )
    assert registration_status(events).is_registered is False
    assert (
        registration_status(
            (*events, registration_event(RegistrationEventType.REGISTERED, event_id="reg_three"))
        ).is_registered
        is True
    )


# ── Rule 6: a correction after approval (§10.5, §17) ─────────────────────────


def test_a_corrected_fact_is_detected_from_the_tier_itself() -> None:
    """The pinned row is precisely the thing a correction supersedes."""
    snapshot = form_snapshot()
    assert superseded_bindings(snapshot, FORM_08, fact_tier()) == ()
    moved = superseded_bindings(snapshot, FORM_08, fact_tier(suffix="b"))
    assert set(moved) == {binding.field_id for binding in bindings()}


def test_a_new_fact_version_of_the_same_fact_is_also_a_correction() -> None:
    moved = superseded_bindings(form_snapshot(), FORM_08, fact_tier(version=2))
    assert moved

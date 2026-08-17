"""Generating a draft, reviewing its fields, and re-evaluating it.

All fixture content is synthetic. The acceptance criteria that live here:

- generation refuses a provisional subtype and a blocking issue;
- the template comes from the confirmed subtype, never from the body alone;
- an unconfirmed critical fact renders the token on the persisted row;
- a critical field cannot be corrected by typing a value onto the form;
- attestation cannot be pre-certified through a field decision either;
- a fact correction after generation marks the form stale and returns the
  affected binding to an unresolved token;
- an approved snapshot is immutable, and its bindings survive a staleness sweep;
- the snapshot handed to approval carries the critical bindings and the
  unresolved field ids.
"""

from __future__ import annotations

import pytest

from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    MORTGAGE_CANCEL_SUBTYPE_ID,
    RULE_PACK_VERSION,
    GeneratedFormState,
    SubtypeDecisionStatus,
    UnresolvedReason,
)
from src.modules.draft.application.draft_service import DraftService, FormView
from src.modules.draft.domain.errors import (
    ApprovedFormImmutableError,
    CriticalFieldRequiresConfirmedFactError,
    FieldDecisionReasonRequiredError,
    FieldNotPopulatedError,
    FormGenerationBlockedError,
    GeneratedFormFieldNotFoundError,
    GeneratedFormNotFoundError,
    LawyerAuthoredTextNotPermittedError,
    PreCertificationNotPermittedError,
    SubtypeNotConfirmedError,
    TemplateNotAvailableForSubtypeError,
)
from src.modules.draft.domain.models import StaleReason
from src.modules.draft.domain.policies import FieldDecisionAction

from .fakes import (
    CONFIRMED_TRANSFER,
    FORM_08_TEMPLATE_ID,
    MATTER_ID,
    NOW,
    TIRE_31_TEMPLATE_ID,
    TRANSFER_SUBTYPE_ID,
    USER_ID,
    FakeAudit,
    FakeCandidateReader,
    FakeChecklistBlockers,
    FakeFactReader,
    FakeGeneratedFormRepository,
    FakeIssueGates,
    candidate,
    fact_tier,
)

_CORRELATION = "corr_synthetic"


def _build(
    values: dict[str, object] | None = None,
    *,
    gates: IssueGateSummary | None = None,
    requirements: tuple[str, ...] = (),
    candidates: tuple[object, ...] = (),
    conflicted: tuple[str, ...] = (),
) -> tuple[DraftService, FakeGeneratedFormRepository, FakeFactReader, FakeAudit]:
    repository, audit = FakeGeneratedFormRepository(), FakeAudit()
    facts = FakeFactReader(
        fact_tier(dict(values if values is not None else CONFIRMED_TRANSFER), conflicted=conflicted)
    )
    service = DraftService(
        repository=repository,
        facts=facts,
        issues=FakeIssueGates(gates),
        checklist=FakeChecklistBlockers(requirements),
        audit=audit,
        candidates=FakeCandidateReader(candidates),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return service, repository, facts, audit


async def _generate(
    service: DraftService,
    *,
    status: SubtypeDecisionStatus = SubtypeDecisionStatus.LAWYER_CONFIRMED,
    template_id: str | None = None,
) -> FormView:
    return await service.generate_form(
        user_id=USER_ID,
        matter_id=MATTER_ID,
        actor_id=USER_ID,
        correlation_id=_CORRELATION,
        subtype_id=TRANSFER_SUBTYPE_ID,
        subtype_decision_status=status,
        template_id=template_id,
    )


def _field(view: FormView, field_id: str):  # type: ignore[no-untyped-def]
    return next(f for f in view.fields if f.field.field_id == field_id)


# ── Generation (§9.1, §9.2) ──────────────────────────────────────────────────


async def test_generation_refuses_a_provisional_subtype() -> None:
    service, repository, _, audit = _build()
    with pytest.raises(SubtypeNotConfirmedError):
        await _generate(service, status=SubtypeDecisionStatus.PROVISIONAL)
    assert repository.forms == {}
    assert audit.events == []


async def test_generation_refuses_an_open_blocking_issue() -> None:
    service, repository, _, _ = _build(
        gates=IssueGateSummary(blocks_draft_generation=True, open_blocking_issue_ids=("iss_1",))
    )
    with pytest.raises(FormGenerationBlockedError):
        await _generate(service)
    assert repository.forms == {}


async def test_generation_pins_the_template_and_rule_pack_versions() -> None:
    service, repository, _, audit = _build()
    view = await _generate(service)
    assert view.form.template_id == FORM_08_TEMPLATE_ID
    assert view.form.template_version == view.template.version
    assert view.form.rule_pack_version == RULE_PACK_VERSION
    assert view.form.form_version == 1
    assert view.form.draft_artifact_hash is not None
    assert view.form.draft_artifact_hash.startswith("sha256:")
    assert "rta.form.generated" in audit.actions()
    assert len(repository.fields) == len(view.template.field_mappings)


async def test_a_companion_template_is_drafted_only_when_named() -> None:
    service, _, _, _ = _build()
    assert (await _generate(service)).form.template_id == FORM_08_TEMPLATE_ID
    companion = await _generate(service, template_id=TIRE_31_TEMPLATE_ID)
    assert companion.form.template_id == TIRE_31_TEMPLATE_ID


async def test_a_template_the_subtype_does_not_select_is_refused() -> None:
    service, repository, _, _ = _build()
    with pytest.raises(TemplateNotAvailableForSubtypeError):
        await _generate(service, template_id="rta.reg.2022.form.12")
    assert repository.forms == {}


async def test_a_second_draft_opens_a_new_form_version() -> None:
    service, _, _, _ = _build()
    first = await _generate(service)
    second = await _generate(service)
    assert (first.form.form_version, second.form.form_version) == (1, 2)
    assert first.form.id != second.form.id


# ── What a generated draft says (§9.3, §9.4) ─────────────────────────────────


async def test_an_unconfirmed_critical_fact_renders_the_token_on_the_row() -> None:
    without_nic = {k: v for k, v in CONFIRMED_TRANSFER.items() if k != "rta.party.transferee_nic"}
    service, repository, _, _ = _build(without_nic)
    view = await _generate(service)
    stored = repository.field("transferee_nic")
    assert stored.rendered_value is None
    assert stored.unresolved_reason is UnresolvedReason.NO_FACT
    assert _field(view, "transferee_nic").display_value == "[[UNRESOLVED: transferee_nic]]"
    assert view.form.state is GeneratedFormState.UNRESOLVED


async def test_every_populated_critical_row_carries_fact_id_version_and_evidence() -> None:
    service, repository, _, _ = _build()
    await _generate(service)
    populated = [f for f in repository.fields.values() if f.critical and f.is_populated]
    assert populated
    for form_field in populated:
        assert form_field.fact_id is not None
        assert form_field.fact_version is not None
        assert form_field.evidence_reference_ids
        assert form_field.transformation_id == "EXACT_COPY"


async def test_a_conflict_leaves_the_field_unresolved_with_both_candidates_side_by_side() -> None:
    left = candidate("rta.party.transferor_name", "Synthetic Seller One", fact_id="fact_l")
    right = candidate("rta.party.transferor_name", "Synthetic Seller Won", fact_id="fact_r")
    service, repository, _, _ = _build(
        conflicted=("rta.party.transferor_name",), candidates=(left, right)
    )
    view = await _generate(service)
    assert repository.field("transferor_name").unresolved_reason is UnresolvedReason.FACT_CONFLICTED
    assert _field(view, "transferor_name").conflicting_candidates == (left, right)
    assert _field(view, "transferee_name").conflicting_candidates == ()


async def test_attestation_is_never_pre_certified_on_a_generated_draft() -> None:
    service, repository, _, _ = _build(
        {**CONFIRMED_TRANSFER, "rta.instrument.attestation_date": "2026-08-14"}
    )
    await _generate(service)
    assert repository.field("attestation_date").rendered_value is None


async def test_a_noncritical_prefill_is_badged_and_a_confirmed_value_is_not() -> None:
    without_notary = {
        k: v for k, v in CONFIRMED_TRANSFER.items() if k != "rta.instrument.notary_name"
    }
    service, _, _, _ = _build(
        without_notary,
        candidates=(candidate("rta.instrument.notary_name", "Synthetic Notary Three"),),
    )
    view = await _generate(service)
    prefilled = _field(view, "notary_name")
    assert prefilled.field.rendered_value == "Synthetic Notary Three"
    assert prefilled.ai_suggested is True
    # notary_code came from a confirmed fact: same "not yet decided" state, but
    # it is not an AI suggestion and must not be badged as one (§9.3).
    confirmed_field = _field(view, "notary_code")
    assert confirmed_field.field.awaiting_confirmation is True
    assert confirmed_field.ai_suggested is False


async def test_a_fully_confirmed_draft_is_review_ready_but_never_registration_ready() -> None:
    service, _, _, _ = _build()
    view = await _generate(service)
    assert view.form.state is GeneratedFormState.REVIEW_READY
    assert view.preflight.review_ready is True
    assert view.preflight.registration_ready is False
    assert view.preflight.watermark_key == "rta.form.watermark.draft_not_approved"


# ── Field decisions (§9.3, §9.4) ─────────────────────────────────────────────


async def _decide(
    service: DraftService,
    view: FormView,
    field_id: str,
    action: FieldDecisionAction,
    *,
    value: str | None = None,
    reason: str | None = None,
) -> FormView:
    return await service.decide_field(
        user_id=USER_ID,
        form_id=view.form.id,
        field_id=field_id,
        actor_id=USER_ID,
        correlation_id=_CORRELATION,
        expected_version=view.form.version,
        action=action,
        value=value,
        reason=reason,
    )


async def test_confirming_a_field_records_the_authenticated_reviewer() -> None:
    service, repository, _, audit = _build()
    view = await _generate(service)
    await _decide(service, view, "transferor_name", FieldDecisionAction.CONFIRM)
    stored = repository.field("transferor_name")
    assert stored.reviewed_by == USER_ID
    assert stored.reviewed_at == NOW
    assert stored.review_decision_id is not None
    assert stored.rendered_value == "Synthetic Seller One"
    assert "rta.form.field-decided" in audit.actions()


async def test_a_critical_field_cannot_be_corrected_by_typing_a_value() -> None:
    service, repository, _, _ = _build()
    view = await _generate(service)
    with pytest.raises(CriticalFieldRequiresConfirmedFactError):
        await _decide(
            service,
            view,
            "transferee_nic",
            FieldDecisionAction.CORRECT,
            value="SYNTHETIC-NIC-Z",
            reason="Read from the certificate.",
        )
    assert repository.field("transferee_nic").rendered_value == "SYNTHETIC-NIC-B"


async def test_lawyer_authored_text_is_refused_where_the_template_forbids_it() -> None:
    service, _, _, _ = _build()
    view = await _generate(service)
    with pytest.raises(LawyerAuthoredTextNotPermittedError):
        await _decide(
            service,
            view,
            "notary_name",
            FieldDecisionAction.CORRECT,
            value="Synthetic Notary Four",
            reason="Different notary will attest.",
        )


async def test_attestation_cannot_be_pre_certified_through_a_field_decision() -> None:
    service, _, _, _ = _build()
    view = await _generate(service)
    with pytest.raises(PreCertificationNotPermittedError):
        await _decide(
            service,
            view,
            "attestation_date",
            FieldDecisionAction.CORRECT,
            value="2026-08-14",
            reason="Execution booked.",
        )


async def test_confirming_an_unresolved_field_is_refused() -> None:
    without_nic = {k: v for k, v in CONFIRMED_TRANSFER.items() if k != "rta.party.transferee_nic"}
    service, _, _, _ = _build(without_nic)
    view = await _generate(service)
    with pytest.raises(FieldNotPopulatedError):
        await _decide(service, view, "transferee_nic", FieldDecisionAction.CONFIRM)


async def test_clearing_a_field_requires_a_reason_and_returns_the_token() -> None:
    service, repository, _, _ = _build()
    view = await _generate(service)
    with pytest.raises(FieldDecisionReasonRequiredError):
        await _decide(service, view, "village", FieldDecisionAction.CLEAR)
    updated = await _decide(
        service,
        view,
        "transferor_address",
        FieldDecisionAction.CLEAR,
        reason="Address on the certificate is out of date.",
    )
    stored = repository.field("transferor_address")
    assert stored.rendered_value is None
    assert stored.fact_id is None
    assert stored.unresolved_reason is UnresolvedReason.NO_FACT
    assert updated.form.state is GeneratedFormState.UNRESOLVED


async def test_lawyer_authored_text_is_accepted_where_the_template_permits_it() -> None:
    """Gazette Form 12's only §9.4 free-text slot."""
    service, repository, _, _ = _build({})
    view = await service.generate_form(
        user_id=USER_ID,
        matter_id=MATTER_ID,
        actor_id=USER_ID,
        correlation_id=_CORRELATION,
        subtype_id=MORTGAGE_CANCEL_SUBTYPE_ID,
        subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
    )
    updated = await _decide(
        service,
        view,
        "cancellation_particulars",
        FieldDecisionAction.CORRECT,
        value="Synthetic cancellation particulars entered by the responsible lawyer.",
        reason="Particulars drafted by the responsible lawyer.",
    )
    stored = repository.field("cancellation_particulars")
    assert stored.rendered_value.startswith("Synthetic cancellation particulars")
    # Lawyer-authored text borrows no fact and no evidence (§9.4).
    assert stored.fact_id is None
    assert stored.evidence_reference_ids == ()
    assert stored.reviewed_by == USER_ID
    assert _field(updated, "cancellation_particulars").ai_suggested is False


async def test_an_unknown_field_is_not_found() -> None:
    service, _, _, _ = _build()
    view = await _generate(service)
    with pytest.raises(GeneratedFormFieldNotFoundError):
        await _decide(service, view, "not_a_form_field", FieldDecisionAction.CONFIRM)


async def test_a_field_decision_on_an_approved_form_is_refused() -> None:
    service, repository, _, _ = _build()
    view = await _generate(service)
    stored = repository.forms[view.form.id]
    stored.state = GeneratedFormState.APPROVED
    stored.approved_artifact_hash = "sha256:synthetic-approved"
    with pytest.raises(ApprovedFormImmutableError):
        await _decide(service, view, "transferor_name", FieldDecisionAction.CONFIRM)


# ── Preflight (§9.4) ─────────────────────────────────────────────────────────


async def test_preflight_is_recorded_and_changes_nothing() -> None:
    service, repository, _, audit = _build()
    view = await _generate(service)
    before = repository.forms[view.form.id]
    result = await service.run_preflight(
        user_id=USER_ID, form_id=view.form.id, actor_id=USER_ID, correlation_id=_CORRELATION
    )
    assert "rta.form.preflight-run" in audit.actions()
    assert repository.forms[view.form.id].version == before.version
    assert repository.forms[view.form.id].state is before.state
    assert result.preflight.registration_ready is False


async def test_preflight_on_an_unknown_form_is_not_found() -> None:
    service, _, _, _ = _build()
    with pytest.raises(GeneratedFormNotFoundError):
        await service.run_preflight(
            user_id=USER_ID, form_id="frm_missing", actor_id=USER_ID, correlation_id=_CORRELATION
        )


async def test_another_users_form_is_not_found() -> None:
    service, _, _, _ = _build()
    view = await _generate(service)
    with pytest.raises(GeneratedFormNotFoundError):
        await service.get_form(user_id="usr_other", form_id=view.form.id)


# ── Staleness (§9.5, §10.5, §10.7) ───────────────────────────────────────────


async def _mark_stale(
    service: DraftService, form_id: str, version: int, declared: StaleReason | None = None
) -> FormView:
    return await service.mark_stale(
        user_id=USER_ID,
        form_id=form_id,
        actor_id=USER_ID,
        correlation_id=_CORRELATION,
        expected_version=version,
        declared=declared,
    )


async def test_a_fact_correction_after_generation_marks_the_form_stale() -> None:
    service, repository, facts, audit = _build()
    view = await _generate(service)
    assert view.form.state is GeneratedFormState.REVIEW_READY

    facts.summary = fact_tier(
        {**CONFIRMED_TRANSFER, "rta.party.transferee_nic": "SYNTHETIC-NIC-C"},
        version=2,
        fact_id_suffix="b",
    )
    updated = await _mark_stale(service, view.form.id, view.form.version)

    assert updated.form.stale_reason == StaleReason.FACT_SUPERSEDED.value
    assert updated.form.state is GeneratedFormState.UNRESOLVED
    stored = repository.field("transferee_nic")
    assert stored.rendered_value is None
    assert stored.unresolved_reason is UnresolvedReason.FACT_SUPERSEDED
    assert "rta.form.marked-stale" in audit.actions()


async def test_a_correction_clears_the_lawyers_review_of_the_superseded_value() -> None:
    service, repository, facts, _ = _build()
    view = await _generate(service)
    await _decide(service, view, "transferee_nic", FieldDecisionAction.CONFIRM)
    assert repository.field("transferee_nic").reviewed_by == USER_ID

    facts.summary = fact_tier(
        {**CONFIRMED_TRANSFER, "rta.party.transferee_nic": "SYNTHETIC-NIC-C"},
        version=2,
        fact_id_suffix="b",
    )
    current = repository.forms[view.form.id]
    await _mark_stale(service, view.form.id, current.version)
    stored = repository.field("transferee_nic")
    assert stored.reviewed_by is None
    assert stored.review_decision_id is None


async def test_an_unchanged_record_is_not_marked_stale_and_writes_nothing() -> None:
    service, repository, _, audit = _build()
    view = await _generate(service)
    before = repository.forms[view.form.id].version
    updated = await _mark_stale(service, view.form.id, view.form.version)
    assert updated.form.stale_reason is None
    assert repository.forms[view.form.id].version == before
    assert "rta.form.marked-stale" not in audit.actions()


async def test_a_declared_checklist_recompile_re_evaluates_without_touching_bindings() -> None:
    service, repository, _, _ = _build()
    view = await _generate(service)
    updated = await _mark_stale(
        service, view.form.id, view.form.version, StaleReason.CHECKLIST_RECOMPILED
    )
    assert updated.form.stale_reason == StaleReason.CHECKLIST_RECOMPILED.value
    # Nothing about the evidence moved, so the draft is still review-ready.
    assert updated.form.state is GeneratedFormState.REVIEW_READY
    assert repository.field("transferor_name").rendered_value == "Synthetic Seller One"


async def test_an_approved_snapshot_keeps_its_bindings_when_it_goes_stale() -> None:
    service, repository, facts, _ = _build()
    view = await _generate(service)
    approved = repository.forms[view.form.id]
    approved.state = GeneratedFormState.APPROVED
    approved.approved_artifact_hash = "sha256:synthetic-approved"

    facts.summary = fact_tier(
        {**CONFIRMED_TRANSFER, "rta.party.transferee_nic": "SYNTHETIC-NIC-C"},
        version=2,
        fact_id_suffix="b",
    )
    updated = await _mark_stale(service, view.form.id, approved.version)

    assert updated.form.state is GeneratedFormState.STALE_AFTER_APPROVAL
    assert updated.form.approved_artifact_hash == "sha256:synthetic-approved"
    # The approved bindings are exactly what was approved (§9.5, §10.7).
    assert repository.field("transferee_nic").rendered_value == "SYNTHETIC-NIC-B"
    assert repository.field("transferee_nic").unresolved_reason is None


# ── The snapshot approval pins itself to (§9.6) ──────────────────────────────


async def test_the_snapshot_carries_the_critical_bindings_and_unresolved_fields() -> None:
    without_nic = {k: v for k, v in CONFIRMED_TRANSFER.items() if k != "rta.party.transferee_nic"}
    service, _, _, _ = _build(without_nic)
    view = await _generate(service)
    snapshot = await service.get_form_snapshot(USER_ID, view.form.id)

    assert snapshot is not None
    assert snapshot.template_id == FORM_08_TEMPLATE_ID
    assert snapshot.draft_artifact_hash == view.form.draft_artifact_hash
    assert "transferee_nic" in snapshot.unresolved_field_ids
    assert "attestation_date" in snapshot.unresolved_field_ids
    bound = {binding.field_id for binding in snapshot.critical_fact_bindings}
    assert "transferor_nic" in bound
    assert "transferee_nic" not in bound
    assert all(binding.evidence_reference_ids for binding in snapshot.critical_fact_bindings)


async def test_the_snapshot_of_a_foreign_form_is_none() -> None:
    service, _, _, _ = _build()
    view = await _generate(service)
    assert await service.get_form_snapshot("usr_other", view.form.id) is None


async def test_list_forms_returns_every_version() -> None:
    service, _, _, _ = _build()
    await _generate(service)
    await _generate(service)
    forms, cursor = await service.list_forms(user_id=USER_ID, matter_id=MATTER_ID)
    assert len(forms) == 2
    assert cursor is None

"""The deterministic V0 checks (§7.2, §14.5).

All fixture content is synthetic and labelled as such; nothing here resembles a
real party, NIC, deed, or parcel.

The acceptance criteria that live here:

- a missing input is ``INCONCLUSIVE`` plus a missing-evidence issue, never a
  ``PASS``, and where the definition says absence is not evidence a ``PASS``
  additionally needs a dated register search;
- a part-parcel disposition fails as ``BLOCKING`` / ``STATUTORY`` on s. 47;
- a proposed co-ownership effect fails as ``BLOCKING`` / ``STATUTORY`` on s. 48;
- an owner/transferor mismatch fails as ``BLOCKING`` and stops draft generation;
- an apparently uncancelled mortgage fails as ``HIGH_RISK`` and a settlement
  letter does not clear it;
- an assessment-register name mismatch is a ``WARNING`` and never touches title;
- the seven-working-day attestation calculation is reported as provisional.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.modules.check.domain.policies import blocks_approval, blocks_draft_generation
from src.modules.check.domain.runners import (
    CheckEvaluation,
    CheckInput,
    derive_party_contexts,
    is_provisional,
    run_all,
    run_check,
)
from src.modules.content_governance.contracts import (
    TRANSFER_SALE_SUBTYPE_ID,
    BlockerKind,
    CheckOutcome,
    DispositionScope,
    DisputeStage,
    IssueSeverity,
    IssueState,
    PartyContext,
    require_check,
    templates_for_subtype,
    v0_check_ids,
)
from tests.factories.fact import fact_tier

from .fakes import (
    CLEAN_TRANSFER,
    issue_from,
)

_EVALUATED_AT = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


def _ctx(
    overrides: dict[str, Any] | None = None, *, drop: tuple[str, ...] = (), **kwargs: Any
) -> CheckInput:
    values = dict(CLEAN_TRANSFER)
    values.update(overrides or {})
    for fact_type_id in drop:
        values.pop(fact_type_id, None)
    tier_kwargs = {
        key: kwargs.pop(key)
        for key in ("has_search_evidence", "conflicted", "version", "evidence_suffix")
        if key in kwargs
    }
    return CheckInput(
        matter_id="mat_synthetic",
        facts=fact_tier(values, **tier_kwargs),
        evaluated_at=_EVALUATED_AT,
        search_currency_max_age_days=kwargs.pop("search_currency_max_age_days", 90),
        **kwargs,
    )


def _run(check_id: str, **kwargs: Any) -> CheckEvaluation:
    return run_check(check_id, _ctx(**kwargs))


# ── The happy path exists, so nothing below is vacuously failing ─────────────


def test_a_fully_evidenced_transfer_raises_no_issue() -> None:
    for evaluation in run_all(_ctx()):
        assert evaluation.raises_issue is False, evaluation.explanation_key
        assert evaluation.outcome in {CheckOutcome.PASS, CheckOutcome.NOT_RUN}


def test_every_v0_required_check_has_a_runner() -> None:
    """§14.5 — V0 cannot launch without these, so none may be unimplemented."""
    ran = {evaluation.check_definition_id for evaluation in run_all(_ctx())}
    assert set(v0_check_ids()) <= ran


def test_every_result_pins_the_rule_pack_version_it_ran_under() -> None:
    for evaluation in run_all(_ctx()):
        definition = require_check(evaluation.check_definition_id)
        assert evaluation.check_definition_version == definition.version
        assert evaluation.safety_rule_key == definition.safety_rule_key
        assert evaluation.issue_type_id == definition.issue_type_id


def test_a_result_pins_the_exact_fact_versions_it_read() -> None:
    evaluation = _run("CHK_EXTENT", version=7)
    assert evaluation.input_fact_versions
    assert {pin.version for pin in evaluation.input_fact_versions} == {7}


# ── A missing input is never a pass (§6.4, §7.2) ─────────────────────────────


@pytest.mark.parametrize(
    "check_id, dropped",
    [
        ("CHK_PARTY_IDENTITY", "rta.party.transferee_nic"),
        ("CHK_OWNER_TRANSFEROR", "rta.party.transferor_is_registered_owner"),
        ("CHK_TITLE_REFERENCE", "rta.title.certificate_no"),
        ("CHK_PARCEL_ID", "rta.parcel.parcel_number"),
        ("CHK_EXTENT", "rta.parcel.extent"),
        ("CHK_MORTGAGE_STATUS", "rta.interest.mortgage_status"),
        ("CHK_LEASE_STATUS", "rta.interest.lease_status"),
        ("CHK_ATTESTATION_DEADLINE", "rta.instrument.attestation_date"),
    ],
)
def test_a_missing_input_is_inconclusive_and_raises_a_missing_evidence_issue(
    check_id: str, dropped: str
) -> None:
    evaluation = _run(check_id, drop=(dropped,))
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE
    assert evaluation.raises_issue is True
    assert dropped in evaluation.missing_fact_type_ids
    assert evaluation.blocker_kind is BlockerKind.EVIDENCE


def test_an_unknown_enum_answer_is_a_missing_input_not_a_negative_one() -> None:
    """``UNKNOWN`` is an evidence gap; it never becomes "no" (§4.4, §6.4)."""
    evaluation = _run("CHK_WHOLE_PART", overrides={"rta.instrument.disposition_scope": "UNKNOWN"})
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE


def test_no_evidence_reviewed_is_a_missing_input_not_an_absence_of_mortgage() -> None:
    evaluation = _run(
        "CHK_MORTGAGE_STATUS", overrides={"rta.interest.mortgage_status": "NO_EVIDENCE_REVIEWED"}
    )
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE
    assert "rta.interest.mortgage_status" in evaluation.missing_fact_type_ids


@pytest.mark.parametrize("check_id", ["CHK_MORTGAGE_STATUS", "CHK_LEASE_STATUS"])
def test_absence_is_not_evidence_makes_a_pass_impossible_without_a_search(
    check_id: str,
) -> None:
    """A silent file is not a negative fact: only a dated search settles this.

    ``has_current_search_evidence`` is the authority, not the mere presence of a
    search datetime — `verification` may tighten what counts as *current*, and
    the runner must follow the flag rather than second-guess it.
    """
    assert require_check(check_id).absence_is_not_evidence is True
    evaluation = _run(check_id, has_search_evidence=False)
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE
    assert evaluation.explanation_key.endswith("no_current_search_evidence")


def test_conflicting_inputs_fail_as_an_evidence_problem() -> None:
    """The documents disagree; that is a defect in the evidence, not the deal."""
    evaluation = _run("CHK_PARCEL_ID", conflicted=("rta.parcel.parcel_number",))
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.blocker_kind is BlockerKind.EVIDENCE
    assert evaluation.conflicted_fact_type_ids == ("rta.parcel.parcel_number",)


# ── s. 47: part of a registered parcel (§7.2, §14.6) ─────────────────────────


def test_a_part_parcel_disposition_is_a_statutory_blocker() -> None:
    evaluation = _run(
        "CHK_WHOLE_PART",
        overrides={"rta.instrument.disposition_scope": DispositionScope.PART_OF_PARCEL.value},
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING
    assert evaluation.blocker_kind is BlockerKind.STATUTORY
    assert "s. 47" in " ".join(
        citation.locator for citation in require_check("CHK_WHOLE_PART").sources
    )


def test_the_section_47_blocker_survives_a_missing_extent() -> None:
    """A gap in the evidence does not make a part disposition into a whole one."""
    evaluation = _run(
        "CHK_WHOLE_PART",
        overrides={"rta.instrument.disposition_scope": DispositionScope.PART_OF_PARCEL.value},
        drop=("rta.parcel.extent", "rta.parcel.extent_subject_to_transaction"),
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.blocker_kind is BlockerKind.STATUTORY


def test_a_whole_parcel_claim_over_a_partial_extent_is_still_section_47() -> None:
    evaluation = _run(
        "CHK_WHOLE_PART", overrides={"rta.parcel.extent_subject_to_transaction": "0.0250 ha"}
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.blocker_kind is BlockerKind.STATUTORY


def test_a_part_parcel_blocker_stops_draft_generation() -> None:
    evaluation = _run(
        "CHK_WHOLE_PART",
        overrides={"rta.instrument.disposition_scope": DispositionScope.PART_OF_PARCEL.value},
    )
    assert blocks_draft_generation([issue_from(evaluation)]) is True


# ── s. 48: prohibited co-ownership effect ────────────────────────────────────


def test_a_proposed_coownership_effect_is_a_statutory_blocker() -> None:
    evaluation = _run("CHK_COOWNERSHIP", overrides={"rta.party.creates_coownership": True})
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING
    assert evaluation.blocker_kind is BlockerKind.STATUTORY
    assert "s. 48" in " ".join(
        citation.locator for citation in require_check("CHK_COOWNERSHIP").sources
    )


def test_an_undivided_interest_over_a_sole_title_confers_coownership() -> None:
    evaluation = _run(
        "CHK_COOWNERSHIP",
        overrides={
            "rta.instrument.disposition_scope": DispositionScope.UNDIVIDED_INTEREST.value,
            "rta.title.class": "FIRST_CLASS",
        },
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.blocker_kind is BlockerKind.STATUTORY


# ── Owner versus transferor ──────────────────────────────────────────────────


def test_an_owner_transferor_mismatch_blocks_draft_generation() -> None:
    evaluation = _run(
        "CHK_OWNER_TRANSFEROR", overrides={"rta.party.transferor_is_registered_owner": False}
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING
    assert blocks_draft_generation([issue_from(evaluation)]) is True


def test_a_name_variant_alone_is_not_a_mismatch() -> None:
    """The conclusion is the lawyer's; an alias is a real explanation (§7.2)."""
    evaluation = _run(
        "CHK_OWNER_TRANSFEROR",
        overrides={"rta.party.transferor_name": "S. Seller One", "rta.title.class": "FIRST_CLASS"},
    )
    assert evaluation.outcome is CheckOutcome.PASS


def test_one_identity_on_both_sides_escalates_to_blocking() -> None:
    evaluation = _run(
        "CHK_PARTY_IDENTITY", overrides={"rta.party.transferee_nic": "SYNTHETIC-NIC-A"}
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING


# ── Mortgage: a paid loan is not a cancelled registered interest ─────────────


def test_an_apparently_uncancelled_mortgage_is_high_risk_and_blocks_approval() -> None:
    evaluation = _run(
        "CHK_MORTGAGE_STATUS", overrides={"rta.interest.mortgage_status": "APPARENTLY_UNCANCELLED"}
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.HIGH_RISK
    issues = [issue_from(evaluation)]
    assert blocks_approval(issues) is True
    assert blocks_draft_generation(issues) is False


def test_a_settlement_letter_alone_does_not_clear_the_mortgage() -> None:
    """§15.4 — the register, not the bank's letter, says whether it is cancelled."""
    evaluation = _run(
        "CHK_MORTGAGE_STATUS",
        overrides={
            "rta.interest.mortgage_status": "DISCHARGE_CLAIMED_NOT_REGISTERED",
            "rta.interest.discharge_evidence_kind": "SETTLEMENT_LETTER",
        },
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert blocks_approval([issue_from(evaluation)]) is True


def test_a_registered_cancellation_clears_the_mortgage() -> None:
    evaluation = _run(
        "CHK_MORTGAGE_STATUS", overrides={"rta.interest.mortgage_status": "CANCELLATION_REGISTERED"}
    )
    assert evaluation.outcome is CheckOutcome.PASS


# ── Lease, occupation, caveats, and litigation ───────────────────────────────


def test_a_current_registered_lease_is_high_risk() -> None:
    evaluation = _run(
        "CHK_LEASE_STATUS", overrides={"rta.interest.lease_status": "REGISTERED_AND_CURRENT"}
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.HIGH_RISK


def test_third_party_possession_is_reported_even_with_no_registered_lease() -> None:
    evaluation = _run(
        "CHK_LEASE_STATUS", overrides={"rta.interest.occupation_status": "THIRD_PARTY_OCCUPATION"}
    )
    assert evaluation.outcome is CheckOutcome.FAIL


def test_an_unresolved_caveat_blocks() -> None:
    evaluation = _run(
        "CHK_CAVEAT_LITIGATION",
        overrides={"rta.interest.caveat_or_notice_status": "PRESENT_UNRESOLVED"},
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING


@pytest.mark.parametrize(
    "stage",
    [
        DisputeStage.S21_DC_REFERRED,
        DisputeStage.S22_APPEAL_FILED,
        DisputeStage.COURT_INQUIRY_PENDING,
        DisputeStage.S29_CHALLENGE_NOTED,
        DisputeStage.RECTIFICATION_PENDING,
    ],
)
def test_a_live_proceeding_is_a_hold_even_without_a_search(stage: DisputeStage) -> None:
    evaluation = _run(
        "CHK_CAVEAT_LITIGATION",
        overrides={"rta.process.dispute_stage": stage.value},
        has_search_evidence=False,
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.explanation_key.endswith("litigation_hold")


def test_a_section_12_notice_stops_automated_output_without_calling_it_litigation() -> None:
    evaluation = _run(
        "CHK_CAVEAT_LITIGATION",
        overrides={"rta.process.dispute_stage": DisputeStage.S12_NOTICE_PUBLISHED.value},
    )
    assert evaluation.explanation_key.endswith("title_settlement_in_progress")


def test_a_confirmed_final_register_clears_the_dispute_check() -> None:
    evaluation = _run(
        "CHK_CAVEAT_LITIGATION",
        overrides={"rta.process.dispute_stage": DisputeStage.FINAL_REGISTER_CONFIRMED.value},
    )
    assert evaluation.outcome is CheckOutcome.PASS


# ── Authority checks apply only where the routing says they do ───────────────


def test_probate_and_company_checks_do_not_run_on_a_natural_person_transfer() -> None:
    for check_id in ("CHK_PROBATE_AUTHORITY", "CHK_COMPANY_AUTHORITY", "CHK_POA_SCOPE"):
        evaluation = _run(check_id)
        assert evaluation.outcome is CheckOutcome.NOT_RUN
        assert evaluation.raises_issue is False


def test_an_incomplete_transmission_blocks() -> None:
    evaluation = _run(
        "CHK_PROBATE_AUTHORITY",
        overrides={
            "rta.process.transmission_completed": False,
            "rta.process.probate_path": "TESTATE",
        },
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING


def test_missing_company_authority_is_blocking_not_a_warning() -> None:
    """§7.2 — "BLOCKING if authority unresolved", and absent evidence is unresolved."""
    evaluation = _run(
        "CHK_COMPANY_AUTHORITY",
        overrides={"rta.org.company_name": "Synthetic Holdings (Pvt) Ltd"},
    )
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE
    assert evaluation.default_severity is IssueSeverity.BLOCKING


def test_attorney_execution_is_a_v0_exclusion() -> None:
    evaluation = _run(
        "CHK_POA_SCOPE", party_contexts=frozenset({PartyContext.ATTORNEY_POWER_OF_ATTORNEY})
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.blocker_kind is BlockerKind.V0_SCOPE


def test_party_contexts_are_derived_from_confirmed_facts_when_not_supplied() -> None:
    contexts = derive_party_contexts(
        fact_tier({**CLEAN_TRANSFER, "rta.org.company_number": "PV-1"})
    )
    assert PartyContext.COMPANY in contexts


# ── The assessment register is not title (§1.2, §7.2, §Executive 9) ──────────


def test_an_assessment_name_mismatch_is_a_warning_and_nothing_more() -> None:
    evaluation = _run(
        "CHK_ASSESSMENT_NAME",
        overrides={"rta.local.assessment_register_name": "Synthetic Previous Occupier"},
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.WARNING
    issue = issue_from(evaluation)
    # It must never conclude, or contribute to concluding, that the seller lacks
    # title: it does not gate drafting or approval, and it raises its own issue
    # type rather than the owner/transferor one.
    assert blocks_draft_generation([issue]) is False
    assert blocks_approval([issue]) is False
    assert issue.issue_type_id == "rta.issue.assessment_name_mismatch"
    assert issue.blocker_kind is not BlockerKind.STATUTORY


def test_an_assessment_mismatch_leaves_the_owner_transferor_check_passing() -> None:
    ctx = _ctx(overrides={"rta.local.assessment_register_name": "Synthetic Previous Occupier"})
    assert run_check("CHK_ASSESSMENT_NAME", ctx).outcome is CheckOutcome.FAIL
    assert run_check("CHK_OWNER_TRANSFEROR", ctx).outcome is CheckOutcome.PASS
    assert run_check("CHK_TITLE_REFERENCE", ctx).outcome is CheckOutcome.PASS


# ── Extent comparison ────────────────────────────────────────────────────────


def test_a_transaction_extent_larger_than_the_parcel_escalates_to_blocking() -> None:
    evaluation = _run(
        "CHK_EXTENT", overrides={"rta.parcel.extent_subject_to_transaction": "0.9 ha"}
    )
    assert evaluation.default_severity is IssueSeverity.BLOCKING


def test_a_smaller_transaction_extent_is_high_risk_for_the_lawyer_to_judge() -> None:
    evaluation = _run(
        "CHK_EXTENT", overrides={"rta.parcel.extent_subject_to_transaction": "0.0400 ha"}
    )
    assert evaluation.default_severity is IssueSeverity.HIGH_RISK
    assert evaluation.blocker_kind is BlockerKind.PROFESSIONAL_JUDGMENT


def test_extents_in_different_units_are_not_silently_converted() -> None:
    evaluation = _run(
        "CHK_EXTENT", overrides={"rta.parcel.extent_subject_to_transaction": "500 sqm"}
    )
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE
    assert evaluation.is_provisional is True


# ── Form completeness (§9.3, §9.4) ───────────────────────────────────────────


def test_form_required_fields_does_not_run_without_a_chosen_template() -> None:
    evaluation = _run("CHK_FORM_REQUIRED_FIELDS")
    assert evaluation.outcome is CheckOutcome.NOT_RUN


def test_an_unresolved_required_field_blocks_and_needs_no_human_conclusion() -> None:
    evaluation = _run("CHK_FORM_REQUIRED_FIELDS", subtype_id=TRANSFER_SALE_SUBTYPE_ID)
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.BLOCKING
    assert evaluation.missing_fact_type_ids
    # The only mechanical check in the catalogue: completeness against a field
    # list needs no legal conclusion, because each fact was already confirmed.
    assert evaluation.requires_human_conclusion is False


def test_a_complete_form_still_needs_a_current_search_to_pass() -> None:
    complete = dict(CLEAN_TRANSFER)
    for template in templates_for_subtype(TRANSFER_SALE_SUBTYPE_ID):
        for mapping in template.field_mappings:
            if mapping.required and mapping.fact_type_id:
                complete.setdefault(mapping.fact_type_id, "SYNTHETIC-VALUE")
    resolved = _run(
        "CHK_FORM_REQUIRED_FIELDS", overrides=complete, subtype_id=TRANSFER_SALE_SUBTYPE_ID
    )
    assert resolved.outcome is CheckOutcome.PASS
    without_search = run_check(
        "CHK_FORM_REQUIRED_FIELDS",
        _ctx(overrides=complete, subtype_id=TRANSFER_SALE_SUBTYPE_ID, has_search_evidence=False),
    )
    assert without_search.outcome is CheckOutcome.INCONCLUSIVE


# ── Currency and the seven-working-day deadline ──────────────────────────────


def test_currency_is_unknown_rather_than_current_when_no_policy_is_configured() -> None:
    evaluation = _run("CHK_DOCUMENT_CURRENCY", search_currency_max_age_days=None)
    assert evaluation.outcome is CheckOutcome.INCONCLUSIVE
    assert evaluation.is_provisional is True


def test_a_stale_register_search_is_high_risk() -> None:
    evaluation = _run(
        "CHK_DOCUMENT_CURRENCY",
        overrides={"rta.title.register_search_datetime": "2025-01-01"},
        search_currency_max_age_days=30,
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.default_severity is IssueSeverity.HIGH_RISK


def test_the_attestation_deadline_is_always_reported_as_provisional() -> None:
    """§16.4 item 5 — no verified Sri Lankan public-holiday calendar exists here."""
    for attested, expected in (
        ("2026-08-14", CheckOutcome.PASS),
        ("2026-08-06", CheckOutcome.FAIL),
        ("2026-07-01", CheckOutcome.FAIL),
    ):
        evaluation = _run(
            "CHK_ATTESTATION_DEADLINE", overrides={"rta.instrument.attestation_date": attested}
        )
        assert evaluation.outcome is expected, attested
        assert is_provisional(evaluation.explanation_key), attested


def test_a_passed_attestation_deadline_is_high_risk_for_the_responsible_lawyer() -> None:
    evaluation = _run(
        "CHK_ATTESTATION_DEADLINE", overrides={"rta.instrument.attestation_date": "2026-07-01"}
    )
    assert evaluation.default_severity is IssueSeverity.HIGH_RISK
    assert evaluation.blocker_kind is BlockerKind.PROFESSIONAL_JUDGMENT
    assert evaluation.explanation_key.endswith("deadline_passed")


def test_the_seven_working_days_skip_weekends() -> None:
    """2026-08-14 is a Friday; seven working days later is 2026-08-25, a Tuesday."""
    evaluation = run_check(
        "CHK_ATTESTATION_DEADLINE",
        CheckInput(
            matter_id="mat_synthetic",
            facts=fact_tier(CLEAN_TRANSFER),
            evaluated_at=datetime(2026, 8, 26, 9, 0, tzinfo=UTC),
        ),
    )
    assert evaluation.outcome is CheckOutcome.FAIL
    assert evaluation.explanation_key.endswith("deadline_passed")


# ── Every raised issue starts OPEN at the default severity (§10.6) ───────────


def test_a_raised_issue_starts_open_and_carries_its_legal_basis() -> None:
    evaluation = _run(
        "CHK_WHOLE_PART",
        overrides={"rta.instrument.disposition_scope": DispositionScope.PART_OF_PARCEL.value},
    )
    issue = issue_from(evaluation)
    assert issue.state is IssueState.OPEN
    assert issue.severity is evaluation.default_severity
    assert issue.source_record_ids

"""V0 eligibility and the mandatory legal stop conditions.

The spec's §17 acceptance criteria that live here:

- a part-parcel answer creates the s. 47 blocker and routes to subdivision;
- a proposed co-ownership effect creates the s. 48 blocker;
- an owner/transferor mismatch blocks;
- an apparently uncancelled mortgage cannot disappear because a settlement
  letter was uploaded;
- company, probate, condominium, and dispute matters leave the automated path
  without losing their work.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.modules.content_governance.domain.enums import (
    AutomationScope,
    BlockerKind,
    DispositionScope,
    DisputeStage,
    IssueSeverity,
    MatterState,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
    TriState,
)
from src.modules.content_governance.domain.rta import eligibility
from src.modules.content_governance.domain.rta.eligibility import (
    MORTGAGE_CANCEL_SUBTYPE_ID,
    TRANSFER_SALE_SUBTYPE_ID,
    EligibilityInput,
)
from src.modules.content_governance.domain.rta.fact_values import (
    EncumbranceStatus,
    NoticeStatus,
    OccupationStatus,
)


def _clean_transfer() -> EligibilityInput:
    """Every §2.3 predicate satisfied except the two that cannot be today.

    ``template_verified`` and source re-verification are deliberately left in
    their real state by the callers that need them; this helper sets them true so
    the other gates can be tested in isolation.
    """
    return EligibilityInput(
        subtype_id=TRANSFER_SALE_SUBTYPE_ID,
        subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
        title_status=TitleStatus.RTA_REGISTERED,
        title_certificate_available=TriState.YES,
        parcel_kind=ParcelKind.ORDINARY,
        disposition_scope=DispositionScope.WHOLE_REGISTERED_PARCEL,
        party_contexts=frozenset({PartyContext.NATURAL_PERSONS_ONLY}),
        transferor_is_registered_owner=TriState.YES,
        transmission_completed=TriState.NOT_APPLICABLE,
        life_interest_present=TriState.NO,
        special_condition_present=TriState.NO,
        coowners_present=TriState.NO,
        creates_coownership=TriState.NO,
        dispute_stage=DisputeStage.NO_INDICIA_FOUND,
        active_court_proceeding=TriState.NO,
        notice_status=NoticeStatus.NOT_FOUND_IN_CURRENT_SEARCH,
        mortgage_status=EncumbranceStatus.NOT_FOUND_IN_CURRENT_SEARCH,
        lease_status=EncumbranceStatus.NOT_FOUND_IN_CURRENT_SEARCH,
        occupation_status=OccupationStatus.OWNER_OCCUPIED,
        unconfirmed_critical_fact_type_ids=(),
        template_verified=True,
        source_reverification_required=False,
    )


def _gate(decision: eligibility.EligibilityDecision, gate_id: str) -> eligibility.Gate:
    matches = [gate for gate in decision.gates if gate.id == gate_id]
    assert matches, f"gate {gate_id} was not evaluated"
    return matches[0]


# ── The happy path exists, so the gates are not vacuously failing ────────────


def test_a_fully_satisfied_transfer_is_v0_automated() -> None:
    decision = eligibility.evaluate(_clean_transfer())
    assert decision.automation_scope is AutomationScope.V0_AUTOMATED
    assert decision.unmet_gate_ids == ()
    assert decision.exception_state is None


def test_an_unverified_template_alone_prevents_v0() -> None:
    """The real state of this repository: no template is lawyer-approved (§9.5)."""
    decision = eligibility.evaluate(
        replace(_clean_transfer(), template_verified=False, source_reverification_required=True)
    )
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED
    assert "V0_TEMPLATE_AND_SOURCES_VERIFIED" in decision.unmet_gate_ids


# ── Statutory stop conditions (§14.6) ────────────────────────────────────────


def test_part_parcel_disposition_creates_the_section_47_statutory_blocker() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), disposition_scope=DispositionScope.PART_OF_PARCEL)
    )
    gate = _gate(decision, "STATUTORY_S47_PART_PARCEL")
    assert gate.satisfied is False
    assert gate.severity is IssueSeverity.BLOCKING
    assert gate.blocker_kind is BlockerKind.STATUTORY
    assert gate.is_statutory_blocker
    assert "s. 47" in " ".join(citation.locator for citation in gate.sources)
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED


def test_the_section_47_blocker_fires_even_when_the_subtype_is_not_a_pilot() -> None:
    """A statutory prohibition does not depend on whether Draftly would draft."""
    decision = eligibility.evaluate(
        EligibilityInput(
            subtype_id="lk.rta.instrument.gift",
            disposition_scope=DispositionScope.PART_OF_PARCEL,
        )
    )
    assert _gate(decision, "STATUTORY_S47_PART_PARCEL").is_statutory_blocker


def test_proposed_coownership_creates_the_section_48_statutory_blocker() -> None:
    decision = eligibility.evaluate(replace(_clean_transfer(), creates_coownership=TriState.YES))
    gate = _gate(decision, "STATUTORY_S48_COOWNERSHIP")
    assert gate.is_statutory_blocker
    assert "s. 48" in " ".join(citation.locator for citation in gate.sources)


def test_owner_transferor_mismatch_blocks() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), transferor_is_registered_owner=TriState.NO)
    )
    gate = _gate(decision, "BLOCK_OWNER_TRANSFEROR_MISMATCH")
    assert gate.satisfied is False
    assert gate.severity is IssueSeverity.BLOCKING
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED


def test_unknown_ownership_is_an_unmet_predicate_but_not_a_mismatch() -> None:
    """UNKNOWN is an evidence gap, not a contradiction (§4.1)."""
    decision = eligibility.evaluate(
        replace(_clean_transfer(), transferor_is_registered_owner=TriState.UNKNOWN)
    )
    assert _gate(decision, "BLOCK_OWNER_TRANSFEROR_MISMATCH").satisfied is True
    assert _gate(decision, "V0_TRANSFEROR_IS_CURRENT_REGISTERED_OWNER").satisfied is False


def test_identifier_conflict_blocks() -> None:
    decision = eligibility.evaluate(replace(_clean_transfer(), identifier_conflict_present=True))
    assert _gate(decision, "BLOCK_TITLE_OR_PARCEL_IDENTIFIER_CONFLICT").satisfied is False


def test_uncompleted_transmission_blocks() -> None:
    decision = eligibility.evaluate(
        replace(
            _clean_transfer(),
            party_contexts=frozenset({PartyContext.ESTATE_OR_DECEASED}),
            transmission_completed=TriState.NO,
        )
    )
    gate = _gate(decision, "BLOCK_UNCOMPLETED_TRANSMISSION")
    assert gate.satisfied is False
    assert gate.blocker_kind is BlockerKind.STATUTORY


def test_unconfirmed_critical_facts_block() -> None:
    decision = eligibility.evaluate(
        replace(
            _clean_transfer(),
            unconfirmed_critical_fact_type_ids=("rta.parcel.extent",),
        )
    )
    assert _gate(decision, "BLOCK_MISSING_CRITICAL_FORM_FACTS").satisfied is False
    assert _gate(decision, "V0_ALL_CRITICAL_FACTS_LAWYER_CONFIRMED").satisfied is False


# ── Mortgage: a paid loan is not a cancelled registered interest ─────────────


@pytest.mark.parametrize(
    "status",
    [
        EncumbranceStatus.NO_EVIDENCE_REVIEWED,
        EncumbranceStatus.APPARENTLY_UNCANCELLED,
        EncumbranceStatus.REGISTERED_AND_CURRENT,
        EncumbranceStatus.DISCHARGE_CLAIMED_NOT_REGISTERED,
    ],
)
def test_an_unresolved_mortgage_blocks_transfer_approval(status: EncumbranceStatus) -> None:
    decision = eligibility.evaluate(replace(_clean_transfer(), mortgage_status=status))
    gate = _gate(decision, "BLOCK_APPARENTLY_UNCANCELLED_MORTGAGE")
    assert gate.satisfied is False
    assert gate.severity is IssueSeverity.HIGH_RISK
    assert _gate(decision, "V0_NO_UNRESOLVED_MORTGAGE").satisfied is False


def test_a_settlement_letter_does_not_clear_the_mortgage_gate() -> None:
    """§15.4 — a paid loan is not automatically a cancelled registered interest."""
    decision = eligibility.evaluate(
        replace(
            _clean_transfer(),
            mortgage_status=EncumbranceStatus.DISCHARGE_CLAIMED_NOT_REGISTERED,
        )
    )
    assert decision.automation_scope is not AutomationScope.V0_AUTOMATED
    assert "V0_NO_UNRESOLVED_MORTGAGE" in decision.unmet_gate_ids


def test_a_registered_cancellation_does_clear_the_mortgage_gate() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), mortgage_status=EncumbranceStatus.CANCELLATION_REGISTERED)
    )
    assert _gate(decision, "V0_NO_UNRESOLVED_MORTGAGE").satisfied is True
    assert decision.automation_scope is AutomationScope.V0_AUTOMATED


# ── Route-out cases (§15.2, §15.3, §15.5, §15.6, §15.7) ─────────────────────


def test_a_company_party_leaves_the_automated_path() -> None:
    decision = eligibility.evaluate(
        replace(
            _clean_transfer(),
            party_contexts=frozenset({PartyContext.NATURAL_PERSONS_ONLY, PartyContext.COMPANY}),
        )
    )
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED
    assert decision.exception_state is MatterState.MANUAL_SUPPORTED
    assert "V0_PARTIES_ARE_NATURAL_PERSONS" in decision.unmet_gate_ids


def test_a_power_of_attorney_leaves_the_automated_path() -> None:
    decision = eligibility.evaluate(
        replace(
            _clean_transfer(),
            party_contexts=frozenset(
                {PartyContext.NATURAL_PERSONS_ONLY, PartyContext.ATTORNEY_POWER_OF_ATTORNEY}
            ),
        )
    )
    assert "V0_NO_POWER_OF_ATTORNEY" in decision.unmet_gate_ids


def test_a_condominium_unit_leaves_the_automated_path() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), parcel_kind=ParcelKind.CONDOMINIUM_UNIT)
    )
    assert "V0_PARCEL_IS_ORDINARY" in decision.unmet_gate_ids
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED


def test_a_life_interest_leaves_the_automated_path() -> None:
    decision = eligibility.evaluate(replace(_clean_transfer(), life_interest_present=TriState.YES))
    assert "V0_NO_LIFE_INTEREST_OR_SPECIAL_CONDITION" in decision.unmet_gate_ids


def test_title_not_yet_registered_routes_to_initial_compilation_triage() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), title_status=TitleStatus.INITIAL_COMPILATION)
    )
    assert "V0_CURRENT_TITLE_REGISTER_CONFIRMED" in decision.unmet_gate_ids
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED


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
def test_live_litigation_becomes_a_litigation_hold(stage: DisputeStage) -> None:
    decision = eligibility.evaluate(replace(_clean_transfer(), dispute_stage=stage))
    assert decision.automation_scope is AutomationScope.LITIGATION_HOLD
    assert decision.exception_state is MatterState.LITIGATION_HOLD
    assert _gate(decision, "HOLD_ACTIVE_LITIGATION").is_statutory_blocker


@pytest.mark.parametrize(
    "stage",
    [
        DisputeStage.S12_NOTICE_PUBLISHED,
        DisputeStage.CLAIMS_FILED,
        DisputeStage.S13_INVESTIGATION_PENDING,
        DisputeStage.CONCILIATION_PENDING,
        DisputeStage.S14_DECLARATION_PUBLISHED,
    ],
)
def test_settlement_stages_block_automation_without_calling_it_litigation(
    stage: DisputeStage,
) -> None:
    """§8.4 — a s. 12 notice is not proof of a contest, but it is not V0 either."""
    decision = eligibility.evaluate(replace(_clean_transfer(), dispute_stage=stage))
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED
    assert _gate(decision, "HOLD_ACTIVE_LITIGATION").satisfied is True


def test_a_final_confirmed_register_can_return_to_the_automated_path() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), dispute_stage=DisputeStage.FINAL_REGISTER_CONFIRMED)
    )
    assert decision.automation_scope is AutomationScope.V0_AUTOMATED


def test_an_unresolved_caveat_leaves_the_automated_path() -> None:
    decision = eligibility.evaluate(
        replace(_clean_transfer(), notice_status=NoticeStatus.PRESENT_UNRESOLVED)
    )
    assert "V0_NO_UNRESOLVED_NOTICE_OR_SEIZURE" in decision.unmet_gate_ids


def test_no_reviewed_notice_evidence_is_not_treated_as_no_caveat() -> None:
    """Absence of an uploaded search is not evidence there is no caveat (§6.4)."""
    decision = eligibility.evaluate(
        replace(_clean_transfer(), notice_status=NoticeStatus.NO_EVIDENCE_REVIEWED)
    )
    assert "V0_NO_UNRESOLVED_NOTICE_OR_SEIZURE" in decision.unmet_gate_ids


# ── Failure never destroys the matter (§2.3) ──────────────────────────────────


def test_a_failed_predicate_never_produces_a_terminal_state() -> None:
    for mutation in (
        {"parcel_kind": ParcelKind.CONDOMINIUM_UNIT},
        {"disposition_scope": DispositionScope.PART_OF_PARCEL},
        {"transferor_is_registered_owner": TriState.NO},
        {"dispute_stage": DisputeStage.S21_DC_REFERRED},
    ):
        decision = eligibility.evaluate(replace(_clean_transfer(), **mutation))
        assert decision.exception_state in {
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
        }
        assert decision.exception_state is not MatterState.CANCELLED
        assert decision.exception_state is not MatterState.CLOSED


def test_every_unmet_gate_carries_a_reason_key_and_a_source() -> None:
    decision = eligibility.evaluate(EligibilityInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID))
    unmet = [gate for gate in decision.gates if not gate.satisfied]
    assert unmet
    for gate in unmet:
        assert gate.reason_key.startswith("rta.gate.")
        assert gate.sources


# ── Subtype scoping ──────────────────────────────────────────────────────────


def test_a_matter_with_no_chosen_subtype_is_assessing_not_v0() -> None:
    decision = eligibility.evaluate(EligibilityInput())
    assert decision.automation_scope is AutomationScope.ASSESSING


def test_a_non_pilot_subtype_is_explicitly_out_of_the_pilot() -> None:
    decision = eligibility.evaluate(replace(_clean_transfer(), subtype_id="lk.rta.instrument.gift"))
    assert _gate(decision, "V0_SUBTYPE_IS_A_PILOT_PATH").satisfied is False
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED


def test_a_provisional_subtype_cannot_reach_v0() -> None:
    """§Executive 6 — the exact instrument needs the lawyer's confirmation."""
    decision = eligibility.evaluate(
        replace(_clean_transfer(), subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL)
    )
    assert "V0_SUBTYPE_LAWYER_CONFIRMED" in decision.unmet_gate_ids


# ── The focused Form 12 pilot (§2.3 closing paragraph) ───────────────────────


def _clean_mortgage_cancellation() -> EligibilityInput:
    return replace(
        _clean_transfer(),
        subtype_id=MORTGAGE_CANCEL_SUBTYPE_ID,
        mortgage_status=EncumbranceStatus.REGISTERED_AND_CURRENT,
        identified_mortgage_reference=True,
        mortgagee_authority_confirmed=TriState.YES,
        discharge_evidence_sufficient=TriState.YES,
        cancellation_route_confirmed=TriState.YES,
    )


def test_a_fully_evidenced_mortgage_cancellation_is_v0_automated() -> None:
    decision = eligibility.evaluate(_clean_mortgage_cancellation())
    assert decision.automation_scope is AutomationScope.V0_AUTOMATED


def test_the_registered_mortgage_gate_does_not_block_its_own_cancellation() -> None:
    """A Form 12 matter exists *because* a mortgage is registered."""
    decision = eligibility.evaluate(_clean_mortgage_cancellation())
    assert _gate(decision, "BLOCK_APPARENTLY_UNCANCELLED_MORTGAGE").satisfied is True


@pytest.mark.parametrize(
    "gate_id, mutation",
    [
        ("V0_F12_MORTGAGE_IDENTIFIED", {"identified_mortgage_reference": False}),
        (
            "V0_F12_RELEASOR_AUTHORITY_CONFIRMED",
            {"mortgagee_authority_confirmed": TriState.UNKNOWN},
        ),
        (
            "V0_F12_DISCHARGE_EVIDENCE_SUFFICIENT",
            {"discharge_evidence_sufficient": TriState.NO},
        ),
        (
            "V0_F12_CANCELLATION_ROUTE_CONFIRMED",
            {"cancellation_route_confirmed": TriState.UNKNOWN},
        ),
    ],
)
def test_each_form_12_predicate_is_load_bearing(gate_id: str, mutation: dict[str, object]) -> None:
    decision = eligibility.evaluate(replace(_clean_mortgage_cancellation(), **mutation))
    assert _gate(decision, gate_id).satisfied is False
    assert decision.automation_scope is AutomationScope.MANUAL_SUPPORTED

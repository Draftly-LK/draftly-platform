"""Routing derivation: what intake answers imply, before any eligibility judgement."""

from __future__ import annotations

from typing import Any

import pytest

from src.modules.content_governance.contracts import (
    ALL_QUESTIONS,
    TRANSFER_SALE_SUBTYPE_ID,
    DispositionScope,
    DisputeStage,
    EncumbranceStatus,
    MatterFamily,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
    TriState,
)
from src.modules.matter.domain import routing as r
from src.modules.matter.domain.routing import (
    LiveAnswer,
    MatterFactSnapshot,
    build_eligibility_input,
    derive_routing,
)


def answers(**values: Any) -> dict[str, LiveAnswer]:
    return {
        getattr(r, name): LiveAnswer(value=value, lawyer_confirmed=True)
        for name, value in values.items()
    }


def test_no_answers_means_unknown_everywhere_not_no() -> None:
    derived = derive_routing({})

    assert derived.title_status is TitleStatus.UNKNOWN
    assert derived.parcel_kind is ParcelKind.UNKNOWN
    assert derived.disposition_scope is DispositionScope.UNKNOWN
    assert derived.party_contexts == frozenset()
    assert derived.dispute_stage is DisputeStage.NO_INDICIA_FOUND
    assert derived.subtype_id is None
    assert derived.family_id is None
    # Silence about a mortgage or a lease activates both checklists (§6.4), and
    # unproven RTA coverage opens initial-compilation triage.
    assert derived.activated_conditional_module_ids == frozenset(
        {r.MODULE_MORTGAGE, r.MODULE_LEASE, r.MODULE_INITIAL_COMPILATION}
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("YES", TitleStatus.RTA_REGISTERED),
        ("NO", TitleStatus.INITIAL_COMPILATION),
        ("UNKNOWN", TitleStatus.UNKNOWN),
        ("garbage", TitleStatus.UNKNOWN),
    ],
)
def test_title_status_follows_the_regime_question(value: str, expected: TitleStatus) -> None:
    derived = derive_routing(answers(Q_REGIME=value))
    assert derived.title_status is expected
    registered = expected is TitleStatus.RTA_REGISTERED
    assert (
        r.MODULE_INITIAL_COMPILATION in derived.activated_conditional_module_ids
    ) is not registered


def test_explicit_no_clears_the_mortgage_and_lease_modules() -> None:
    derived = derive_routing(answers(Q_REGIME="YES", Q_MORTGAGE="NO", Q_LEASE_OCCUPATION="NO"))
    assert derived.activated_conditional_module_ids == frozenset()


def test_unrecognised_choice_values_fall_back_to_unknown() -> None:
    derived = derive_routing(
        answers(Q_PARCEL_KIND="HOUSEBOAT", Q_SCOPE="HALF", Q_PARTY_CONTEXT=["ALIENS", "COMPANY"])
    )
    assert derived.parcel_kind is ParcelKind.UNKNOWN
    assert derived.disposition_scope is DispositionScope.UNKNOWN
    assert derived.party_contexts == frozenset({PartyContext.COMPANY})


def test_none_and_non_sequence_values_are_ignored() -> None:
    derived = derive_routing(answers(Q_PARCEL_KIND=None, Q_PARTY_CONTEXT=None, Q_SCOPE=None))
    assert derived.parcel_kind is ParcelKind.UNKNOWN
    assert derived.party_contexts == frozenset()
    assert derive_routing(answers(Q_PARTY_CONTEXT=42)).party_contexts == frozenset()


def test_a_single_string_party_context_is_accepted() -> None:
    derived = derive_routing(answers(Q_PARTY_CONTEXT="PUBLIC_BODY"))
    assert derived.party_contexts == frozenset({PartyContext.PUBLIC_BODY})
    assert r.MODULE_STATE_LAND in derived.activated_conditional_module_ids


def test_deceased_owner_via_q08_is_the_same_fact_as_ticking_estate() -> None:
    via_q08 = derive_routing(answers(Q_OWNER_DEAD="YES"))
    via_q05 = derive_routing(answers(Q_PARTY_CONTEXT=["ESTATE_OR_DECEASED"]))

    assert PartyContext.ESTATE_OR_DECEASED in via_q08.party_contexts
    assert r.MODULE_ESTATE in via_q08.activated_conditional_module_ids
    assert r.MODULE_ESTATE in via_q05.activated_conditional_module_ids
    # Q05 opens both follow-ups; Q08 was already answered on the other path.
    assert via_q05.triggered_question_ids[:2] == (r.Q_OWNER_DEAD, r.Q_PROBATE_PATH)
    assert r.Q_OWNER_DEAD not in via_q08.triggered_question_ids
    assert r.Q_PROBATE_PATH in via_q08.triggered_question_ids


def test_power_of_attorney_answer_adds_the_context_and_module() -> None:
    derived = derive_routing(answers(Q_POA="YES"))
    assert PartyContext.ATTORNEY_POWER_OF_ATTORNEY in derived.party_contexts
    assert r.MODULE_POA in derived.activated_conditional_module_ids


@pytest.mark.parametrize(
    ("answer", "module"),
    [
        ({"Q_PARCEL_KIND": "CONDOMINIUM_UNIT"}, r.MODULE_CONDOMINIUM),
        ({"Q_PARCEL_KIND": "CONVERSION_TO_CONDOMINIUM"}, r.MODULE_CONDOMINIUM),
        ({"Q_SCOPE": "PART_OF_PARCEL"}, r.MODULE_SUBDIVISION),
        ({"Q_SCOPE": "UNDIVIDED_INTEREST"}, r.MODULE_COOWNERS),
        ({"Q_COOWNERS": "YES"}, r.MODULE_COOWNERS),
        ({"Q_DISPUTE": "YES"}, r.MODULE_LITIGATION),
        ({"Q_ENCUMBRANCE": "YES"}, r.MODULE_LITIGATION),
        ({"Q_LIFE_INTEREST": "YES"}, r.MODULE_LIFE_INTEREST),
        ({"Q_SERVITUDE": "YES"}, r.MODULE_SERVITUDE),
        ({"Q_BUILDING": "YES"}, r.MODULE_BUILDING),
        ({"Q_LOCAL_AUTHORITY": "la_synthetic"}, r.MODULE_LOCAL_AUTHORITY),
        ({"Q_COMPANY_AUTH": "YES"}, r.MODULE_COMPANY),
        ({"Q_PARTY_CONTEXT": ["COMPANY"]}, r.MODULE_COMPANY),
    ],
)
def test_each_trigger_activates_its_module_and_only_when_fired(
    answer: dict[str, Any], module: str
) -> None:
    baseline = derive_routing({}).activated_conditional_module_ids
    assert module not in baseline
    assert module in derive_routing(answers(**answer)).activated_conditional_module_ids


def test_every_activatable_module_is_declared_by_some_question() -> None:
    declared = {
        module_id for question in ALL_QUESTIONS for module_id in question.activates_module_ids
    }
    routed = {value for name, value in vars(r).items() if name.startswith("MODULE_")}
    assert routed <= declared


def test_dispute_answer_maps_to_the_conservative_stage_and_evidence_overrides_it() -> None:
    assert derive_routing(answers(Q_DISPUTE="YES")).dispute_stage is DisputeStage.CLAIMS_FILED
    assert derive_routing(answers(Q_DISPUTE="NO")).dispute_stage is DisputeStage.NO_INDICIA_FOUND
    reported = derive_routing(
        answers(Q_DISPUTE="NO"), reported_dispute_stage=DisputeStage.S21_DC_REFERRED
    )
    assert reported.dispute_stage is DisputeStage.S21_DC_REFERRED


def test_triggered_questions_are_deduplicated_ordered_and_exclude_answered_ones() -> None:
    derived = derive_routing(
        answers(
            Q_PARTY_CONTEXT=["COMPANY", "ATTORNEY_POWER_OF_ATTORNEY"],
            Q_PARCEL_KIND="CONDOMINIUM_UNIT",
            Q_DISPUTE="UNKNOWN",
            Q_COMPANY_AUTH="YES",
        )
    )
    assert derived.triggered_question_ids == (r.Q_POA, r.Q_BUILDING, r.Q_ENCUMBRANCE)


def test_a_clean_dispute_answer_does_not_open_the_encumbrance_question() -> None:
    assert r.Q_ENCUMBRANCE not in derive_routing(answers(Q_DISPUTE="NO")).triggered_question_ids
    assert r.Q_ENCUMBRANCE in derive_routing({}).triggered_question_ids


def test_intent_resolves_a_subtype_only_when_it_names_one() -> None:
    exact = derive_routing(answers(Q_INTENT=TRANSFER_SALE_SUBTYPE_ID))
    family_only = derive_routing(answers(Q_INTENT="ownership_change"))

    assert exact.subtype_id == TRANSFER_SALE_SUBTYPE_ID
    assert exact.family_id is MatterFamily.OWNERSHIP_CHANGE
    # Selecting a family is not selecting an instrument.
    assert family_only.subtype_id is None
    assert family_only.family_id is None


# ── build_eligibility_input ─────────────────────────────────────────────────


def _input(facts: MatterFactSnapshot, **answer_values: Any) -> Any:
    live = answers(**answer_values)
    return build_eligibility_input(
        derive_routing(live),
        facts,
        regime_id="lk.rta",
        subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL,
        template_verified=False,
        source_reverification_required=True,
        answers=live,
    )


def test_answers_fill_in_only_where_no_fact_has_been_confirmed() -> None:
    built = _input(MatterFactSnapshot(), Q_LIFE_INTEREST="YES", Q_COOWNERS="NO")
    assert built.life_interest_present is TriState.YES
    assert built.coowners_present is TriState.NO


def test_a_confirmed_fact_is_never_overridden_by_an_answer() -> None:
    facts = MatterFactSnapshot(life_interest_present=TriState.YES, coowners_present=TriState.YES)
    built = _input(facts, Q_LIFE_INTEREST="NO", Q_COOWNERS="NO")
    assert built.life_interest_present is TriState.YES
    assert built.coowners_present is TriState.YES


def test_facts_and_flags_are_carried_through_unchanged() -> None:
    facts = MatterFactSnapshot(
        mortgage_status=EncumbranceStatus.APPARENTLY_UNCANCELLED,
        identifier_conflict_present=True,
        unconfirmed_critical_fact_type_ids=("rta.instrument.consideration",),
        identified_mortgage_reference=True,
    )
    built = _input(facts, Q_REGIME="YES")

    assert built.regime_id == "lk.rta"
    assert built.title_status is TitleStatus.RTA_REGISTERED
    assert built.mortgage_status is EncumbranceStatus.APPARENTLY_UNCANCELLED
    assert built.identifier_conflict_present is True
    assert built.unconfirmed_critical_fact_type_ids == ("rta.instrument.consideration",)
    assert built.identified_mortgage_reference is True
    assert built.template_verified is False
    assert built.source_reverification_required is True
    assert built.subtype_decision_status is SubtypeDecisionStatus.PROVISIONAL


def test_without_answers_unknown_stays_unknown() -> None:
    built = build_eligibility_input(
        derive_routing({}),
        MatterFactSnapshot(),
        regime_id="lk.rta",
        subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL,
        template_verified=False,
        source_reverification_required=True,
    )
    assert built.life_interest_present is TriState.UNKNOWN
    assert built.coowners_present is TriState.UNKNOWN


def test_the_default_fact_snapshot_is_the_honest_nothing_reviewed_state() -> None:
    snapshot = MatterFactSnapshot()
    assert snapshot.mortgage_status is EncumbranceStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.transferor_is_registered_owner is TriState.UNKNOWN
    assert snapshot.identifier_conflict_present is False

"""Intake routing: answers decide the modules, the modules decide the checklist (F8).

The most consequential decision in the product was untested. These pin the
rules routing.py states for itself, and check it against the question
catalogue, question by question and value by value.

Where routing and the catalogue disagree, the test records the gap as a
strict xfail rather than choosing a legal mapping: which answer should
activate which module is for the lawyers who own the rule pack.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.modules.content_governance.contracts import (
    AnswerValueKind,
    DispositionScope,
    DisputeStage,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
    TriState,
    get_question,
)
from src.modules.matter.domain import routing
from src.modules.matter.domain.routing import (
    LiveAnswer,
    MatterFactSnapshot,
    build_eligibility_input,
    derive_routing,
)

QUESTIONS = sorted(v for k, v in vars(routing).items() if k.startswith("Q_"))


def _answers(**by_question: Any) -> dict[str, LiveAnswer]:
    return {q: LiveAnswer(value, True) for q, value in by_question.items()}


def _route(**by_question: Any) -> routing.RoutingDerivation:
    return derive_routing(_answers(**by_question))


def _catalogue_values(question_id: str) -> list[Any]:
    """Every answer the question catalogue lets a user give to this question."""
    question = get_question(question_id)
    assert question is not None
    match question.value_kind:
        case AnswerValueKind.TRI_STATE:
            return [t.value for t in TriState]
        case AnswerValueKind.SINGLE_CHOICE:
            return [o.value for o in question.options]
        case AnswerValueKind.MULTI_CHOICE:
            return [[o.value] for o in question.options]
        case AnswerValueKind.TEXT:
            return ["synthetic text answer"]
        case _:
            return []


def _modules_toggled_by(question_id: str) -> set[str]:
    """Modules that answering this question alone switches on or off."""
    baseline = derive_routing({}).activated_conditional_module_ids
    toggled: set[str] = set()
    for value in _catalogue_values(question_id):
        activated = _route(**{question_id: value}).activated_conditional_module_ids
        toggled |= activated ^ baseline
    return toggled


# ── Routing against the question catalogue ─────────────────────────────────


@pytest.mark.parametrize("question_id", QUESTIONS)
def test_a_question_never_activates_a_module_it_does_not_declare(question_id: str) -> None:
    """The promise routing.py's docstring makes, checked for every answer."""
    question = get_question(question_id)
    assert question is not None

    assert _modules_toggled_by(question_id) <= set(question.activates_module_ids)


#: Modules a question declares that no catalogue answer to it can reach.
#: Routing reads Q08 and Q20 as YES/NO/UNKNOWN, but the catalogue offers them
#: as choices (e.g. DECEASED_TRANSMISSION_INCOMPLETE), and Q21 as free text,
#: so routing never sees a YES. Q09 is never read at all. Which answers should
#: activate these modules is a legal mapping for the rule-pack owners.
UNREACHABLE_DECLARATIONS = {
    "Q08_OWNER_DEAD": {"lk.rta.module.estate_or_deceased_owner"},
    "Q09_PROBATE_PATH": {
        "lk.rta.module.court_or_statutory_sale",
        "lk.rta.module.estate_or_deceased_owner",
    },
    "Q20_COOWNERS": {"lk.rta.module.coowners"},
    "Q21_COMPANY_AUTH": {"lk.rta.module.company_party"},
}


def _unreachable(question_id: str) -> set[str]:
    question = get_question(question_id)
    assert question is not None
    return set(question.activates_module_ids) - _modules_toggled_by(question_id)


@pytest.mark.parametrize("question_id", QUESTIONS)
def test_no_new_declared_module_is_unreachable(question_id: str) -> None:
    assert _unreachable(question_id) <= UNREACHABLE_DECLARATIONS.get(question_id, set())


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Q08, Q09, Q20 and Q21 declare modules no answer can reach; see UNREACHABLE_DECLARATIONS.",
)
@pytest.mark.parametrize("question_id", sorted(UNREACHABLE_DECLARATIONS))
def test_every_declared_module_is_reachable(question_id: str) -> None:
    assert _unreachable(question_id) == set()


# ── Q01: title status is the first gate ─────────────────────────────────────


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        (TriState.YES.value, TitleStatus.RTA_REGISTERED),
        (TriState.NO.value, TitleStatus.INITIAL_COMPILATION),
        (TriState.UNKNOWN.value, TitleStatus.UNKNOWN),
        ("maybe", TitleStatus.UNKNOWN),
    ],
)
def test_q01_decides_the_title_status(answer: str, status: TitleStatus) -> None:
    assert _route(Q01_REGIME=answer).title_status is status


def test_an_unanswered_q01_is_unknown_not_registered() -> None:
    assert derive_routing({}).title_status is TitleStatus.UNKNOWN


@pytest.mark.parametrize("answer", [TriState.NO.value, TriState.UNKNOWN.value, None])
def test_anything_short_of_rta_registered_needs_initial_compilation_triage(
    answer: str | None,
) -> None:
    answers = {} if answer is None else _answers(Q01_REGIME=answer)

    assert (
        routing.MODULE_INITIAL_COMPILATION
        in derive_routing(answers).activated_conditional_module_ids
    )


def test_a_registered_title_needs_no_initial_compilation_triage() -> None:
    derivation = _route(Q01_REGIME=TriState.YES.value)

    assert routing.MODULE_INITIAL_COMPILATION not in derivation.activated_conditional_module_ids


# ── UNKNOWN never becomes NO ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("question_id", "module"),
    [
        (routing.Q_MORTGAGE, routing.MODULE_MORTGAGE),
        (routing.Q_LEASE_OCCUPATION, routing.MODULE_LEASE),
    ],
)
@pytest.mark.parametrize(
    ("answer", "activated"),
    [
        (TriState.YES.value, True),
        (TriState.UNKNOWN.value, True),
        (None, True),
        (TriState.NO.value, False),
    ],
)
def test_silence_about_an_interest_keeps_its_checklist(
    question_id: str, module: str, answer: str | None, activated: bool
) -> None:
    """Treating an unanswered mortgage question as "no mortgage" is §6.4's failure."""
    answers = {} if answer is None else _answers(**{question_id: answer})

    assert (module in derive_routing(answers).activated_conditional_module_ids) is activated


# ── Parcel scope and kind ───────────────────────────────────────────────────


def test_part_of_a_parcel_activates_subdivision() -> None:
    """Appendix A, refusal 4: a part-parcel disposition routes to Section 47."""
    derivation = _route(Q03_SCOPE="PART_OF_PARCEL")

    assert derivation.disposition_scope is DispositionScope.PART_OF_PARCEL
    assert routing.MODULE_SUBDIVISION in derivation.activated_conditional_module_ids


def test_an_undivided_interest_activates_coowners() -> None:
    derivation = _route(Q03_SCOPE="UNDIVIDED_INTEREST")

    assert routing.MODULE_COOWNERS in derivation.activated_conditional_module_ids
    assert routing.MODULE_SUBDIVISION not in derivation.activated_conditional_module_ids


@pytest.mark.parametrize("kind", ["CONDOMINIUM_UNIT", "CONVERSION_TO_CONDOMINIUM"])
def test_a_condominium_activates_strata_and_asks_about_the_building(kind: str) -> None:
    derivation = _route(Q04_PARCEL_KIND=kind)

    assert derivation.parcel_kind is ParcelKind(kind)
    assert routing.MODULE_CONDOMINIUM in derivation.activated_conditional_module_ids
    assert routing.Q_BUILDING in derivation.triggered_question_ids


@pytest.mark.parametrize("question_id", [routing.Q_SCOPE, routing.Q_PARCEL_KIND])
def test_an_unrecognised_choice_is_unknown_not_a_default(question_id: str) -> None:
    derivation = _route(**{question_id: "SYNTHETIC_NOT_AN_OPTION"})

    assert derivation.disposition_scope is DispositionScope.UNKNOWN
    assert derivation.parcel_kind is ParcelKind.UNKNOWN


# ── Parties ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("context", "module"),
    [
        ("COMPANY", routing.MODULE_COMPANY),
        ("ESTATE_OR_DECEASED", routing.MODULE_ESTATE),
        ("ATTORNEY_POWER_OF_ATTORNEY", routing.MODULE_POA),
        ("PUBLIC_BODY", routing.MODULE_STATE_LAND),
    ],
)
def test_each_party_context_activates_its_module(context: str, module: str) -> None:
    derivation = _route(Q05_PARTY_CONTEXT=[context])

    assert PartyContext(context) in derivation.party_contexts
    assert module in derivation.activated_conditional_module_ids


def test_several_party_contexts_combine() -> None:
    derivation = _route(Q05_PARTY_CONTEXT=["COMPANY", "ATTORNEY_POWER_OF_ATTORNEY"])

    assert {
        routing.MODULE_COMPANY,
        routing.MODULE_POA,
    } <= derivation.activated_conditional_module_ids


def test_an_estate_asks_about_the_death_and_probate_until_answered() -> None:
    asked = _route(Q05_PARTY_CONTEXT=["ESTATE_OR_DECEASED"]).triggered_question_ids
    answered = derive_routing(
        _answers(
            Q05_PARTY_CONTEXT=["ESTATE_OR_DECEASED"],
            Q08_OWNER_DEAD="DECEASED_TRANSMISSION_INCOMPLETE",
        )
    ).triggered_question_ids

    assert (routing.Q_OWNER_DEAD, routing.Q_PROBATE_PATH) == asked[:2]
    assert routing.Q_OWNER_DEAD not in answered


def test_a_power_of_attorney_answered_yes_counts_as_the_party_context() -> None:
    derivation = _route(Q22_POA=TriState.YES.value)

    assert PartyContext.ATTORNEY_POWER_OF_ATTORNEY in derivation.party_contexts
    assert routing.MODULE_POA in derivation.activated_conditional_module_ids


# ── Disputes ────────────────────────────────────────────────────────────────


def test_a_reported_dispute_is_litigation_at_the_most_conservative_stage() -> None:
    derivation = _route(Q06_DISPUTE=TriState.YES.value)

    assert derivation.dispute_stage is DisputeStage.CLAIMS_FILED
    assert routing.MODULE_LITIGATION in derivation.activated_conditional_module_ids


def test_a_stage_from_evidence_outranks_the_intake_answer() -> None:
    derivation = derive_routing(
        _answers(Q06_DISPUTE=TriState.YES.value),
        reported_dispute_stage=DisputeStage.NO_INDICIA_FOUND,
    )

    assert derivation.dispute_stage is DisputeStage.NO_INDICIA_FOUND


@pytest.mark.parametrize("answer", [TriState.YES.value, TriState.UNKNOWN.value])
def test_a_possible_dispute_asks_about_encumbrances(answer: str) -> None:
    assert routing.Q_ENCUMBRANCE in _route(Q06_DISPUTE=answer).triggered_question_ids


def test_no_dispute_asks_nothing_more() -> None:
    assert routing.Q_ENCUMBRANCE not in _route(Q06_DISPUTE=TriState.NO.value).triggered_question_ids


# ── Subtype and determinism ─────────────────────────────────────────────────


def test_an_unknown_intent_names_no_subtype() -> None:
    """Routing never defaults the exact subtype (§12.4)."""
    derivation = _route(Q02_INTENT="synthetic_not_a_subtype")

    assert (derivation.subtype_id, derivation.family_id) == (None, None)


def test_routing_is_deterministic() -> None:
    answers = _answers(
        Q01_REGIME=TriState.YES.value,
        Q03_SCOPE="PART_OF_PARCEL",
        Q05_PARTY_CONTEXT=["COMPANY", "ESTATE_OR_DECEASED"],
        Q06_DISPUTE=TriState.UNKNOWN.value,
    )

    assert derive_routing(answers) == derive_routing(dict(reversed(list(answers.items()))))


# ── Eligibility input ───────────────────────────────────────────────────────


def _eligibility(facts: MatterFactSnapshot, **answers: Any) -> Any:
    return build_eligibility_input(
        derive_routing(_answers(**answers)),
        facts,
        regime_id="lk.rta",
        subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL,
        template_verified=False,
        source_reverification_required=False,
        answers=_answers(**answers),
    )


def test_an_answer_fills_a_fact_nobody_has_reviewed() -> None:
    result = _eligibility(MatterFactSnapshot(), Q12_LIFE_INTEREST=TriState.YES.value)

    assert result.life_interest_present is TriState.YES


def test_no_answer_leaves_an_unreviewed_fact_unknown() -> None:
    assert _eligibility(MatterFactSnapshot()).life_interest_present is TriState.UNKNOWN


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "build_eligibility_input says the more conservative value wins when an answer "
        "and a fact disagree, but a confirmed NO life interest overrides an answered YES. "
        "Which side should win is a legal decision."
    ),
)
def test_a_conflicting_answer_is_not_overruled_by_a_less_cautious_fact() -> None:
    result = _eligibility(
        MatterFactSnapshot(life_interest_present=TriState.NO),
        Q12_LIFE_INTEREST=TriState.YES.value,
    )

    assert result.life_interest_present is TriState.YES

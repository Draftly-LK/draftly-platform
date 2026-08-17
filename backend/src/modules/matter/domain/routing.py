"""Turning intake answers into a routing decision.

The question catalogue declares *which* conditional modules a question can
activate; this module decides *when*, because that mapping is legal logic
rather than metadata. A test asserts the two agree, so a question can never
activate a module it never declared.

Three rules govern every derivation here:

- An unanswered question is ``UNKNOWN``, and ``UNKNOWN`` never becomes ``NO``
  (§4.1). It leaves the predicate unmet and produces an evidence task.
- Only a live, lawyer-confirmed or provisional answer counts; a superseded one
  is history (§10.5).
- Inference may propose, never conclude. An answer whose status is
  ``INFERRED`` still routes the matter — it simply cannot satisfy a gate that
  requires lawyer confirmation, which the eligibility predicate enforces
  separately.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.modules.content_governance.contracts import (
    DispositionScope,
    DisputeStage,
    EligibilityInput,
    EncumbranceStatus,
    MatterFamily,
    NoticeStatus,
    OccupationStatus,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
    TriState,
    get_question,
    get_subtype,
)

Q_REGIME = "Q01_REGIME"
Q_INTENT = "Q02_INTENT"
Q_SCOPE = "Q03_SCOPE"
Q_PARCEL_KIND = "Q04_PARCEL_KIND"
Q_PARTY_CONTEXT = "Q05_PARTY_CONTEXT"
Q_DISPUTE = "Q06_DISPUTE"
Q_UPLOAD = "Q07_UPLOAD"
Q_OWNER_DEAD = "Q08_OWNER_DEAD"
Q_PROBATE_PATH = "Q09_PROBATE_PATH"
Q_MORTGAGE = "Q10_MORTGAGE"
Q_LEASE_OCCUPATION = "Q11_LEASE_OCCUPATION"
Q_LIFE_INTEREST = "Q12_LIFE_INTEREST"
Q_SERVITUDE = "Q13_SERVITUDE"
Q_ENCUMBRANCE = "Q14_ENCUMBRANCE"
Q_BUILDING = "Q15_BUILDING"
Q_LOCAL_AUTHORITY = "Q17_LOCAL_AUTHORITY"
Q_COOWNERS = "Q20_COOWNERS"
Q_COMPANY_AUTH = "Q21_COMPANY_AUTH"
Q_POA = "Q22_POA"

MODULE_COMPANY = "lk.rta.module.company_party"
MODULE_ESTATE = "lk.rta.module.estate_or_deceased_owner"
MODULE_POA = "lk.rta.module.power_of_attorney"
MODULE_COOWNERS = "lk.rta.module.coowners"
MODULE_MORTGAGE = "lk.rta.module.mortgage_present"
MODULE_LEASE = "lk.rta.module.lease_or_occupation"
MODULE_LIFE_INTEREST = "lk.rta.module.life_interest"
MODULE_SERVITUDE = "lk.rta.module.servitude"
MODULE_BUILDING = "lk.rta.module.building_present"
MODULE_LOCAL_AUTHORITY = "lk.rta.module.local_authority_clearance"
MODULE_LITIGATION = "lk.rta.module.active_notice_or_litigation"
MODULE_CONDOMINIUM = "lk.rta.module.condominium_strata"
MODULE_SUBDIVISION = "lk.rta.module.subdivision_amalgamation"
MODULE_INITIAL_COMPILATION = "lk.rta.module.initial_compilation_triage"
MODULE_STATE_LAND = "lk.rta.module.state_land"


@dataclass(frozen=True)
class LiveAnswer:
    """The minimum routing needs: the value and how it was reached."""

    value: Any
    lawyer_confirmed: bool


AnswerMap = Mapping[str, LiveAnswer]


@dataclass(frozen=True)
class RoutingDerivation:
    """What the answers imply, before any eligibility judgement is made."""

    title_status: TitleStatus
    parcel_kind: ParcelKind
    disposition_scope: DispositionScope
    party_contexts: frozenset[PartyContext]
    dispute_stage: DisputeStage
    activated_conditional_module_ids: frozenset[str]
    subtype_id: str | None
    family_id: MatterFamily | None
    #: Questions that must be asked next because a trigger fired (§4.1 step 3).
    triggered_question_ids: tuple[str, ...]


def _tri(answers: AnswerMap, question_id: str) -> TriState:
    answer = answers.get(question_id)
    if answer is None:
        return TriState.UNKNOWN
    try:
        return TriState(str(answer.value))
    except ValueError:
        return TriState.UNKNOWN


def _choice(answers: AnswerMap, question_id: str) -> str | None:
    answer = answers.get(question_id)
    if answer is None or answer.value is None:
        return None
    return str(answer.value)


def _choices(answers: AnswerMap, question_id: str) -> tuple[str, ...]:
    answer = answers.get(question_id)
    if answer is None or answer.value is None:
        return ()
    value = answer.value
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return ()


def _title_status(answers: AnswerMap) -> TitleStatus:
    """Q01 is the first gate: an address alone does not prove RTA coverage."""
    match _tri(answers, Q_REGIME):
        case TriState.YES:
            return TitleStatus.RTA_REGISTERED
        case TriState.NO:
            return TitleStatus.INITIAL_COMPILATION
        case _:
            return TitleStatus.UNKNOWN


def _parcel_kind(answers: AnswerMap) -> ParcelKind:
    raw = _choice(answers, Q_PARCEL_KIND)
    if raw is None:
        return ParcelKind.UNKNOWN
    try:
        return ParcelKind(raw)
    except ValueError:
        return ParcelKind.UNKNOWN


def _disposition_scope(answers: AnswerMap) -> DispositionScope:
    raw = _choice(answers, Q_SCOPE)
    if raw is None:
        return DispositionScope.UNKNOWN
    try:
        return DispositionScope(raw)
    except ValueError:
        return DispositionScope.UNKNOWN


def _party_contexts(answers: AnswerMap) -> frozenset[PartyContext]:
    contexts: set[PartyContext] = set()
    for raw in _choices(answers, Q_PARTY_CONTEXT):
        try:
            contexts.add(PartyContext(raw))
        except ValueError:
            continue
    # A deceased registered owner reported through Q08 is the same fact as
    # ticking "estate" in Q05; routing must not depend on which one was used.
    if _tri(answers, Q_OWNER_DEAD) is TriState.YES:
        contexts.add(PartyContext.ESTATE_OR_DECEASED)
    if _tri(answers, Q_POA) is TriState.YES:
        contexts.add(PartyContext.ATTORNEY_POWER_OF_ATTORNEY)
    return frozenset(contexts)


def _dispute_stage(answers: AnswerMap, reported: DisputeStage | None) -> DisputeStage:
    """A reported stage from evidence wins; Q06 only says "something exists".

    Q06 answering YES cannot by itself say *which* stage the matter is at, and
    guessing one would be a legal conclusion. It maps to the most conservative
    non-litigation blocking stage until evidence says otherwise.
    """
    if reported is not None:
        return reported
    if _tri(answers, Q_DISPUTE) is TriState.YES:
        return DisputeStage.CLAIMS_FILED
    return DisputeStage.NO_INDICIA_FOUND


def _activated_modules(
    answers: AnswerMap,
    party_contexts: frozenset[PartyContext],
    parcel_kind: ParcelKind,
    disposition_scope: DispositionScope,
    title_status: TitleStatus,
) -> frozenset[str]:
    modules: set[str] = set()

    if PartyContext.COMPANY in party_contexts:
        modules.add(MODULE_COMPANY)
    if PartyContext.ESTATE_OR_DECEASED in party_contexts:
        modules.add(MODULE_ESTATE)
    if PartyContext.ATTORNEY_POWER_OF_ATTORNEY in party_contexts:
        modules.add(MODULE_POA)
    if PartyContext.PUBLIC_BODY in party_contexts:
        modules.add(MODULE_STATE_LAND)

    if parcel_kind in {ParcelKind.CONDOMINIUM_UNIT, ParcelKind.CONVERSION_TO_CONDOMINIUM}:
        modules.add(MODULE_CONDOMINIUM)
    if disposition_scope is DispositionScope.PART_OF_PARCEL:
        modules.add(MODULE_SUBDIVISION)
    if disposition_scope is DispositionScope.UNDIVIDED_INTEREST:
        modules.add(MODULE_COOWNERS)
    if title_status is not TitleStatus.RTA_REGISTERED:
        modules.add(MODULE_INITIAL_COMPILATION)

    if _tri(answers, Q_DISPUTE) is TriState.YES:
        modules.add(MODULE_LITIGATION)
    if _tri(answers, Q_ENCUMBRANCE) is TriState.YES:
        modules.add(MODULE_LITIGATION)
    if _tri(answers, Q_MORTGAGE) in {TriState.YES, TriState.UNKNOWN}:
        # UNKNOWN activates too: an unresolved mortgage question is exactly the
        # case that needs the release checklist, and treating silence as "no
        # mortgage" is the failure §6.4 names.
        modules.add(MODULE_MORTGAGE)
    if _tri(answers, Q_LEASE_OCCUPATION) in {TriState.YES, TriState.UNKNOWN}:
        modules.add(MODULE_LEASE)
    if _tri(answers, Q_LIFE_INTEREST) is TriState.YES:
        modules.add(MODULE_LIFE_INTEREST)
    if _tri(answers, Q_SERVITUDE) is TriState.YES:
        modules.add(MODULE_SERVITUDE)
    if _tri(answers, Q_BUILDING) is TriState.YES:
        modules.add(MODULE_BUILDING)
    if _tri(answers, Q_COOWNERS) is TriState.YES:
        modules.add(MODULE_COOWNERS)
    if _choice(answers, Q_LOCAL_AUTHORITY):
        modules.add(MODULE_LOCAL_AUTHORITY)
    if _tri(answers, Q_COMPANY_AUTH) is TriState.YES:
        modules.add(MODULE_COMPANY)

    return frozenset(modules)


def _triggered_questions(
    answers: AnswerMap,
    party_contexts: frozenset[PartyContext],
    parcel_kind: ParcelKind,
) -> tuple[str, ...]:
    """Which resolution questions the answers so far have opened (§4.1)."""
    triggered: list[str] = []
    if PartyContext.ESTATE_OR_DECEASED in party_contexts:
        triggered.extend([Q_OWNER_DEAD, Q_PROBATE_PATH])
    if PartyContext.COMPANY in party_contexts:
        triggered.append(Q_COMPANY_AUTH)
    if PartyContext.ATTORNEY_POWER_OF_ATTORNEY in party_contexts:
        triggered.append(Q_POA)
    if parcel_kind in {ParcelKind.CONDOMINIUM_UNIT, ParcelKind.CONVERSION_TO_CONDOMINIUM}:
        triggered.append(Q_BUILDING)
    if _tri(answers, Q_DISPUTE) in {TriState.YES, TriState.UNKNOWN}:
        triggered.append(Q_ENCUMBRANCE)
    ordered = [q for q in dict.fromkeys(triggered) if get_question(q) is not None]
    return tuple(q for q in ordered if q not in answers)


def derive_routing(
    answers: AnswerMap,
    *,
    reported_dispute_stage: DisputeStage | None = None,
) -> RoutingDerivation:
    """Read the answers. Make no judgement about eligibility here."""
    title_status = _title_status(answers)
    parcel_kind = _parcel_kind(answers)
    disposition_scope = _disposition_scope(answers)
    party_contexts = _party_contexts(answers)
    dispute_stage = _dispute_stage(answers, reported_dispute_stage)

    subtype_id = _choice(answers, Q_INTENT)
    subtype = get_subtype(subtype_id) if subtype_id else None

    return RoutingDerivation(
        title_status=title_status,
        parcel_kind=parcel_kind,
        disposition_scope=disposition_scope,
        party_contexts=party_contexts,
        dispute_stage=dispute_stage,
        activated_conditional_module_ids=_activated_modules(
            answers, party_contexts, parcel_kind, disposition_scope, title_status
        ),
        subtype_id=subtype.id if subtype else None,
        family_id=subtype.family_id if subtype else None,
        triggered_question_ids=_triggered_questions(answers, party_contexts, parcel_kind),
    )


@dataclass(frozen=True)
class MatterFactSnapshot:
    """Lawyer-confirmed facts the eligibility predicate needs, from `verification`.

    Defaults are the honest "nothing reviewed yet" values, not favourable ones.
    """

    transferor_is_registered_owner: TriState = TriState.UNKNOWN
    title_certificate_available: TriState = TriState.UNKNOWN
    transmission_completed: TriState = TriState.NOT_APPLICABLE
    life_interest_present: TriState = TriState.UNKNOWN
    special_condition_present: TriState = TriState.UNKNOWN
    coowners_present: TriState = TriState.UNKNOWN
    creates_coownership: TriState = TriState.UNKNOWN
    mortgage_status: EncumbranceStatus = EncumbranceStatus.NO_EVIDENCE_REVIEWED
    lease_status: EncumbranceStatus = EncumbranceStatus.NO_EVIDENCE_REVIEWED
    occupation_status: OccupationStatus = OccupationStatus.NO_EVIDENCE_REVIEWED
    notice_status: NoticeStatus = NoticeStatus.NO_EVIDENCE_REVIEWED
    active_court_proceeding: TriState = TriState.UNKNOWN
    identifier_conflict_present: bool = False
    unconfirmed_critical_fact_type_ids: tuple[str, ...] = ()
    identified_mortgage_reference: bool = False
    mortgagee_authority_confirmed: TriState = TriState.UNKNOWN
    discharge_evidence_sufficient: TriState = TriState.UNKNOWN
    cancellation_route_confirmed: TriState = TriState.UNKNOWN


def build_eligibility_input(
    derivation: RoutingDerivation,
    facts: MatterFactSnapshot,
    *,
    regime_id: str,
    subtype_decision_status: SubtypeDecisionStatus,
    template_verified: bool,
    source_reverification_required: bool,
    answers: AnswerMap | None = None,
) -> EligibilityInput:
    """Assemble the predicate input from routing plus confirmed facts.

    Answers can only *raise* a concern here, never lower one. Where an answer
    and a fact disagree — the lawyer said "no mortgage", the register shows one
    — the more conservative value wins and the conflict surfaces as a check.
    """
    answers = answers or {}
    life_interest = facts.life_interest_present
    if life_interest is TriState.UNKNOWN:
        life_interest = _tri(answers, Q_LIFE_INTEREST)
    coowners = facts.coowners_present
    if coowners is TriState.UNKNOWN:
        coowners = _tri(answers, Q_COOWNERS)

    return EligibilityInput(
        regime_id=regime_id,
        subtype_id=derivation.subtype_id,
        subtype_decision_status=subtype_decision_status,
        title_status=derivation.title_status,
        title_certificate_available=facts.title_certificate_available,
        parcel_kind=derivation.parcel_kind,
        disposition_scope=derivation.disposition_scope,
        party_contexts=derivation.party_contexts,
        transferor_is_registered_owner=facts.transferor_is_registered_owner,
        transmission_completed=facts.transmission_completed,
        life_interest_present=life_interest,
        special_condition_present=facts.special_condition_present,
        coowners_present=coowners,
        creates_coownership=facts.creates_coownership,
        dispute_stage=derivation.dispute_stage,
        active_court_proceeding=facts.active_court_proceeding,
        notice_status=facts.notice_status,
        mortgage_status=facts.mortgage_status,
        lease_status=facts.lease_status,
        occupation_status=facts.occupation_status,
        identifier_conflict_present=facts.identifier_conflict_present,
        unconfirmed_critical_fact_type_ids=facts.unconfirmed_critical_fact_type_ids,
        template_verified=template_verified,
        source_reverification_required=source_reverification_required,
        identified_mortgage_reference=facts.identified_mortgage_reference,
        mortgagee_authority_confirmed=facts.mortgagee_authority_confirmed,
        discharge_evidence_sufficient=facts.discharge_evidence_sufficient,
        cancellation_route_confirmed=facts.cancellation_route_confirmed,
    )

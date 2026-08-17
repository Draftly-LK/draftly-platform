"""RTA intake questions — the routing interview and the resolution interview.

Two rules govern this catalogue. ``UNKNOWN`` is a real answer and is never
coerced into ``NO``: a question that no uploaded document answers yields
``UNKNOWN`` plus a missing-evidence task (§4.1, §4.4). And a question whose
answer controls the regime, the exact instrument, V0 eligibility, a statutory
prohibition, or a dispute hold is asked immediately instead of being deferred
to extraction — that is ``controls_v0_eligibility`` (§4.4).

Prompts, options, and trigger notes are translation keys. The lawyer-facing
wording of §4.2 and §4.3 is owned by the team and lives in the message
catalogue, never in this file.

Implements §4.1–§4.4 and the V0 question set of §14.3. The pre-draft
confirmation of §4.1 step 4 owns no numbered question: it re-presents answers
and facts recorded here and is gated by the preflight in §9.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.modules.content_governance.domain.enums import (
    AnswerStatus,
    AnswerValueKind,
    DispositionScope,
    ParcelKind,
    PartyContext,
    QuestionStage,
)
from src.modules.content_governance.domain.rta.fact_values import ProbatePath
from src.modules.content_governance.domain.rta.taxonomy import FAMILIES
from src.modules.content_governance.domain.sources import (
    SRC_GAZETTE_2022,
    SRC_LAWYER_PRACTICE,
    SRC_LOCAL_AUTHORITY,
    SRC_PRODUCT_SAFETY,
    SRC_RGD_CHARGES,
    SRC_RGD_TRANSACTIONS,
    SRC_RTA_ACT,
    SRC_UDA_APPROVALS,
    SourceCitation,
)

#: Bumped whenever a question is added, retired, or changes its answer shape.
#: Pinned into every checklist snapshot so an intake is never re-interpreted
#: under a later question set.
QUESTIONS_VERSION = "1.0.0"


@dataclass(frozen=True)
class QuestionOption:
    """One selectable value. ``value`` is the stored answer, never the label."""

    value: str
    label_key: str


@dataclass(frozen=True)
class QuestionDefinition:
    """One intake question (§4.2, §4.3).

    ``inferable`` says only that a model may *propose* a value. It never
    weakens ``lawyer_confirmation_required``, and the two are independent:
    every legal characterisation stays lawyer-owned however confidently it was
    extracted (§6.4).
    """

    id: str
    stage: QuestionStage
    order: int
    prompt_key: str
    why_key: str
    value_kind: AnswerValueKind
    sources: tuple[SourceCitation, ...]
    options: tuple[QuestionOption, ...] = ()
    activates_module_ids: tuple[str, ...] = ()
    trigger_note_key: str | None = None
    inferable: bool = False
    lawyer_confirmation_required: bool = True
    #: §4.4 — asked immediately, never suppressed in favour of extraction.
    controls_v0_eligibility: bool = False
    #: §14.3 — part of the implement-now set for the two V0 pilot paths.
    v0_required: bool = False
    allows_unknown: bool = True


def _act(section: str) -> SourceCitation:
    return SourceCitation(SRC_RTA_ACT.id, locator=f"s. {section}")


def _opt(question_id: str, value: str) -> QuestionOption:
    return QuestionOption(value, f"rta.question.{question_id}.option.{value}")


def _enum_options(question_id: str, members: tuple[Enum, ...]) -> tuple[QuestionOption, ...]:
    """Options taken from the closed vocabulary rather than restated here.

    Members are listed explicitly at each call site so the display order is a
    UI decision and the enum stays the only definition of the values.
    """
    return tuple(_opt(question_id, str(m.value)) for m in members)


def _q(
    question_id: str,
    stage: QuestionStage,
    order: int,
    value_kind: AnswerValueKind,
    sources: tuple[SourceCitation, ...],
    *,
    options: tuple[QuestionOption, ...] = (),
    activates: tuple[str, ...] = (),
    inferable: bool = False,
    lawyer_confirmation_required: bool = True,
    controls_v0_eligibility: bool = False,
    v0_required: bool = False,
    allows_unknown: bool = True,
) -> QuestionDefinition:
    return QuestionDefinition(
        id=question_id,
        stage=stage,
        order=order,
        prompt_key=f"rta.question.{question_id}.prompt",
        why_key=f"rta.question.{question_id}.why",
        value_kind=value_kind,
        sources=sources,
        options=options,
        activates_module_ids=activates,
        # Routing questions are always asked; everything later appears only on
        # a trigger, so only those carry a trigger explanation (§4.3).
        trigger_note_key=(
            None if stage is QuestionStage.ROUTING else f"rta.question.{question_id}.trigger"
        ),
        inferable=inferable,
        lawyer_confirmation_required=lawyer_confirmation_required,
        controls_v0_eligibility=controls_v0_eligibility,
        v0_required=v0_required,
        allows_unknown=allows_unknown,
    )


# ── Option sets ──────────────────────────────────────────────────────────────

# Q02 selects a family first; the exact prescribed instrument is a second
# selection over `subtypes_in_family` and requires lawyer confirmation before
# the subtype leaves SubtypeDecisionStatus.PROVISIONAL (§3.2, §3.3).
_INTENT_OPTIONS: tuple[QuestionOption, ...] = tuple(
    QuestionOption(family.id.value, family.label_key) for family in FAMILIES
)

_SCOPE_OPTIONS = _enum_options(
    "Q03_SCOPE",
    (
        DispositionScope.WHOLE_REGISTERED_PARCEL,
        DispositionScope.PART_OF_PARCEL,
        DispositionScope.UNDIVIDED_INTEREST,
        DispositionScope.UNKNOWN,
    ),
)

_PARCEL_KIND_OPTIONS = _enum_options(
    "Q04_PARCEL_KIND",
    (
        ParcelKind.ORDINARY,
        ParcelKind.CONDOMINIUM_UNIT,
        ParcelKind.CONVERSION_TO_CONDOMINIUM,
        ParcelKind.UNKNOWN,
    ),
)

# NATURAL_PERSONS_ONLY excludes every other member and is the only selection
# that keeps the matter on the V0 path. "UNKNOWN" is not a PartyContext member
# because it is not a party kind: it records that the screening has not been
# done, and it must never collapse into NATURAL_PERSONS_ONLY (§4.1, §4.4).
_PARTY_CONTEXT_OPTIONS: tuple[QuestionOption, ...] = (
    *_enum_options(
        "Q05_PARTY_CONTEXT",
        (
            PartyContext.NATURAL_PERSONS_ONLY,
            PartyContext.COMPANY,
            PartyContext.ESTATE_OR_DECEASED,
            PartyContext.ATTORNEY_POWER_OF_ATTORNEY,
            PartyContext.PUBLIC_BODY,
            PartyContext.OTHER_NON_INDIVIDUAL,
        ),
    ),
    _opt("Q05_PARTY_CONTEXT", "UNKNOWN"),
)


# ── Routing interview (§4.2) ─────────────────────────────────────────────────

ROUTING_QUESTIONS: tuple[QuestionDefinition, ...] = (
    _q(
        "Q01_REGIME",
        QuestionStage.ROUTING,
        1,
        AnswerValueKind.TRI_STATE,
        (_act("1"), _act("10-27"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        # NO or UNKNOWN does not mean "not RTA land". It means the parcel may
        # still be in initial compilation, which is a different statutory
        # process from a subsequent instrument (§1.2). An address never proves
        # RTA coverage (s. 1).
        activates=("lk.rta.module.initial_compilation_triage",),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q02_INTENT",
        QuestionStage.ROUTING,
        2,
        AnswerValueKind.SINGLE_CHOICE,
        (
            SourceCitation(SRC_GAZETTE_2022.id, locator="regulation 15(1) amendment"),
            _act("39"),
        ),
        options=_INTENT_OPTIONS,
        # The instrument-specific checklist modules come from the chosen
        # subtype's `default_module_definition_ids`, not from this answer.
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q03_SCOPE",
        QuestionStage.ROUTING,
        3,
        AnswerValueKind.SINGLE_CHOICE,
        (_act("47"), _act("48")),
        options=_SCOPE_OPTIONS,
        activates=("lk.rta.module.subdivision_amalgamation", "lk.rta.module.coowners"),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q04_PARCEL_KIND",
        QuestionStage.ROUTING,
        4,
        AnswerValueKind.SINGLE_CHOICE,
        (_act("50-52"),),
        options=_PARCEL_KIND_OPTIONS,
        activates=("lk.rta.module.condominium_strata",),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q05_PARTY_CONTEXT",
        QuestionStage.ROUTING,
        5,
        AnswerValueKind.MULTI_CHOICE,
        (_act("43"), _act("44"), SourceCitation(SRC_LAWYER_PRACTICE.id)),
        options=_PARTY_CONTEXT_OPTIONS,
        activates=(
            "lk.rta.module.company_party",
            "lk.rta.module.estate_or_deceased_owner",
            "lk.rta.module.power_of_attorney",
            "lk.rta.module.state_land",
        ),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q06_DISPUTE",
        QuestionStage.ROUTING,
        6,
        AnswerValueKind.TRI_STATE,
        (
            _act("21-25"),
            _act("29-30"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="dispute hold"),
        ),
        # A YES here may move the matter to LITIGATION_HOLD, which is an
        # automation scope, not a checklist module (§2.3, §8.4).
        activates=("lk.rta.module.active_notice_or_litigation",),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q07_UPLOAD",
        QuestionStage.ROUTING,
        7,
        AnswerValueKind.FILE_UPLOAD,
        (SourceCitation(SRC_PRODUCT_SAFETY.id, locator="immutable evidence"),),
        # Not a legal answer: uploading files asserts nothing about the matter,
        # so there is nothing for a lawyer to confirm and no UNKNOWN state.
        lawyer_confirmation_required=False,
        v0_required=True,
        allows_unknown=False,
    ),
)


# ── Resolution interview (§4.3) ──────────────────────────────────────────────

RESOLUTION_QUESTIONS: tuple[QuestionDefinition, ...] = (
    _q(
        "Q08_OWNER_DEAD",
        QuestionStage.RESOLUTION,
        8,
        AnswerValueKind.SINGLE_CHOICE,
        (_act("54"), _act("55")),
        # Death and completed transmission are one gate: an uncompleted
        # transmission is what blocks V0, and probate papers alone never
        # establish that registration followed. Only the death half may be
        # proposed from evidence.
        options=(
            _opt("Q08_OWNER_DEAD", "NO_OWNER_DECEASED"),
            _opt("Q08_OWNER_DEAD", "DECEASED_TRANSMISSION_REGISTERED"),
            _opt("Q08_OWNER_DEAD", "DECEASED_TRANSMISSION_INCOMPLETE"),
            _opt("Q08_OWNER_DEAD", "UNKNOWN"),
        ),
        activates=("lk.rta.module.estate_or_deceased_owner",),
        inferable=True,
        controls_v0_eligibility=True,
    ),
    _q(
        "Q09_PROBATE_PATH",
        QuestionStage.RESOLUTION,
        9,
        AnswerValueKind.SINGLE_CHOICE,
        (_act("54"), _act("55"), _act("56")),
        # The route vocabulary is `ProbatePath`; restating it as literals here
        # would let the two drift apart silently.
        options=_enum_options(
            "Q09_PROBATE_PATH",
            (
                ProbatePath.TESTATE,
                ProbatePath.INTESTATE,
                ProbatePath.COURT_ORDER_OR_CERTIFICATE,
                ProbatePath.UNKNOWN,
            ),
        ),
        activates=(
            "lk.rta.module.estate_or_deceased_owner",
            "lk.rta.module.court_or_statutory_sale",
        ),
        inferable=True,
    ),
    _q(
        "Q10_MORTGAGE",
        QuestionStage.RESOLUTION,
        10,
        AnswerValueKind.TRI_STATE,
        (_act("44"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        # NO is answerable only against a current register/encumbrance search;
        # the absence of a mortgage instrument in the upload is UNKNOWN (§7.2).
        activates=("lk.rta.module.mortgage_present",),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q11_LEASE_OCCUPATION",
        QuestionStage.RESOLUTION,
        11,
        AnswerValueKind.TRI_STATE,
        (SourceCitation(SRC_LAWYER_PRACTICE.id), _act("45(2)")),
        # Silence in the uploaded papers is not proof of vacant possession, so
        # extraction can support YES but never NO.
        activates=("lk.rta.module.lease_or_occupation",),
        inferable=True,
        v0_required=True,
    ),
    _q(
        "Q12_LIFE_INTEREST",
        QuestionStage.RESOLUTION,
        12,
        AnswerValueKind.TRI_STATE,
        (_act("46"),),
        activates=("lk.rta.module.life_interest",),
        inferable=True,
        controls_v0_eligibility=True,
    ),
    _q(
        "Q13_SERVITUDE",
        QuestionStage.RESOLUTION,
        13,
        AnswerValueKind.TRI_STATE,
        (_act("75"),),
        activates=("lk.rta.module.servitude",),
        inferable=True,
    ),
    _q(
        "Q14_ENCUMBRANCE",
        QuestionStage.RESOLUTION,
        14,
        AnswerValueKind.TRI_STATE,
        (_act("45(2)"), _act("21-25"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        # Same asymmetry as Q10: absence of a caveat in the file is not absence
        # of a caveat on the register.
        activates=("lk.rta.module.active_notice_or_litigation",),
        inferable=True,
        v0_required=True,
    ),
    _q(
        "Q15_BUILDING",
        QuestionStage.RESOLUTION,
        15,
        AnswerValueKind.TRI_STATE,
        (SourceCitation(SRC_LAWYER_PRACTICE.id),),
        activates=("lk.rta.module.building_present",),
        inferable=True,
    ),
    _q(
        "Q16_APPROVALS",
        QuestionStage.RESOLUTION,
        16,
        AnswerValueKind.SINGLE_CHOICE,
        (SourceCitation(SRC_UDA_APPROVALS.id), SourceCitation(SRC_LOCAL_AUTHORITY.id)),
        # Only AVAILABLE may be proposed, and only from a detected plan or
        # certificate. Whether approvals are legally required for this matter
        # in this jurisdiction is a lawyer conclusion.
        options=(
            _opt("Q16_APPROVALS", "AVAILABLE"),
            _opt("Q16_APPROVALS", "REQUIRED_NOT_AVAILABLE"),
            _opt("Q16_APPROVALS", "NOT_REQUIRED"),
            _opt("Q16_APPROVALS", "UNKNOWN"),
        ),
        activates=("lk.rta.module.building_present",),
        inferable=True,
    ),
    _q(
        "Q17_LOCAL_AUTHORITY",
        QuestionStage.RESOLUTION,
        17,
        AnswerValueKind.TEXT,
        (SourceCitation(SRC_LOCAL_AUTHORITY.id),),
        # The answer names the authority. Which certificates that office
        # requires is jurisdiction-specific and enters the checklist as
        # LOCAL_AUTHORITY/OFFICE_ADDED items, never as a global rule (§13.2.8).
        activates=("lk.rta.module.local_authority_clearance",),
        inferable=True,
    ),
    _q(
        "Q18_ORIGINALS",
        QuestionStage.RESOLUTION,
        18,
        AnswerValueKind.MULTI_CHOICE,
        (
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="human-only original inspection"),
            SourceCitation(SRC_LAWYER_PRACTICE.id),
        ),
        # Human attestation, per item, with a named reviewer and a timestamp.
        # No scan, OCR result, or model confidence may set
        # PhysicalOriginalStatus.ORIGINAL_INSPECTED, so this is never inferable
        # (§Executive 5, §5.4). The option set is the matter's own checklist
        # items that require an original, so it cannot be enumerated here.
        # An item left unselected stays UNKNOWN or COPY_ONLY: "unknown" is the
        # absence of an attestation, not a value the lawyer can assert.
        inferable=False,
        v0_required=True,
        allows_unknown=False,
    ),
    _q(
        "Q19_MISSING_ORIGINAL",
        QuestionStage.RESOLUTION,
        19,
        AnswerValueKind.TEXT,
        (SourceCitation(SRC_LAWYER_PRACTICE.id), SourceCitation(SRC_PRODUCT_SAFETY.id)),
        # Ingestion can detect that an expected original is absent; the reason
        # and the approved substitute or curative action are a lawyer
        # disposition, and that is what this answer records.
        activates=("lk.rta.module.missing_original",),
        inferable=False,
        v0_required=True,
    ),
    _q(
        "Q20_COOWNERS",
        QuestionStage.RESOLUTION,
        20,
        AnswerValueKind.SINGLE_CHOICE,
        (_act("48"), _act("14"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        # s. 48 makes the *effect* on co-ownership the gate, not the number of
        # owners, so both halves of the §4.3 question are one value.
        options=(
            _opt("Q20_COOWNERS", "SOLE_OWNER_NO_COOWNERSHIP_EFFECT"),
            _opt("Q20_COOWNERS", "COOWNERS_NO_CHANGE"),
            _opt("Q20_COOWNERS", "CREATES_OR_ALTERS_COOWNERSHIP"),
            _opt("Q20_COOWNERS", "UNKNOWN"),
        ),
        activates=("lk.rta.module.coowners",),
        inferable=True,
        controls_v0_eligibility=True,
        v0_required=True,
    ),
    _q(
        "Q21_COMPANY_AUTH",
        QuestionStage.RESOLUTION,
        21,
        AnswerValueKind.TEXT,
        (SourceCitation(SRC_LAWYER_PRACTICE.id), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        activates=("lk.rta.module.company_party",),
        inferable=True,
    ),
    _q(
        "Q22_POA",
        QuestionStage.RESOLUTION,
        22,
        AnswerValueKind.TRI_STATE,
        (SourceCitation(SRC_RGD_TRANSACTIONS.id), SourceCitation(SRC_LAWYER_PRACTICE.id)),
        # Extraction surfaces the authorising clause and the land description
        # as evidence regions; whether they *expressly authorise this
        # transaction* is the legal conclusion the answer records, so the
        # answer itself is never proposed by the pipeline.
        activates=("lk.rta.module.power_of_attorney",),
        inferable=False,
        controls_v0_eligibility=True,
    ),
    _q(
        "Q23_SEARCH_CUTOFF",
        QuestionStage.RESOLUTION,
        23,
        AnswerValueKind.DATE,
        (
            _act("34"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id),
            SourceCitation(SRC_LAWYER_PRACTICE.id),
        ),
        # The date is extractable; whether it is still current enough to
        # execute against is the lawyer's call and drives CurrencyStatus.
        inferable=True,
        v0_required=True,
    ),
    _q(
        "Q24_CONSIDERATION",
        QuestionStage.RESOLUTION,
        24,
        AnswerValueKind.MONEY,
        (SourceCitation(SRC_RGD_CHARGES.id), SourceCitation(SRC_LAWYER_PRACTICE.id)),
        # Draftly records the confirmed consideration and the payment evidence.
        # It does not compute stamp duty from hard-coded rates (§13.4).
        inferable=True,
        v0_required=True,
    ),
    _q(
        "Q25_DEADLINE",
        QuestionStage.RESOLUTION,
        25,
        AnswerValueKind.DATE,
        (_act("45(1)"), SourceCitation(SRC_RGD_TRANSACTIONS.id)),
        # Attestation starts the seven-working-day forwarding clock. Export or
        # signature of a draft is not attestation (§9.6).
        inferable=True,
        v0_required=True,
    ),
)


ALL_QUESTIONS: tuple[QuestionDefinition, ...] = (*ROUTING_QUESTIONS, *RESOLUTION_QUESTIONS)


def should_reopen(previous_status: AnswerStatus, conflicting_evidence: bool) -> bool:
    """§4.4 — must a suppressed or already-answered question be asked again?

    ``conflicting_evidence`` is the caller's summary of the three triggers the
    spec lists: a later file conflicts, the source behind the answer was
    superseded, or the document the answer rested on was rejected in review.

    ``LAWYER_CONFIRMED`` is deliberately not exempt. A conflicting extraction
    re-opens the question as a review task rather than silently replacing what
    the lawyer said.
    """
    if previous_status is AnswerStatus.SUPERSEDED:
        return True
    return conflicting_evidence


# ── Lookups ──────────────────────────────────────────────────────────────────

_BY_ID: dict[str, QuestionDefinition] = {q.id: q for q in ALL_QUESTIONS}


def get_question(question_id: str) -> QuestionDefinition | None:
    return _BY_ID.get(question_id)


def require_question(question_id: str) -> QuestionDefinition:
    question = _BY_ID.get(question_id)
    if question is None:
        raise KeyError(f"Unknown RTA intake question '{question_id}'.")
    return question


def questions_for_stage(stage: QuestionStage) -> tuple[QuestionDefinition, ...]:
    return tuple(q for q in ALL_QUESTIONS if q.stage is stage)


def v0_question_ids() -> tuple[str, ...]:
    """The §14.3 implement-now set, in ask order."""
    return tuple(q.id for q in ALL_QUESTIONS if q.v0_required)

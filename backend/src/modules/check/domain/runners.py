"""The deterministic V0 checks (§7.2, §14.5).

Every runner is a pure function ``(CheckInput) -> CheckEvaluation``. Severity,
blocker kind, issue type, and the safety-rule key always come from
`content_governance.contracts.require_check`, never from a literal here: the
catalogue is governed content and this file is only the arithmetic that
consumes it.

Four behaviours are load-bearing, and each is a test:

1. **A missing input is never a PASS.** It is ``INCONCLUSIVE`` plus a
   missing-evidence issue, and where the definition sets
   ``absence_is_not_evidence`` a PASS additionally requires a confirmed dated
   register search — a silent file is not a negative fact (§6.4).
2. **A statutory contravention is evaluated before the evidence guard.** Once
   the disposition is known to be a part-parcel or a co-ownership-conferring
   transaction, a missing extent does not make s. 47 or s. 48 go away.
3. **A conflicted input fails as an evidence problem** — at the definition's
   failure severity but with ``BlockerKind.EVIDENCE``, because the defect is in
   the documents, not (yet) in the transaction.
4. **The assessment-register check is a WARNING and nothing else.** A council
   record is contextual evidence, never title (§1.2, §7.2).

`INCONCLUSIVE` and `NOT_RUN` are different answers and stay different:
`NOT_RUN` means the comparison does not apply to this matter's routing (no
company party, no deceased owner), `INCONCLUSIVE` means it applies and the
evidence does not settle it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from src.modules.check.domain.models import FactVersionPin
from src.modules.content_governance.contracts import (
    BlockerKind,
    CheckDefinition,
    CheckOutcome,
    DispositionScope,
    DisputeStage,
    EncumbranceStatus,
    IssueSeverity,
    NoticeStatus,
    OccupationStatus,
    PartyContext,
    TitleClass,
    require_check,
    templates_for_subtype,
)
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary

#: A conclusion whose explanation key contains this marker rests on a rule this
#: repository cannot verify yet. §16.4 item 5 (the Sri Lankan public-holiday
#: calendar) is the reason the attestation deadline is always one of them.
PROVISIONAL_MARKER = ".provisional_"

#: The confirmed fact whose presence means a dated register/encumbrance search
#: exists. Mirrors `verification`'s own constant; duplicated rather than
#: imported because a module may not reach into another module's infrastructure.
SEARCH_FACT_TYPE_ID = "rta.title.register_search_datetime"

#: The lawyer's conclusion about two names, which `CHK_OWNER_TRANSFEROR` reads
#: instead of comparing strings itself (§7.2, `facts.py`).
TRANSFEROR_IS_OWNER_FACT_TYPE_ID = "rta.party.transferor_is_registered_owner"

#: Enum members and blanks that mean "nobody has looked yet". They are treated
#: as *absent* inputs, never as negative answers (§6.4). ``NOT_FOUND_IN_
#: CURRENT_SEARCH`` is deliberately not here: it records what a dated search
#: showed and is a real answer.
_ABSENT_VALUES: frozenset[str] = frozenset({"", "UNKNOWN", "NO_EVIDENCE_REVIEWED"})

_LITIGATION_HOLD_STAGES: frozenset[DisputeStage] = frozenset(
    {
        DisputeStage.S21_DC_REFERRED,
        DisputeStage.S22_APPEAL_FILED,
        DisputeStage.COURT_INQUIRY_PENDING,
        DisputeStage.COURT_ORDER_ISSUED,
        DisputeStage.S29_CHALLENGE_NOTED,
        DisputeStage.RECTIFICATION_PENDING,
    }
)

#: §8.4 — settlement is under way. Manual title-settlement handling continues;
#: only automated output stops. Draftly never ranks the claimants.
_SETTLEMENT_PENDING_STAGES: frozenset[DisputeStage] = frozenset(
    {
        DisputeStage.S12_NOTICE_PUBLISHED,
        DisputeStage.CLAIM_WINDOW_OPEN,
        DisputeStage.CLAIMS_FILED,
        DisputeStage.S13_INVESTIGATION_PENDING,
        DisputeStage.CONCILIATION_PENDING,
        DisputeStage.SCHEDULE_PREPARED,
    }
)

_CLEAR_STAGES: frozenset[DisputeStage] = frozenset(
    {
        DisputeStage.NO_INDICIA_FOUND,
        DisputeStage.INITIAL_REGISTER_CREATED,
        DisputeStage.FINAL_REGISTER_CONFIRMED,
    }
)

#: Working days allowed between attestation and presentation (RTA s. 45(1)).
ATTESTATION_DEADLINE_WORKING_DAYS = 7

#: Working days remaining at which the deadline stops being comfortable. Chosen
#: as a product default, not a legal rule; the responsible lawyer owns the
#: conclusion either way (§7.2 CHK_ATTESTATION_DEADLINE).
ATTESTATION_IMMINENT_WORKING_DAYS = 2


@dataclass(frozen=True)
class CheckInput:
    """Everything a deterministic check may read, and nothing else.

    The confirmed fact tier is the evidence; the routing values are how the
    matter was classified. Routing values are optional because most of them
    also exist as facts — where both are present the confirmed fact wins, since
    it is the one carrying a version to pin.
    """

    matter_id: str
    facts: FactTierSummary
    evaluated_at: datetime
    subtype_id: str | None = None
    #: Left empty by default: `derive_party_contexts` reconstructs what it can
    #: from the fact tier. A caller that has the matter's routing answers may
    #: pass them, and they then take precedence.
    party_contexts: frozenset[PartyContext] = frozenset()
    disposition_scope: DispositionScope = DispositionScope.UNKNOWN
    dispute_stage: DisputeStage | None = None
    #: Office policy for how old a register search may be. ``None`` means no
    #: office has configured one, which makes currency unknowable rather than
    #: current (§5.4, §16.4).
    search_currency_max_age_days: int | None = None

    def effective_party_contexts(self) -> frozenset[PartyContext]:
        return self.party_contexts or derive_party_contexts(self.facts)


@dataclass(frozen=True)
class CheckEvaluation:
    """One check's verdict, with everything the result row and issue need."""

    check_definition_id: str
    check_definition_version: str
    outcome: CheckOutcome
    #: The severity an issue raised from this result starts at. A lawyer may
    #: reclassify it at TRIAGED within policy; the check never does (§10.6).
    default_severity: IssueSeverity
    blocker_kind: BlockerKind
    issue_type_id: str
    explanation_key: str
    safety_rule_key: str
    source_record_ids: tuple[str, ...]
    requires_human_conclusion: bool
    input_fact_versions: tuple[FactVersionPin, ...] = field(default_factory=tuple)
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    missing_fact_type_ids: tuple[str, ...] = field(default_factory=tuple)
    conflicted_fact_type_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def raises_issue(self) -> bool:
        """An inconclusive check raises an issue too — that is the whole point.

        Silence about evidence nobody has produced is what §6.4 forbids.
        """
        return self.outcome in {CheckOutcome.FAIL, CheckOutcome.INCONCLUSIVE}

    @property
    def is_provisional(self) -> bool:
        return is_provisional(self.explanation_key)


def is_provisional(explanation_key: str) -> bool:
    """Whether the conclusion rests on a rule that is not yet verified."""
    return PROVISIONAL_MARKER in explanation_key


Runner = Callable[[CheckInput], CheckEvaluation]


# ── Reading the fact tier ────────────────────────────────────────────────────


def _is_absent(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    return str(value).strip().upper() in _ABSENT_VALUES


def _confirmed(ctx: CheckInput, fact_type_id: str) -> ConfirmedFactValue | None:
    confirmed = ctx.facts.confirmed.get(fact_type_id)
    if confirmed is None or _is_absent(confirmed.value):
        return None
    return confirmed


def _value(ctx: CheckInput, fact_type_id: str) -> Any | None:
    confirmed = _confirmed(ctx, fact_type_id)
    return confirmed.value if confirmed is not None else None


def _text(ctx: CheckInput, fact_type_id: str) -> str | None:
    raw = _value(ctx, fact_type_id)
    return str(raw).strip() if raw is not None else None


def _flag(ctx: CheckInput, fact_type_id: str) -> bool | None:
    """Read a BOOLEAN fact. Anything that is not a boolean is not an answer."""
    raw = _value(ctx, fact_type_id)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.strip().upper() in {"TRUE", "FALSE"}:
        return raw.strip().upper() == "TRUE"
    return None


def _enum_fact[E: Enum](ctx: CheckInput, fact_type_id: str, enum_type: type[E]) -> E | None:
    raw = _value(ctx, fact_type_id)
    if raw is None:
        return None
    try:
        return enum_type(str(raw))
    except ValueError:
        return None


def _date_fact(ctx: CheckInput, fact_type_id: str) -> date | None:
    raw = _value(ctx, fact_type_id)
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _pins(ctx: CheckInput, fact_type_ids: Iterable[str]) -> tuple[FactVersionPin, ...]:
    """Pin the exact version of every input that was actually readable.

    Only confirmed values are pinned, so a later correction shows up as a
    different input set rather than as a silent reinterpretation (§7.1).
    """
    return tuple(
        FactVersionPin(fact_id=confirmed.fact_id, version=confirmed.version)
        for fact_type_id in dict.fromkeys(fact_type_ids)
        if (confirmed := _confirmed(ctx, fact_type_id)) is not None
    )


def _evidence(ctx: CheckInput, fact_type_ids: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for fact_type_id in dict.fromkeys(fact_type_ids):
        confirmed = _confirmed(ctx, fact_type_id)
        if confirmed is None:
            continue
        for reference_id in confirmed.evidence_reference_ids:
            seen[reference_id] = None
    return tuple(seen)


def derive_party_contexts(facts: FactTierSummary) -> frozenset[PartyContext]:
    """Reconstruct the §4.2 party contexts from confirmed facts alone.

    A power of attorney has no fact type of its own, so an execution route that
    is neither natural persons, nor a company, nor an estate lands in
    ``OTHER_NON_INDIVIDUAL`` — which `CHK_POA_SCOPE` treats as the V0 exclusion
    it is, rather than guessing from the free text of the signing authority.
    """
    contexts: set[PartyContext] = set()
    confirmed = facts.confirmed
    if "rta.org.company_name" in confirmed or "rta.org.company_number" in confirmed:
        contexts.add(PartyContext.COMPANY)
    if "rta.process.probate_path" in confirmed or "rta.process.transmission_completed" in confirmed:
        contexts.add(PartyContext.ESTATE_OR_DECEASED)
    natural = confirmed.get("rta.party.all_natural_persons")
    if natural is not None and natural.value is False and not contexts:
        contexts.add(PartyContext.OTHER_NON_INDIVIDUAL)
    if natural is not None and natural.value is True:
        contexts.add(PartyContext.NATURAL_PERSONS_ONLY)
    return frozenset(contexts)


# ── Building an evaluation ───────────────────────────────────────────────────


def _evaluation(
    definition: CheckDefinition,
    ctx: CheckInput,
    consumed: Iterable[str],
    *,
    outcome: CheckOutcome,
    reason: str,
    severity: IssueSeverity,
    blocker_kind: BlockerKind,
    missing: tuple[str, ...] = (),
    conflicted: tuple[str, ...] = (),
) -> CheckEvaluation:
    consumed = tuple(consumed)
    return CheckEvaluation(
        check_definition_id=definition.id,
        check_definition_version=definition.version,
        outcome=outcome,
        default_severity=severity,
        blocker_kind=blocker_kind,
        issue_type_id=definition.issue_type_id,
        explanation_key=f"rta.check.{definition.id}.explanation.{reason}",
        safety_rule_key=definition.safety_rule_key,
        source_record_ids=tuple(
            dict.fromkeys(citation.source_record_id for citation in definition.sources)
        ),
        requires_human_conclusion=definition.requires_human_conclusion,
        input_fact_versions=_pins(ctx, consumed),
        evidence_reference_ids=_evidence(ctx, consumed),
        missing_fact_type_ids=missing,
        conflicted_fact_type_ids=conflicted,
    )


def _pass(
    definition: CheckDefinition,
    ctx: CheckInput,
    consumed: Iterable[str],
    *,
    reason: str = "pass",
) -> CheckEvaluation:
    """The comparison passed — subject to the one thing a PASS cannot assume.

    Where the definition sets ``absence_is_not_evidence``, passing means "no
    registered interest was found", and that proposition is only knowable from
    a dated search. Without one the honest answer is ``INCONCLUSIVE``, and this
    is the single place that decision is made so no runner can forget it.
    """
    consumed = tuple(consumed)
    if definition.absence_is_not_evidence and not ctx.facts.has_current_search_evidence:
        return _inconclusive(
            definition,
            ctx,
            consumed,
            reason="no_current_search_evidence",
            missing=(SEARCH_FACT_TYPE_ID,),
        )
    return _evaluation(
        definition,
        ctx,
        consumed,
        outcome=CheckOutcome.PASS,
        reason=reason,
        severity=IssueSeverity.INFORMATION,
        blocker_kind=definition.failure_blocker_kind,
    )


def _fail(
    definition: CheckDefinition,
    ctx: CheckInput,
    consumed: Iterable[str],
    *,
    reason: str,
    severity: IssueSeverity | None = None,
    blocker_kind: BlockerKind | None = None,
    conflicted: tuple[str, ...] = (),
) -> CheckEvaluation:
    return _evaluation(
        definition,
        ctx,
        consumed,
        outcome=CheckOutcome.FAIL,
        reason=reason,
        severity=severity or definition.failure_severity,
        blocker_kind=blocker_kind or definition.failure_blocker_kind,
        conflicted=conflicted,
    )


def _inconclusive(
    definition: CheckDefinition,
    ctx: CheckInput,
    consumed: Iterable[str],
    *,
    reason: str,
    severity: IssueSeverity | None = None,
    missing: tuple[str, ...] = (),
) -> CheckEvaluation:
    return _evaluation(
        definition,
        ctx,
        consumed,
        outcome=CheckOutcome.INCONCLUSIVE,
        reason=reason,
        severity=severity or definition.inconclusive_severity,
        # An evidence gap closes on evidence, whatever the definition's failure
        # blocker kind is: not knowing whether s. 47 applies is not itself a
        # statutory contravention.
        blocker_kind=BlockerKind.EVIDENCE,
        missing=missing,
    )


def _not_run(
    definition: CheckDefinition, ctx: CheckInput, consumed: Iterable[str], *, reason: str
) -> CheckEvaluation:
    return _evaluation(
        definition,
        ctx,
        consumed,
        outcome=CheckOutcome.NOT_RUN,
        reason=reason,
        severity=IssueSeverity.INFORMATION,
        blocker_kind=definition.failure_blocker_kind,
    )


def _input_guard(
    definition: CheckDefinition,
    ctx: CheckInput,
    required: Iterable[str],
    *,
    consumed: Iterable[str] | None = None,
    missing_severity: IssueSeverity | None = None,
) -> CheckEvaluation | None:
    """Refuse to compare inputs that disagree or are not there.

    Conflicts are tested first: "the documents say two different things" is a
    more useful answer than "one of them is missing", and both are true when a
    fact tier reports a conflict.
    """
    required = tuple(required)
    consumed = tuple(consumed) if consumed is not None else required
    conflicted = tuple(f for f in required if f in ctx.facts.conflicted_fact_type_ids)
    if conflicted:
        return _fail(
            definition,
            ctx,
            consumed,
            reason="conflicting_inputs",
            blocker_kind=BlockerKind.EVIDENCE,
            conflicted=conflicted,
        )
    missing = tuple(f for f in required if _confirmed(ctx, f) is None)
    if missing:
        return _inconclusive(
            definition,
            ctx,
            consumed,
            reason="missing_input",
            severity=missing_severity,
            missing=missing,
        )
    return None


# ── Comparison helpers ───────────────────────────────────────────────────────


class AreaComparison(str, Enum):
    """Result of comparing two recorded extents.

    ``INCOMPARABLE`` exists because no verified unit-conversion table lives in
    this repository: two extents in different units are not silently converted
    and then declared equal (§7.2 "convert units transparently").
    """

    EQUAL = "EQUAL"
    SMALLER = "SMALLER"
    LARGER = "LARGER"
    DIFFERENT = "DIFFERENT"
    INCOMPARABLE = "INCOMPARABLE"


def _parse_area(raw: str) -> tuple[Decimal, str] | None:
    text = raw.strip().replace(",", "")
    magnitude = ""
    index = 0
    while index < len(text) and (text[index].isdigit() or text[index] == "."):
        magnitude += text[index]
        index += 1
    if not magnitude:
        return None
    try:
        return Decimal(magnitude), text[index:].strip().rstrip(".").lower()
    except InvalidOperation:
        return None


def compare_areas(parcel: str, transaction: str) -> AreaComparison:
    """Compare the registered extent with the extent subject to the transaction."""
    left, right = _parse_area(parcel), _parse_area(transaction)
    if left is None or right is None:
        return (
            AreaComparison.EQUAL
            if _normalise(parcel) == _normalise(transaction)
            else AreaComparison.DIFFERENT
        )
    if left[1] != right[1]:
        return AreaComparison.INCOMPARABLE
    if right[0] == left[0]:
        return AreaComparison.EQUAL
    return AreaComparison.LARGER if right[0] > left[0] else AreaComparison.SMALLER


def _normalise(raw: str) -> str:
    """Case- and spacing-insensitive form, used only where a mismatch downgrades.

    Never used to decide that two *people* are the same: §7.2 forbids silently
    normalising a different person into a match.
    """
    return " ".join(raw.strip().lower().split())


def _add_working_days(start: date, days: int) -> date:
    current, remaining = start, days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _working_days_between(start: date, end: date) -> int:
    count, current = 0, start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


# ── The checks (§7.2, in catalogue order) ────────────────────────────────────


def run_party_identity(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_PARTY_IDENTITY")
    consumed = definition.input_fact_type_ids
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    transferor_nic = _text(ctx, "rta.party.transferor_nic")
    transferee_nic = _text(ctx, "rta.party.transferee_nic")
    if transferor_nic is not None and transferor_nic == transferee_nic:
        # §7.2 escalates an ID-number or role conflict above the HIGH_RISK
        # default: one identity cannot stand on both sides of a disposition,
        # and no alias explanation resolves that.
        return _fail(
            definition,
            ctx,
            consumed,
            reason="same_identity_on_both_sides",
            severity=IssueSeverity.BLOCKING,
        )
    if _flag(ctx, "rta.party.capacity_confirmed") is not True:
        return _fail(definition, ctx, consumed, reason="capacity_not_confirmed")
    return _pass(definition, ctx, consumed)


def run_owner_transferor(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_OWNER_TRANSFEROR")
    consumed = (*definition.input_fact_type_ids, TRANSFEROR_IS_OWNER_FACT_TYPE_ID)
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    # The comparison is the lawyer's recorded conclusion about two names, not a
    # string equality: an alias, a maiden name, or a transliteration is a real
    # explanation and only a human may accept it (§7.2).
    if _flag(ctx, TRANSFEROR_IS_OWNER_FACT_TYPE_ID) is False:
        return _fail(definition, ctx, consumed, reason="transferor_is_not_registered_owner")
    return _pass(definition, ctx, consumed)


def run_title_reference(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_TITLE_REFERENCE")
    consumed = definition.input_fact_type_ids
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    if _flag(ctx, "rta.regime.coverage_confirmed") is not True:
        return _fail(definition, ctx, consumed, reason="rta_coverage_not_confirmed")
    if _enum_fact(ctx, "rta.title.class", TitleClass) is None:
        return _fail(definition, ctx, consumed, reason="title_class_not_recognised")
    return _pass(definition, ctx, consumed)


def run_parcel_id(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_PARCEL_ID")
    consumed = definition.input_fact_type_ids
    # There is nothing to compare beyond the identifiers themselves: a conflict
    # between documents is what the fact tier reports, and §7.2 forbids fuzzy
    # auto-acceptance of anything else.
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    return _pass(definition, ctx, consumed)


def run_extent(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_EXTENT")
    consumed = definition.input_fact_type_ids
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    parcel = _text(ctx, "rta.parcel.extent") or ""
    transaction = _text(ctx, "rta.parcel.extent_subject_to_transaction") or ""
    comparison = compare_areas(parcel, transaction)
    if comparison is AreaComparison.EQUAL:
        return _pass(definition, ctx, consumed)
    if comparison is AreaComparison.INCOMPARABLE:
        return _inconclusive(
            definition, ctx, consumed, reason="provisional_unit_conversion_unverified"
        )
    if comparison is AreaComparison.LARGER:
        # The instrument would dispose of more than the register records, so no
        # form can describe the parcel accurately — the §7.2 escalation.
        return _fail(
            definition,
            ctx,
            consumed,
            reason="transaction_extent_exceeds_registered_parcel",
            severity=IssueSeverity.BLOCKING,
        )
    return _fail(definition, ctx, consumed, reason="extent_discrepancy")


def run_whole_part(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_WHOLE_PART")
    consumed = definition.input_fact_type_ids
    scope = (
        _enum_fact(ctx, "rta.instrument.disposition_scope", DispositionScope)
        or ctx.disposition_scope
    )
    # Deliberately before the evidence guard: s. 47 forbids dealing with part of
    # a registered parcel before subdivision, and a missing extent does not make
    # a part disposition into a whole one.
    if scope is DispositionScope.PART_OF_PARCEL:
        return _fail(definition, ctx, consumed, reason="part_of_parcel_without_subdivision")
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    if scope is DispositionScope.WHOLE_REGISTERED_PARCEL:
        comparison = compare_areas(
            _text(ctx, "rta.parcel.extent") or "",
            _text(ctx, "rta.parcel.extent_subject_to_transaction") or "",
        )
        if comparison is AreaComparison.INCOMPARABLE:
            return _inconclusive(
                definition, ctx, consumed, reason="provisional_unit_conversion_unverified"
            )
        if comparison is not AreaComparison.EQUAL:
            # Whole parcel is claimed but only part of the extent is disposed of.
            # In substance that is a part disposition and s. 47 still applies.
            return _fail(
                definition, ctx, consumed, reason="whole_parcel_claimed_for_partial_extent"
            )
    return _pass(definition, ctx, consumed)


def run_coownership(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_COOWNERSHIP")
    consumed = definition.input_fact_type_ids
    # s. 48 again outranks the evidence guard: an instrument that would confer
    # co-ownership is invalid except as the Act provides, whatever else is known.
    if _flag(ctx, "rta.party.creates_coownership") is True:
        return _fail(definition, ctx, consumed, reason="prohibited_coownership_effect")
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    scope = (
        _enum_fact(ctx, "rta.instrument.disposition_scope", DispositionScope)
        or ctx.disposition_scope
    )
    title_class = _enum_fact(ctx, "rta.title.class", TitleClass)
    if scope is DispositionScope.UNDIVIDED_INTEREST and title_class is not TitleClass.CO_OWNERSHIP:
        return _fail(
            definition, ctx, consumed, reason="undivided_interest_would_confer_coownership"
        )
    return _pass(definition, ctx, consumed)


def run_mortgage_status(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_MORTGAGE_STATUS")
    consumed = definition.input_fact_type_ids
    required = ("rta.interest.mortgage_status", SEARCH_FACT_TYPE_ID)
    blocked = _input_guard(definition, ctx, required, consumed=consumed)
    if blocked is not None:
        return blocked
    status = _enum_fact(ctx, "rta.interest.mortgage_status", EncumbranceStatus)
    if status is None:
        return _inconclusive(
            definition,
            ctx,
            consumed,
            reason="mortgage_status_not_recognised",
            missing=("rta.interest.mortgage_status",),
        )
    if status.blocks_transfer_approval:
        # A repaid loan, a bank's settlement letter, and a quiet file are all
        # the same thing to the register: an interest that is still entered.
        # Only a registered cancellation clears this (§7.2, §15.4).
        return _fail(definition, ctx, consumed, reason=f"mortgage_{status.value.lower()}")
    return _pass(definition, ctx, consumed)


def run_lease_status(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_LEASE_STATUS")
    consumed = definition.input_fact_type_ids
    required = ("rta.interest.lease_status", "rta.interest.occupation_status", SEARCH_FACT_TYPE_ID)
    blocked = _input_guard(definition, ctx, required, consumed=consumed)
    if blocked is not None:
        return blocked
    lease = _enum_fact(ctx, "rta.interest.lease_status", EncumbranceStatus)
    if lease is not None and lease.blocks_transfer_approval:
        return _fail(definition, ctx, consumed, reason=f"lease_{lease.value.lower()}")
    occupation = _enum_fact(ctx, "rta.interest.occupation_status", OccupationStatus)
    if occupation in {
        OccupationStatus.THIRD_PARTY_OCCUPATION,
        OccupationStatus.UNDER_REGISTERED_LEASE,
    }:
        return _fail(definition, ctx, consumed, reason="third_party_in_possession")
    return _pass(definition, ctx, consumed)


def run_caveat_litigation(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_CAVEAT_LITIGATION")
    consumed = definition.input_fact_type_ids
    stage = _enum_fact(ctx, "rta.process.dispute_stage", DisputeStage) or ctx.dispute_stage
    # A live proceeding is a hold regardless of what else is on file. Draftly
    # summarises and stops there; it never decides the merits (§8.4).
    if stage in _LITIGATION_HOLD_STAGES:
        return _fail(definition, ctx, consumed, reason="litigation_hold")
    required = (
        "rta.interest.caveat_or_notice_status",
        "rta.process.dispute_stage",
        SEARCH_FACT_TYPE_ID,
    )
    blocked = _input_guard(definition, ctx, required, consumed=consumed)
    if blocked is not None:
        return blocked
    notice = _enum_fact(ctx, "rta.interest.caveat_or_notice_status", NoticeStatus)
    if notice is NoticeStatus.PRESENT_UNRESOLVED:
        return _fail(definition, ctx, consumed, reason="notice_or_caveat_unresolved")
    if stage in _SETTLEMENT_PENDING_STAGES:
        return _fail(definition, ctx, consumed, reason="title_settlement_in_progress")
    if stage is DisputeStage.S14_DECLARATION_PUBLISHED:
        # §8.4 rates this HIGH_RISK "escalating to BLOCKING before drafting".
        # The only consumer of the result is the drafting gate, so the escalated
        # value is what gets recorded rather than one that would let a draft out.
        return _fail(definition, ctx, consumed, reason="declaration_status_unconfirmed")
    if stage not in _CLEAR_STAGES:
        return _fail(definition, ctx, consumed, reason="dispute_stage_not_cleared")
    return _pass(definition, ctx, consumed)


def run_probate_authority(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_PROBATE_AUTHORITY")
    consumed = definition.input_fact_type_ids
    if PartyContext.ESTATE_OR_DECEASED not in ctx.effective_party_contexts():
        return _not_run(definition, ctx, consumed, reason="no_deceased_owner")
    required = (
        "rta.process.transmission_completed",
        "rta.party.signing_authority",
        "rta.title.registered_owner_name",
    )
    blocked = _input_guard(
        definition,
        ctx,
        required,
        consumed=consumed,
        # §7.2: unresolved signer/title authority is BLOCKING, and "unresolved"
        # is exactly what a missing transmission record means here.
        missing_severity=definition.failure_severity,
    )
    if blocked is not None:
        return blocked
    if _flag(ctx, "rta.process.transmission_completed") is not True:
        return _fail(definition, ctx, consumed, reason="transmission_not_completed")
    return _pass(definition, ctx, consumed)


def run_company_authority(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_COMPANY_AUTHORITY")
    consumed = definition.input_fact_type_ids
    if PartyContext.COMPANY not in ctx.effective_party_contexts():
        return _not_run(definition, ctx, consumed, reason="no_company_party")
    required = (
        "rta.org.company_name",
        "rta.org.company_number",
        "rta.org.resolution_date",
        "rta.party.signing_authority",
    )
    blocked = _input_guard(
        definition, ctx, required, consumed=consumed, missing_severity=definition.failure_severity
    )
    if blocked is not None:
        return blocked
    return _pass(definition, ctx, consumed)


def run_poa_scope(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_POA_SCOPE")
    consumed = definition.input_fact_type_ids
    contexts = ctx.effective_party_contexts()
    if not contexts & {PartyContext.ATTORNEY_POWER_OF_ATTORNEY, PartyContext.OTHER_NON_INDIVIDUAL}:
        return _not_run(definition, ctx, consumed, reason="no_attorney_execution")
    # §7.2 marks attorney-executed matters a V0 exclusion outright, so there is
    # no evidence set that turns this into a PASS. The manual path stays open.
    return _fail(definition, ctx, consumed, reason="attorney_execution_outside_v0")


def run_assessment_name(ctx: CheckInput) -> CheckEvaluation:
    """A council assessment record is contextual evidence, never title.

    This check may report that two records disagree. It may never conclude, or
    contribute to concluding, that the seller lacks title — which is why its
    severity stays ``WARNING`` and its definition sets ``blocks_approval`` false
    (§1.2, §7.2, §Executive 9).
    """
    definition = require_check("CHK_ASSESSMENT_NAME")
    consumed = definition.input_fact_type_ids
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    assessment = _text(ctx, "rta.local.assessment_register_name") or ""
    owner = _text(ctx, "rta.title.registered_owner_name") or ""
    if _normalise(assessment) != _normalise(owner):
        return _fail(definition, ctx, consumed, reason="assessment_name_mismatch")
    return _pass(definition, ctx, consumed)


def run_form_required_fields(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_FORM_REQUIRED_FIELDS")
    templates = templates_for_subtype(ctx.subtype_id) if ctx.subtype_id else ()
    mappings = tuple(
        mapping for template in templates for mapping in template.field_mappings if mapping.required
    )
    consumed = tuple(m.fact_type_id for m in mappings if m.fact_type_id is not None)
    if not mappings:
        return _not_run(definition, ctx, consumed, reason="no_template_selected")
    # A field with no canonical fact type can only ever be lawyer-entered, so it
    # counts as unresolved until the drafting module records that entry (§9.3).
    unresolved = tuple(
        m.field_id
        for m in mappings
        if m.fact_type_id is None or _confirmed(ctx, m.fact_type_id) is None
    )
    if unresolved:
        return _evaluation(
            definition,
            ctx,
            consumed,
            outcome=CheckOutcome.FAIL,
            reason="required_field_unresolved",
            severity=definition.failure_severity,
            blocker_kind=definition.failure_blocker_kind,
            missing=unresolved,
        )
    return _pass(definition, ctx, consumed)


def run_document_currency(ctx: CheckInput) -> CheckEvaluation:
    definition = require_check("CHK_DOCUMENT_CURRENCY")
    consumed = definition.input_fact_type_ids
    blocked = _input_guard(definition, ctx, (SEARCH_FACT_TYPE_ID,), consumed=consumed)
    if blocked is not None:
        return blocked
    max_age = ctx.search_currency_max_age_days
    if max_age is None:
        # No office has configured a validity period and no official source in
        # this repository states one (§16.4 items 2 and 6). An undated rule
        # produces UNKNOWN currency, never CURRENT (§5.4).
        return _inconclusive(
            definition, ctx, consumed, reason="provisional_currency_policy_not_configured"
        )
    searched = _date_fact(ctx, SEARCH_FACT_TYPE_ID)
    if searched is None:
        return _inconclusive(
            definition,
            ctx,
            consumed,
            reason="search_date_not_readable",
            missing=(SEARCH_FACT_TYPE_ID,),
        )
    if (ctx.evaluated_at.date() - searched).days > max_age:
        return _fail(definition, ctx, consumed, reason="register_search_stale")
    return _pass(definition, ctx, consumed)


def run_attestation_deadline(ctx: CheckInput) -> CheckEvaluation:
    """Seven working days from attestation (RTA s. 45(1)), counted provisionally.

    No verified Sri Lankan public-holiday calendar exists in this repository
    (§16.4 item 5), so the count skips weekends and nothing else. Every outcome
    therefore carries a ``provisional_`` explanation key: the lawyer is told the
    calendar source is unconfirmed rather than being handed a date that quietly
    assumes no holiday falls in the window.
    """
    definition = require_check("CHK_ATTESTATION_DEADLINE")
    consumed = definition.input_fact_type_ids
    blocked = _input_guard(definition, ctx, consumed)
    if blocked is not None:
        return blocked
    attested = _date_fact(ctx, "rta.instrument.attestation_date")
    if attested is None:
        return _inconclusive(
            definition,
            ctx,
            consumed,
            reason="attestation_date_not_readable",
            missing=("rta.instrument.attestation_date",),
        )
    deadline = _add_working_days(attested, ATTESTATION_DEADLINE_WORKING_DAYS)
    today = ctx.evaluated_at.date()
    if today > deadline:
        return _fail(definition, ctx, consumed, reason="provisional_deadline_passed")
    if _working_days_between(today, deadline) <= ATTESTATION_IMMINENT_WORKING_DAYS:
        return _fail(definition, ctx, consumed, reason="provisional_deadline_imminent")
    return _pass(definition, ctx, consumed, reason="provisional_within_deadline")


# ── Registry ─────────────────────────────────────────────────────────────────

#: The §14.5 set V0 cannot launch without, in §7.2 table order.
RUNNERS: dict[str, Runner] = {
    "CHK_PARTY_IDENTITY": run_party_identity,
    "CHK_OWNER_TRANSFEROR": run_owner_transferor,
    "CHK_TITLE_REFERENCE": run_title_reference,
    "CHK_PARCEL_ID": run_parcel_id,
    "CHK_EXTENT": run_extent,
    "CHK_WHOLE_PART": run_whole_part,
    "CHK_COOWNERSHIP": run_coownership,
    "CHK_MORTGAGE_STATUS": run_mortgage_status,
    "CHK_LEASE_STATUS": run_lease_status,
    "CHK_CAVEAT_LITIGATION": run_caveat_litigation,
    "CHK_PROBATE_AUTHORITY": run_probate_authority,
    "CHK_COMPANY_AUTHORITY": run_company_authority,
    "CHK_POA_SCOPE": run_poa_scope,
    "CHK_ASSESSMENT_NAME": run_assessment_name,
    "CHK_FORM_REQUIRED_FIELDS": run_form_required_fields,
    "CHK_DOCUMENT_CURRENCY": run_document_currency,
    "CHK_ATTESTATION_DEADLINE": run_attestation_deadline,
}


def implemented_check_ids() -> tuple[str, ...]:
    """Ordered by the catalogue, so a run reads like the §7.2 table."""
    return tuple(sorted(RUNNERS, key=lambda check_id: require_check(check_id).order))


def run_check(check_id: str, ctx: CheckInput) -> CheckEvaluation:
    return RUNNERS[check_id](ctx)


def run_all(ctx: CheckInput) -> tuple[CheckEvaluation, ...]:
    return tuple(run_check(check_id, ctx) for check_id in implemented_check_ids())

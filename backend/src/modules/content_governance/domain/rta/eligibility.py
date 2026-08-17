"""V0 eligibility predicate and the mandatory legal safety gates.

Two related but distinct questions live here, and collapsing them would be a
bug:

1. **May Draftly automate this matter?** — the §2.3 predicate. Failing it is
   not an error and never deletes or rejects the matter: the matter moves to
   ``MANUAL_SUPPORTED``, keeps its checklist and evidence, and is told why
   (§2.3 closing paragraph, §11.2).
2. **Is there a legal stop condition?** — §14.6. These fire whatever the
   automation scope is, because a part-parcel disposition is void under RTA
   s. 47 whether or not Draftly was going to draft it.

Everything here is a pure function of an explicit input snapshot. No clock, no
I/O, no database. The caller assembles the snapshot from confirmed intake
answers and lawyer-confirmed facts; this module never reads a candidate value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.modules.content_governance.domain.enums import (
    AutomationScope,
    BlockerKind,
    DispositionScope,
    DisputeStage,
    IssueSeverity,
    LegalRegime,
    MatterState,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
    TriState,
)
from src.modules.content_governance.domain.rta.fact_values import (
    EncumbranceStatus,
    NoticeStatus,
    OccupationStatus,
)
from src.modules.content_governance.domain.rta.taxonomy import (
    get_subtype,
)
from src.modules.content_governance.domain.sources import (
    SRC_PRODUCT_SAFETY,
    SRC_RTA_ACT,
    SourceCitation,
)

ELIGIBILITY_VERSION = "1.0.0"

TRANSFER_SALE_SUBTYPE_ID = "lk.rta.instrument.transfer_sale"
MORTGAGE_CANCEL_SUBTYPE_ID = "lk.rta.instrument.mortgage_cancel"

#: Dispute stages that force a litigation hold outright (§8.4).
LITIGATION_HOLD_STAGES: frozenset[DisputeStage] = frozenset(
    {
        DisputeStage.S21_DC_REFERRED,
        DisputeStage.S22_APPEAL_FILED,
        DisputeStage.COURT_INQUIRY_PENDING,
        DisputeStage.S29_CHALLENGE_NOTED,
        DisputeStage.RECTIFICATION_PENDING,
    }
)

#: Dispute stages that block automated drafting but are settlement-process
#: rather than live litigation (§8.4). They route to manual handling.
SETTLEMENT_BLOCKING_STAGES: frozenset[DisputeStage] = frozenset(
    {
        DisputeStage.S12_NOTICE_PUBLISHED,
        DisputeStage.CLAIM_WINDOW_OPEN,
        DisputeStage.CLAIMS_FILED,
        DisputeStage.S13_INVESTIGATION_PENDING,
        DisputeStage.CONCILIATION_PENDING,
        DisputeStage.S14_DECLARATION_PUBLISHED,
        DisputeStage.COURT_ORDER_ISSUED,
        DisputeStage.SCHEDULE_PREPARED,
    }
)

#: Party contexts incompatible with the V0 natural-persons-only pilot (§2.3).
NON_INDIVIDUAL_CONTEXTS: frozenset[PartyContext] = frozenset(
    {
        PartyContext.COMPANY,
        PartyContext.ESTATE_OR_DECEASED,
        PartyContext.ATTORNEY_POWER_OF_ATTORNEY,
        PartyContext.PUBLIC_BODY,
        PartyContext.OTHER_NON_INDIVIDUAL,
    }
)


@dataclass(frozen=True)
class EligibilityInput:
    """The confirmed picture of a matter that the gates reason over.

    Every ``TriState`` field defaults to ``UNKNOWN`` on purpose. An unanswered
    question is not a "no": it leaves the corresponding predicate unmet and
    produces an evidence task, which is the behaviour §4.4 requires.
    """

    regime_id: str = LegalRegime.LK_RTA.value
    subtype_id: str | None = None
    subtype_decision_status: SubtypeDecisionStatus = SubtypeDecisionStatus.PROVISIONAL
    title_status: TitleStatus = TitleStatus.UNKNOWN
    title_certificate_available: TriState = TriState.UNKNOWN
    parcel_kind: ParcelKind = ParcelKind.UNKNOWN
    disposition_scope: DispositionScope = DispositionScope.UNKNOWN
    party_contexts: frozenset[PartyContext] = field(default_factory=frozenset)
    transferor_is_registered_owner: TriState = TriState.UNKNOWN
    transmission_completed: TriState = TriState.NOT_APPLICABLE
    life_interest_present: TriState = TriState.UNKNOWN
    special_condition_present: TriState = TriState.UNKNOWN
    coowners_present: TriState = TriState.UNKNOWN
    creates_coownership: TriState = TriState.UNKNOWN
    dispute_stage: DisputeStage = DisputeStage.NO_INDICIA_FOUND
    active_court_proceeding: TriState = TriState.UNKNOWN
    notice_status: NoticeStatus = NoticeStatus.NO_EVIDENCE_REVIEWED
    mortgage_status: EncumbranceStatus = EncumbranceStatus.NO_EVIDENCE_REVIEWED
    lease_status: EncumbranceStatus = EncumbranceStatus.NO_EVIDENCE_REVIEWED
    occupation_status: OccupationStatus = OccupationStatus.NO_EVIDENCE_REVIEWED
    #: Identifier conflicts surfaced by the check engine (title/parcel/extent).
    identifier_conflict_present: bool = False
    #: Critical fact type ids that are not yet LAWYER_CONFIRMED.
    unconfirmed_critical_fact_type_ids: tuple[str, ...] = ()
    #: True only when the selected template is a lawyer-approved production
    #: rendering with a current source. False today for every template.
    template_verified: bool = False
    source_reverification_required: bool = True
    #: Form 12 pilot inputs (§2.3 closing paragraph).
    identified_mortgage_reference: bool = False
    mortgagee_authority_confirmed: TriState = TriState.UNKNOWN
    discharge_evidence_sufficient: TriState = TriState.UNKNOWN
    cancellation_route_confirmed: TriState = TriState.UNKNOWN


@dataclass(frozen=True)
class Gate:
    """One evaluated predicate or stop condition."""

    id: str
    satisfied: bool
    severity: IssueSeverity
    blocker_kind: BlockerKind
    reason_key: str
    sources: tuple[SourceCitation, ...]
    #: True for §2.3 predicates; false for §14.6 stop conditions that apply
    #: regardless of whether automation was ever on the table.
    is_v0_predicate: bool = True

    @property
    def is_statutory_blocker(self) -> bool:
        return (
            not self.satisfied
            and self.severity is IssueSeverity.BLOCKING
            and self.blocker_kind is BlockerKind.STATUTORY
        )


@dataclass(frozen=True)
class EligibilityDecision:
    """The routing answer, with every reason it reached that answer."""

    automation_scope: AutomationScope
    gates: tuple[Gate, ...]
    #: Suggested exception state. ``None`` means the matter's ordinary state
    #: machine continues; the caller owns the actual transition.
    exception_state: MatterState | None = None

    @property
    def unmet_gate_ids(self) -> tuple[str, ...]:
        return tuple(g.id for g in self.gates if not g.satisfied)

    @property
    def statutory_blockers(self) -> tuple[Gate, ...]:
        return tuple(g for g in self.gates if g.is_statutory_blocker)

    @property
    def blocking_gates(self) -> tuple[Gate, ...]:
        return tuple(
            g for g in self.gates if not g.satisfied and g.severity is IssueSeverity.BLOCKING
        )

    @property
    def is_v0_automated(self) -> bool:
        return self.automation_scope is AutomationScope.V0_AUTOMATED


_PRODUCT = SourceCitation(SRC_PRODUCT_SAFETY.id, locator="V0 scope gate")


def _act(section: str) -> SourceCitation:
    return SourceCitation(SRC_RTA_ACT.id, locator=f"s. {section}")


def _gate(
    gate_id: str,
    satisfied: bool,
    *,
    severity: IssueSeverity = IssueSeverity.BLOCKING,
    blocker_kind: BlockerKind = BlockerKind.V0_SCOPE,
    sources: tuple[SourceCitation, ...] = (_PRODUCT,),
    is_v0_predicate: bool = True,
) -> Gate:
    return Gate(
        id=gate_id,
        satisfied=satisfied,
        severity=severity,
        blocker_kind=blocker_kind,
        reason_key=f"rta.gate.{gate_id.lower()}.reason",
        sources=sources,
        is_v0_predicate=is_v0_predicate,
    )


def _is_yes(value: TriState) -> bool:
    """Only an explicit YES satisfies a predicate. UNKNOWN never does."""
    return value is TriState.YES


def _is_definitely_no(value: TriState) -> bool:
    """Only an explicit NO clears a "must not be present" predicate.

    ``UNKNOWN`` and ``NOT_APPLICABLE`` both leave the question open — the
    second because "not applicable" to a screening question is itself a
    judgement the lawyer must have made.
    """
    return value is TriState.NO


# ── Statutory stop conditions (§14.6) ────────────────────────────────────────


def evaluate_statutory_gates(data: EligibilityInput) -> tuple[Gate, ...]:
    """Stop conditions that hold regardless of automation scope.

    These are ``BlockerKind.STATUTORY`` and cannot be overridden inside
    Draftly by any role (§7.3).
    """
    gates: list[Gate] = []

    # RTA s. 47 — part of a registered parcel cannot be dealt with before
    # subdivision and new registration.
    gates.append(
        _gate(
            "STATUTORY_S47_PART_PARCEL",
            data.disposition_scope is not DispositionScope.PART_OF_PARCEL,
            blocker_kind=BlockerKind.STATUTORY,
            sources=(_act("47"),),
            is_v0_predicate=False,
        )
    )

    # RTA s. 48 — an instrument conferring co-ownership is invalid except as
    # the Act provides. A proposed co-ownership effect is a statutory blocker
    # pending lawyer analysis, not a warning.
    gates.append(
        _gate(
            "STATUTORY_S48_COOWNERSHIP",
            not _is_yes(data.creates_coownership),
            blocker_kind=BlockerKind.STATUTORY,
            sources=(_act("48"), _act("14")),
            is_v0_predicate=False,
        )
    )

    # Owner versus transferor mismatch. Only an explicit NO is a mismatch;
    # UNKNOWN is an evidence gap, handled by the V0 predicate below.
    gates.append(
        _gate(
            "BLOCK_OWNER_TRANSFEROR_MISMATCH",
            data.transferor_is_registered_owner is not TriState.NO,
            blocker_kind=BlockerKind.STATUTORY,
            sources=(_act("44"), _act("45")),
            is_v0_predicate=False,
        )
    )

    gates.append(
        _gate(
            "BLOCK_TITLE_OR_PARCEL_IDENTIFIER_CONFLICT",
            not data.identifier_conflict_present,
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_act("45"),),
            is_v0_predicate=False,
        )
    )

    # An uncompleted probate/transmission blocks: the register still names the
    # deceased owner, so the proposed transferor has no registered title yet.
    transmission_open = (
        PartyContext.ESTATE_OR_DECEASED in data.party_contexts
        and data.transmission_completed is not TriState.YES
    )
    gates.append(
        _gate(
            "BLOCK_UNCOMPLETED_TRANSMISSION",
            not transmission_open,
            blocker_kind=BlockerKind.STATUTORY,
            sources=(_act("54"), _act("55")),
            is_v0_predicate=False,
        )
    )

    # An apparently uncancelled mortgage blocks approval of an unqualified
    # transfer. It does not block evidence work, and it never disappears
    # because a settlement letter was uploaded.
    mortgage_open = (
        data.subtype_id == TRANSFER_SALE_SUBTYPE_ID
        and data.mortgage_status.blocks_transfer_approval
    )
    gates.append(
        _gate(
            "BLOCK_APPARENTLY_UNCANCELLED_MORTGAGE",
            not mortgage_open,
            severity=IssueSeverity.HIGH_RISK,
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_act("44"), _PRODUCT),
            is_v0_predicate=False,
        )
    )

    gates.append(
        _gate(
            "BLOCK_MISSING_CRITICAL_FORM_FACTS",
            not data.unconfirmed_critical_fact_type_ids,
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_act("43"), _act("45"), _PRODUCT),
            is_v0_predicate=False,
        )
    )

    return tuple(gates)


def evaluate_litigation_hold(data: EligibilityInput) -> Gate:
    """§8.4 — a live referral, appeal, inquiry, s. 29 action, or rectification.

    Draftly may summarise competing documents and build a timeline. It must not
    rank claimants or predict an outcome, so the only product behaviour is to
    hold.
    """
    held = data.dispute_stage in LITIGATION_HOLD_STAGES or _is_yes(data.active_court_proceeding)
    return _gate(
        "HOLD_ACTIVE_LITIGATION",
        not held,
        blocker_kind=BlockerKind.STATUTORY,
        sources=(_act("21-25"), _act("29-30"), _act("58-62")),
        is_v0_predicate=False,
    )


# ── V0 predicate (§2.3) ──────────────────────────────────────────────────────


def _common_v0_gates(data: EligibilityInput) -> list[Gate]:
    subtype = get_subtype(data.subtype_id) if data.subtype_id else None
    return [
        _gate("V0_REGIME_IS_RTA", data.regime_id == LegalRegime.LK_RTA.value),
        _gate(
            "V0_CURRENT_TITLE_REGISTER_CONFIRMED",
            data.title_status is TitleStatus.RTA_REGISTERED,
            sources=(_act("1"), _act("32-33"), _PRODUCT),
        ),
        _gate(
            "V0_TITLE_CERTIFICATE_AVAILABLE_OR_VERIFIED",
            _is_yes(data.title_certificate_available),
            sources=(_act("37"), _act("44"), _PRODUCT),
        ),
        _gate(
            "V0_PARCEL_IS_ORDINARY",
            data.parcel_kind is ParcelKind.ORDINARY,
            sources=(_act("50-52"), _PRODUCT),
        ),
        _gate(
            "V0_EXACT_SUBTYPE_SELECTED",
            subtype is not None,
        ),
        _gate(
            "V0_SUBTYPE_LAWYER_CONFIRMED",
            data.subtype_decision_status is SubtypeDecisionStatus.LAWYER_CONFIRMED,
            blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
        ),
        _gate(
            "V0_NO_ACTIVE_DISPUTE_OR_COURT_NOTICE",
            data.dispute_stage
            in {DisputeStage.NO_INDICIA_FOUND, DisputeStage.FINAL_REGISTER_CONFIRMED}
            and not _is_yes(data.active_court_proceeding),
            sources=(_act("21-25"), _act("29-30")),
        ),
        _gate(
            "V0_NO_UNRESOLVED_NOTICE_OR_SEIZURE",
            data.notice_status
            in {NoticeStatus.NOT_FOUND_IN_CURRENT_SEARCH, NoticeStatus.PRESENT_RESOLVED},
            sources=(_act("44"), _PRODUCT),
        ),
        _gate(
            "V0_ALL_CRITICAL_FACTS_LAWYER_CONFIRMED",
            not data.unconfirmed_critical_fact_type_ids,
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_PRODUCT,),
        ),
        _gate(
            "V0_TEMPLATE_AND_SOURCES_VERIFIED",
            data.template_verified and not data.source_reverification_required,
            blocker_kind=BlockerKind.OFFICE_POLICY,
            sources=(_PRODUCT,),
        ),
    ]


def _transfer_v0_gates(data: EligibilityInput) -> list[Gate]:
    """Additional §2.3 predicates for the Form 8 transfer/sale pilot."""
    return [
        _gate(
            "V0_SCOPE_IS_WHOLE_REGISTERED_PARCEL",
            data.disposition_scope is DispositionScope.WHOLE_REGISTERED_PARCEL,
            sources=(_act("47"), _PRODUCT),
        ),
        _gate(
            "V0_TRANSFEROR_IS_CURRENT_REGISTERED_OWNER",
            _is_yes(data.transferor_is_registered_owner),
            sources=(_act("44"),),
        ),
        _gate(
            "V0_PARTIES_ARE_NATURAL_PERSONS",
            # An empty set is not a "yes": Q05 must have been answered
            # NATURAL_PERSONS_ONLY for the pilot to proceed.
            PartyContext.NATURAL_PERSONS_ONLY in data.party_contexts
            and not (data.party_contexts & NON_INDIVIDUAL_CONTEXTS),
            sources=(_PRODUCT,),
        ),
        _gate(
            "V0_NO_POWER_OF_ATTORNEY",
            PartyContext.ATTORNEY_POWER_OF_ATTORNEY not in data.party_contexts,
            sources=(_PRODUCT,),
        ),
        _gate(
            "V0_NO_UNCOMPLETED_TRANSMISSION",
            PartyContext.ESTATE_OR_DECEASED not in data.party_contexts
            and data.transmission_completed is not TriState.NO,
            sources=(_act("54"), _act("55")),
        ),
        _gate(
            "V0_NO_LIFE_INTEREST_OR_SPECIAL_CONDITION",
            _is_definitely_no(data.life_interest_present)
            and _is_definitely_no(data.special_condition_present),
            sources=(_act("46"), _PRODUCT),
        ),
        _gate(
            "V0_NO_PROPOSED_COOWNERSHIP_CREATION",
            _is_definitely_no(data.creates_coownership) and not _is_yes(data.coowners_present),
            sources=(_act("48"), _PRODUCT),
        ),
        _gate(
            "V0_NO_UNRESOLVED_MORTGAGE",
            not data.mortgage_status.blocks_transfer_approval,
            sources=(_act("44"), _PRODUCT),
        ),
        _gate(
            "V0_NO_UNRESOLVED_LEASE_OR_OCCUPATION",
            not data.lease_status.blocks_transfer_approval
            and data.occupation_status
            in {
                OccupationStatus.VACANT_CONFIRMED_BY_LAWYER,
                OccupationStatus.OWNER_OCCUPIED,
            },
            sources=(_PRODUCT,),
        ),
    ]


def _mortgage_cancel_v0_gates(data: EligibilityInput) -> list[Gate]:
    """Additional §2.3 predicates for the focused Form 12 pilot."""
    return [
        _gate(
            "V0_F12_MORTGAGE_IDENTIFIED",
            data.identified_mortgage_reference,
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_PRODUCT,),
        ),
        _gate(
            "V0_F12_RELEASOR_AUTHORITY_CONFIRMED",
            _is_yes(data.mortgagee_authority_confirmed),
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_act("43"), _act("44")),
        ),
        _gate(
            "V0_F12_DISCHARGE_EVIDENCE_SUFFICIENT",
            _is_yes(data.discharge_evidence_sufficient),
            blocker_kind=BlockerKind.EVIDENCE,
            sources=(_PRODUCT,),
        ),
        _gate(
            "V0_F12_CANCELLATION_ROUTE_CONFIRMED",
            _is_yes(data.cancellation_route_confirmed),
            blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
            sources=(_PRODUCT,),
        ),
        _gate(
            "V0_F12_PARCEL_IS_ORDINARY_NO_DISPUTE",
            data.parcel_kind is ParcelKind.ORDINARY
            and data.dispute_stage
            in {DisputeStage.NO_INDICIA_FOUND, DisputeStage.FINAL_REGISTER_CONFIRMED},
            sources=(_PRODUCT,),
        ),
    ]


def evaluate(data: EligibilityInput) -> EligibilityDecision:
    """Route the matter. Never rejects it; only decides how much may be automated."""
    gates: list[Gate] = []

    litigation = evaluate_litigation_hold(data)
    gates.append(litigation)
    gates.extend(evaluate_statutory_gates(data))

    subtype = get_subtype(data.subtype_id) if data.subtype_id else None

    if subtype is None:
        # Nothing to evaluate against yet. Assessing is honest; V0 is not.
        return EligibilityDecision(
            automation_scope=AutomationScope.ASSESSING,
            gates=tuple(gates),
            exception_state=MatterState.LITIGATION_HOLD if not litigation.satisfied else None,
        )

    gates.extend(_common_v0_gates(data))
    if data.subtype_id == TRANSFER_SALE_SUBTYPE_ID:
        gates.extend(_transfer_v0_gates(data))
    elif data.subtype_id == MORTGAGE_CANCEL_SUBTYPE_ID:
        gates.extend(_mortgage_cancel_v0_gates(data))
    else:
        # Every other subtype may be intaken, checklisted, and organised — it
        # simply has no automated V0 output path (§14.1).
        gates.append(
            _gate(
                "V0_SUBTYPE_IS_A_PILOT_PATH",
                False,
                sources=(_PRODUCT,),
            )
        )

    if not litigation.satisfied:
        scope = AutomationScope.LITIGATION_HOLD
        exception_state: MatterState | None = MatterState.LITIGATION_HOLD
    elif data.dispute_stage in SETTLEMENT_BLOCKING_STAGES:
        scope = AutomationScope.MANUAL_SUPPORTED
        exception_state = MatterState.MANUAL_SUPPORTED
    elif all(g.satisfied for g in gates):
        scope = AutomationScope.V0_AUTOMATED
        exception_state = None
    else:
        scope = AutomationScope.MANUAL_SUPPORTED
        exception_state = MatterState.MANUAL_SUPPORTED

    return EligibilityDecision(
        automation_scope=scope,
        gates=tuple(gates),
        exception_state=exception_state,
    )

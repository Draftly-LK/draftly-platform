"""Deterministic cross-document check catalogue for the RTA rule pack.

Three rules govern everything below (§7.1, §7.3, §6.4):

1. A ``PASS`` means the encoded comparison passed. It is not a title opinion,
   so all but the purely mechanical completeness check require a human
   conclusion before the result carries weight.
2. Absence of evidence is not a negative fact. Where
   ``absence_is_not_evidence`` is set, a missing input yields ``INCONCLUSIVE``
   plus a missing-evidence task — never a ``PASS``.
3. Severity drives the gates, and ``blocker_kind`` decides who (if anyone) may
   override. ``STATUTORY`` cannot be overridden inside Draftly at all, and an
   accepted risk never rewrites a ``FAIL`` to a ``PASS``.

Implements §7.1 (architecture), §7.2 (the check table), §7.3 (severity, gates,
blocker kinds), and §14.5 (the checks V0 cannot launch without).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.content_governance.domain.enums import BlockerKind, IssueSeverity
from src.modules.content_governance.domain.sources import (
    SRC_GAZETTE_2022,
    SRC_LAWYER_PRACTICE,
    SRC_LOCAL_AUTHORITY,
    SRC_PRODUCT_SAFETY,
    SRC_RGD_TRANSACTIONS,
    SRC_RTA_ACT,
    SRC_UDA_APPROVALS,
    SourceCitation,
)

#: Pinned into every ``CrossDocumentCheck`` result so a rule change never
#: retroactively reinterprets a check that already ran (§7.1, §12.2).
CHECKS_VERSION = "1.0.0"


@dataclass(frozen=True)
class CheckDefinition:
    """One deterministic comparison, its failure severity, and its gates."""

    id: str
    version: str
    label_key: str
    #: What is compared, as a translation key — the lawyer-facing wording of
    #: the §7.2 "Comparison" column is content, not code.
    comparison_key: str
    input_fact_type_ids: tuple[str, ...]
    failure_severity: IssueSeverity
    failure_blocker_kind: BlockerKind
    issue_type_id: str
    #: The §7.2 "Safety rule/action" column, as a translation key.
    safety_rule_key: str
    sources: tuple[SourceCitation, ...]
    inconclusive_severity: IssueSeverity = IssueSeverity.WARNING
    requires_human_conclusion: bool = True
    v0_required: bool = False
    #: True when a missing input must yield INCONCLUSIVE + a missing-evidence
    #: task rather than a PASS (§7.2, §6.4 negative facts).
    absence_is_not_evidence: bool = False
    blocks_draft_generation: bool = False
    blocks_approval: bool = True
    order: int = 0


def _check(
    check_id: str,
    *,
    input_fact_type_ids: tuple[str, ...],
    failure_severity: IssueSeverity,
    failure_blocker_kind: BlockerKind,
    issue_type_id: str,
    sources: tuple[SourceCitation, ...],
    order: int,
    inconclusive_severity: IssueSeverity = IssueSeverity.WARNING,
    requires_human_conclusion: bool = True,
    v0_required: bool = False,
    absence_is_not_evidence: bool = False,
    blocks_draft_generation: bool = False,
    blocks_approval: bool = True,
) -> CheckDefinition:
    """Derive the three translation keys from the id so they cannot drift."""
    return CheckDefinition(
        id=check_id,
        version=CHECKS_VERSION,
        label_key=f"rta.check.{check_id}.label",
        comparison_key=f"rta.check.{check_id}.comparison",
        safety_rule_key=f"rta.check.{check_id}.safety_rule",
        input_fact_type_ids=input_fact_type_ids,
        failure_severity=failure_severity,
        failure_blocker_kind=failure_blocker_kind,
        issue_type_id=issue_type_id,
        sources=sources,
        inconclusive_severity=inconclusive_severity,
        requires_human_conclusion=requires_human_conclusion,
        v0_required=v0_required,
        absence_is_not_evidence=absence_is_not_evidence,
        blocks_draft_generation=blocks_draft_generation,
        blocks_approval=blocks_approval,
        order=order,
    )


# ── The §7.2 catalogue, in table order ───────────────────────────────────────

CHECK_DEFINITIONS: tuple[CheckDefinition, ...] = (
    _check(
        "CHK_PARTY_IDENTITY",
        input_fact_type_ids=(
            "rta.party.transferor_name",
            "rta.party.transferor_nic",
            "rta.party.transferor_address",
            "rta.party.transferee_name",
            "rta.party.transferee_nic",
            "rta.party.transferee_address",
            "rta.party.capacity_confirmed",
        ),
        # HIGH_RISK is the default because a name variant may have an alias
        # explanation; an ID-number or role conflict escalates to BLOCKING at
        # run time (§7.2). Either way a different person is never silently
        # normalised into a match.
        failure_severity=IssueSeverity.HIGH_RISK,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.party_identity_conflict",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 44"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 45(2)"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="identity and capacity"),
        ),
        v0_required=True,
        order=1,
    ),
    _check(
        "CHK_OWNER_TRANSFEROR",
        input_fact_type_ids=(
            "rta.title.registered_owner_name",
            "rta.party.transferor_name",
            "rta.party.transferor_nic",
            "rta.party.signing_authority",
            "rta.title.register_search_datetime",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # Closes on transmission/authority evidence plus a lawyer conclusion,
        # not on an override (§7.2, §14.6).
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.owner_transferor_mismatch",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 32-33"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 44"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 45(2)"),
        ),
        v0_required=True,
        blocks_draft_generation=True,
        order=2,
    ),
    _check(
        "CHK_TITLE_REFERENCE",
        input_fact_type_ids=(
            "rta.title.certificate_no",
            "rta.title.class",
            "rta.title.place_of_registration",
            "rta.regime.coverage_confirmed",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.title_reference_mismatch",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 1"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 37"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
        ),
        v0_required=True,
        blocks_draft_generation=True,
        order=3,
    ),
    _check(
        "CHK_PARCEL_ID",
        input_fact_type_ids=(
            "rta.parcel.district",
            "rta.parcel.ds_division",
            "rta.parcel.gn_division",
            "rta.parcel.village",
            "rta.parcel.cadastral_map_number",
            "rta.parcel.block_number",
            "rta.parcel.sheet_number",
            "rta.parcel.parcel_number",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.parcel_identifier_conflict",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 4-5"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 45(2)"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 75"),
        ),
        v0_required=True,
        blocks_draft_generation=True,
        order=4,
    ),
    _check(
        "CHK_EXTENT",
        input_fact_type_ids=(
            "rta.parcel.extent",
            "rta.parcel.extent_subject_to_transaction",
        ),
        # Escalates to BLOCKING when the discrepancy means the form cannot
        # describe the parcel accurately (§7.2); the tolerance itself is a
        # lawyer decision, so the default stops short of blocking.
        failure_severity=IssueSeverity.HIGH_RISK,
        failure_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
        issue_type_id="rta.issue.extent_discrepancy",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 45(2)"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="extent and units"),
        ),
        v0_required=True,
        order=5,
    ),
    _check(
        "CHK_PLAN_DETAILS",
        input_fact_type_ids=(
            "rta.parcel.survey_plan_no",
            "rta.parcel.surveyor_name",
            "rta.parcel.land_name",
            "rta.parcel.lot_no",
            "rta.parcel.boundary_north",
            "rta.parcel.boundary_east",
            "rta.parcel.boundary_south",
            "rta.parcel.boundary_west",
        ),
        failure_severity=IssueSeverity.HIGH_RISK,
        # A boundary defect is a surveyor's or lawyer's conclusion; the check
        # reports the discrepancy and stops there (§7.2).
        failure_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
        issue_type_id="rta.issue.plan_detail_discrepancy",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 4-5"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="survey plan and boundaries"),
        ),
        order=6,
    ),
    _check(
        "CHK_WHOLE_PART",
        input_fact_type_ids=(
            "rta.instrument.disposition_scope",
            "rta.parcel.extent",
            "rta.parcel.extent_subject_to_transaction",
            "rta.parcel.parcel_number",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # s. 47 forbids dealing with part of a registered parcel before
        # subdivision and new registration. No role inside Draftly may waive it.
        failure_blocker_kind=BlockerKind.STATUTORY,
        issue_type_id="rta.issue.part_parcel_without_subdivision",
        sources=(SourceCitation(SRC_RTA_ACT.id, locator="s. 47"),),
        v0_required=True,
        blocks_draft_generation=True,
        order=7,
    ),
    _check(
        "CHK_COOWNERSHIP",
        input_fact_type_ids=(
            "rta.party.coowners_present",
            "rta.party.creates_coownership",
            "rta.instrument.disposition_scope",
            "rta.title.class",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # s. 48 makes an instrument conferring co-ownership invalid except as
        # the Act provides; the lawyer chooses a valid structure instead.
        failure_blocker_kind=BlockerKind.STATUTORY,
        issue_type_id="rta.issue.prohibited_coownership_effect",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 48"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 14(d)"),
        ),
        v0_required=True,
        blocks_draft_generation=True,
        order=8,
    ),
    _check(
        "CHK_INSTRUMENT_CONDITIONS",
        input_fact_type_ids=(
            "rta.instrument.exact_subtype",
            "rta.interest.life_interest_present",
        ),
        # No fact type carries the proposed special-condition text; the check
        # runs against the subtype and life-interest facts until one exists.
        failure_severity=IssueSeverity.BLOCKING,
        # The controlling proposition is current registry practice awaiting
        # template-counsel confirmation, so an authorised override is possible
        # once that rule is validated (§7.2, §13.2.2).
        failure_blocker_kind=BlockerKind.OFFICE_POLICY,
        issue_type_id="rta.issue.instrument_condition_not_permitted",
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 39"),
        ),
        blocks_draft_generation=True,
        order=9,
    ),
    _check(
        "CHK_DEED_INSTRUMENT_REF",
        input_fact_type_ids=(
            "rta.instrument.attestation_date",
            "rta.instrument.notary_name",
            "rta.instrument.notary_code",
            "rta.title.certificate_no",
        ),
        # Gap: no fact type exists yet for the prior instrument number or the
        # day-book entry, so those two comparisons stay unimplemented.
        failure_severity=IssueSeverity.HIGH_RISK,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.prior_instrument_reference_mismatch",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 43"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="prior instrument chain"),
        ),
        order=10,
    ),
    _check(
        "CHK_MORTGAGE_STATUS",
        input_fact_type_ids=(
            "rta.interest.mortgage_status",
            "rta.interest.mortgage_reference",
            "rta.interest.mortgagee_name",
            "rta.interest.mortgagee_authority_confirmed",
            "rta.interest.discharge_evidence_kind",
            "rta.title.register_search_datetime",
        ),
        failure_severity=IssueSeverity.HIGH_RISK,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.mortgage_unresolved",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 32-33"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 38"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="encumbrance discharge"),
        ),
        v0_required=True,
        # A repaid loan, a bank letter, or a silent file is not a cancelled
        # registered interest; only a current register entry settles this.
        absence_is_not_evidence=True,
        order=11,
    ),
    _check(
        "CHK_LEASE_STATUS",
        input_fact_type_ids=(
            "rta.interest.lease_status",
            "rta.interest.occupation_status",
            "rta.title.register_search_datetime",
        ),
        failure_severity=IssueSeverity.HIGH_RISK,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.lease_or_occupation_unresolved",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 32-33"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="lease and occupation"),
        ),
        # §7.2 downgrades an unclear status to a warning rather than reading it
        # as "no lease".
        inconclusive_severity=IssueSeverity.WARNING,
        v0_required=True,
        absence_is_not_evidence=True,
        order=12,
    ),
    _check(
        "CHK_CAVEAT_LITIGATION",
        input_fact_type_ids=(
            "rta.interest.caveat_or_notice_status",
            "rta.process.dispute_stage",
            "rta.process.court_proceeding_reference",
            "rta.title.register_search_datetime",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # Manual/litigation support continues; only automated V0 output stops.
        # Draftly never decides the merits of a caveat or an action.
        failure_blocker_kind=BlockerKind.V0_SCOPE,
        issue_type_id="rta.issue.caveat_or_litigation_active",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 29"),
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 58-62"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="litigation hold"),
        ),
        v0_required=True,
        absence_is_not_evidence=True,
        blocks_draft_generation=True,
        order=13,
    ),
    _check(
        "CHK_PROBATE_AUTHORITY",
        input_fact_type_ids=(
            "rta.process.transmission_completed",
            "rta.process.probate_path",
            "rta.party.signing_authority",
            "rta.title.registered_owner_name",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.transmission_authority_unresolved",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 54"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 55"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="deceased owner"),
        ),
        absence_is_not_evidence=True,
        blocks_draft_generation=True,
        order=14,
    ),
    _check(
        "CHK_COMPANY_AUTHORITY",
        input_fact_type_ids=(
            "rta.org.company_name",
            "rta.org.company_number",
            "rta.org.resolution_date",
            "rta.party.signing_authority",
            "rta.party.all_natural_persons",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.company_authority_unresolved",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 43"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 44"),
            SourceCitation(SRC_LAWYER_PRACTICE.id, locator="corporate signing authority"),
        ),
        absence_is_not_evidence=True,
        blocks_draft_generation=True,
        order=15,
    ),
    _check(
        "CHK_ASSESSMENT_NAME",
        input_fact_type_ids=(
            "rta.local.assessment_register_name",
            "rta.local.local_authority_id",
            "rta.title.registered_owner_name",
        ),
        failure_severity=IssueSeverity.WARNING,
        failure_blocker_kind=BlockerKind.OFFICE_POLICY,
        issue_type_id="rta.issue.assessment_name_mismatch",
        sources=(
            SourceCitation(SRC_LOCAL_AUTHORITY.id, locator="assessment register"),
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 32-33"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="council records are not title"),
        ),
        # A council assessment record is contextual evidence, never title
        # (§1.2, §Executive 9), so it must not gate approval and must never be
        # read as showing the seller lacks title.
        blocks_approval=False,
        order=16,
    ),
    _check(
        "CHK_RATES_CURRENCY",
        input_fact_type_ids=(
            "rta.local.rates_paid_to",
            "rta.local.local_authority_id",
            "rta.parcel.assessment_number",
        ),
        # Escalates to HIGH_RISK only under a named office's configured policy;
        # the default never draws a title conclusion from rates (§7.2).
        failure_severity=IssueSeverity.WARNING,
        failure_blocker_kind=BlockerKind.OFFICE_POLICY,
        issue_type_id="rta.issue.rates_not_current",
        sources=(SourceCitation(SRC_LOCAL_AUTHORITY.id, locator="rates and assessment period"),),
        blocks_approval=False,
        order=17,
    ),
    _check(
        "CHK_BUILDING_COMPLIANCE",
        input_fact_type_ids=(
            "rta.parcel.building_present",
            "rta.parcel.assessment_number",
            "rta.local.local_authority_id",
        ),
        # HIGH_RISK only when the office rule set says the discrepancy is
        # material; Draftly does not certify construction legality either way.
        failure_severity=IssueSeverity.WARNING,
        failure_blocker_kind=BlockerKind.OFFICE_POLICY,
        issue_type_id="rta.issue.building_compliance_discrepancy",
        sources=(
            SourceCitation(SRC_UDA_APPROVALS.id, locator="approval process"),
            SourceCitation(SRC_LOCAL_AUTHORITY.id, locator="certificate of conformity"),
        ),
        absence_is_not_evidence=True,
        blocks_approval=False,
        order=18,
    ),
    _check(
        "CHK_CONDO_PARENT_UNIT",
        input_fact_type_ids=(
            "rta.parcel.kind",
            "rta.title.certificate_no",
            "rta.parcel.parcel_number",
            "rta.parcel.extent",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # Strata registration is a deferred workflow; the manual path stays
        # open but no automated output is produced (§14.7).
        failure_blocker_kind=BlockerKind.V0_SCOPE,
        issue_type_id="rta.issue.condominium_unit_mismatch",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="ss. 50-52"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="V0 scope"),
        ),
        blocks_draft_generation=True,
        order=19,
    ),
    _check(
        "CHK_SUBDIVISION_MAP",
        input_fact_type_ids=(
            "rta.parcel.cadastral_map_number",
            "rta.parcel.survey_plan_no",
            "rta.parcel.parcel_number",
            "rta.parcel.extent_subject_to_transaction",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # The s. 36 amendment of the cadastral map has to actually happen; no
        # Draftly role can substitute for it.
        failure_blocker_kind=BlockerKind.STATUTORY,
        issue_type_id="rta.issue.subdivision_process_incomplete",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 36"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 47"),
        ),
        absence_is_not_evidence=True,
        blocks_draft_generation=True,
        order=20,
    ),
    _check(
        "CHK_RESTRUCTURE_PRIOR_AGREEMENTS",
        input_fact_type_ids=("rta.instrument.exact_subtype",),
        # Gap: no fact type records the status of a prior agreement to sell,
        # so the comparison currently runs on the subtype plus evidence review.
        failure_severity=IssueSeverity.BLOCKING,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.prior_agreement_active",
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 36"),
        ),
        # Cancellation is proved, never inferred from an absent document.
        absence_is_not_evidence=True,
        blocks_draft_generation=True,
        order=21,
    ),
    _check(
        "CHK_POA_SCOPE",
        input_fact_type_ids=(
            "rta.party.signing_authority",
            "rta.party.capacity_confirmed",
            "rta.party.all_natural_persons",
        ),
        failure_severity=IssueSeverity.BLOCKING,
        # §7.2 marks attorney-executed matters a V0 exclusion outright.
        failure_blocker_kind=BlockerKind.V0_SCOPE,
        issue_type_id="rta.issue.power_of_attorney_scope_unresolved",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 44"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="V0 scope"),
        ),
        # No revocation on file is not proof that the power is still current.
        absence_is_not_evidence=True,
        blocks_draft_generation=True,
        order=22,
    ),
    _check(
        "CHK_DOCUMENT_CURRENCY",
        input_fact_type_ids=(
            "rta.title.register_search_datetime",
            "rta.local.rates_paid_to",
            "rta.instrument.attestation_date",
        ),
        # §7.2 allows WARNING or HIGH_RISK; the default is the stricter one
        # because §14.5 makes currency a launch-blocking V0 check and a stale
        # register search silently invalidates every encumbrance conclusion.
        failure_severity=IssueSeverity.HIGH_RISK,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.document_not_current",
        sources=(
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_LOCAL_AUTHORITY.id, locator="certificate validity period"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="source re-verification"),
        ),
        v0_required=True,
        # An undated document is UNKNOWN currency, not CURRENT (§5.4).
        absence_is_not_evidence=True,
        order=23,
    ),
    _check(
        "CHK_FORM_REQUIRED_FIELDS",
        # Empty on purpose: the input set is the selected template's required
        # field list, resolved per matter at run time (§9.3), not a fixed tuple.
        input_fact_type_ids=(),
        failure_severity=IssueSeverity.BLOCKING,
        failure_blocker_kind=BlockerKind.EVIDENCE,
        issue_type_id="rta.issue.form_required_field_unresolved",
        sources=(
            SourceCitation(SRC_GAZETTE_2022.id, locator="regulation 15(1)"),
            SourceCitation(SRC_RTA_ACT.id, locator="s. 45(2)"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="no guessed field values"),
        ),
        # Completeness against the template's field list is mechanical; the
        # human decisions already happened when each fact was confirmed (§9.3).
        requires_human_conclusion=False,
        v0_required=True,
        absence_is_not_evidence=True,
        # The draft is still produced — it renders [[UNRESOLVED: …]] tokens and
        # stays out of review-ready/export instead (§9.4).
        blocks_draft_generation=False,
        order=24,
    ),
    _check(
        "CHK_ATTESTATION_DEADLINE",
        input_fact_type_ids=("rta.instrument.attestation_date",),
        failure_severity=IssueSeverity.HIGH_RISK,
        # The working-day calendar including Sri Lankan public holidays is not
        # yet verified, so the responsible lawyer owns the conclusion (§7.2).
        failure_blocker_kind=BlockerKind.PROFESSIONAL_JUDGMENT,
        issue_type_id="rta.issue.attestation_deadline_at_risk",
        sources=(
            SourceCitation(SRC_RTA_ACT.id, locator="s. 45(1)"),
            SourceCitation(SRC_RGD_TRANSACTIONS.id, locator="Transactions page"),
            SourceCitation(SRC_PRODUCT_SAFETY.id, locator="holiday calendar unverified"),
        ),
        v0_required=True,
        order=25,
    ),
)


# ── Lookups ──────────────────────────────────────────────────────────────────

_BY_ID: dict[str, CheckDefinition] = {c.id: c for c in CHECK_DEFINITIONS}

_BY_FACT_TYPE: dict[str, tuple[CheckDefinition, ...]] = {}
for _definition in CHECK_DEFINITIONS:
    for _fact_type_id in _definition.input_fact_type_ids:
        _BY_FACT_TYPE[_fact_type_id] = (*_BY_FACT_TYPE.get(_fact_type_id, ()), _definition)


def get_check(check_id: str) -> CheckDefinition | None:
    return _BY_ID.get(check_id)


def require_check(check_id: str) -> CheckDefinition:
    definition = _BY_ID.get(check_id)
    if definition is None:
        raise KeyError(f"Unknown RTA check '{check_id}'.")
    return definition


def v0_check_ids() -> tuple[str, ...]:
    """The §14.5 set — V0 cannot launch without every one of these."""
    return tuple(c.id for c in CHECK_DEFINITIONS if c.v0_required)


def checks_consuming(fact_type_id: str) -> tuple[CheckDefinition, ...]:
    """Which checks a change to this fact invalidates, so re-runs stay scoped."""
    return _BY_FACT_TYPE.get(fact_type_id, ())

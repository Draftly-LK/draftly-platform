"""The §9.3 fact-to-field rules, the §9.4 preflight, and §10.7 staleness.

All fixture content is synthetic. The acceptance criteria that live here:

- an unconfirmed critical fact renders the unresolved token and never a value,
  at any candidate confidence including 1.00;
- a populated critical field always carries fact id, fact version, and evidence,
  and an unevidenced confirmed critical fact is refused rather than rendered;
- two conflicting facts leave the field unresolved with both candidates;
- a negative proposition is not populated without a current search;
- attestation is never pre-certified;
- `registration_ready` is false while a required field is unresolved, and false
  again when nothing at all is unresolved, because no template in this
  repository is a lawyer-approved production rendering.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    FORM_TEMPLATES,
    RULE_PACK_VERSION,
    FormFieldMapping,
    GeneratedFormState,
    SubtypeDecisionStatus,
    UnresolvedReason,
    require_subtype,
    require_template,
)
from src.modules.draft.domain.errors import (
    CriticalFieldEvidenceMissingError,
    FormGenerationBlockedError,
    SubtypeNotConfirmedError,
    TemplateNotAvailableForSubtypeError,
)
from src.modules.draft.domain.models import (
    FactCandidate,
    GeneratedForm,
    GeneratedFormField,
    StaleReason,
    unresolved_token,
)
from src.modules.draft.domain.policies import (
    PreflightCode,
    PreflightGate,
    PreflightResult,
    derive_state,
    detect_staleness,
    draft_artifact_hash,
    guard_generation,
    guard_populated_critical_field,
    is_ai_suggested,
    is_pre_certification,
    preflight,
    render_exact_copy,
    resolve_field,
    resolve_template,
    select_template,
    source_reverification_required,
    stale_bindings,
    stale_state,
)
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary
from tests.factories.constants import NOW

from .fakes import (
    CONFIRMED_TRANSFER,
    FORM_08_TEMPLATE_ID,
    MATTER_ID,
    TIRE_31_TEMPLATE_ID,
    TRANSFER_SUBTYPE_ID,
    USER_ID,
    candidate,
    fact_tier,
)

FORM_08 = require_template(FORM_08_TEMPLATE_ID)
_MAPPINGS = {mapping.field_id: mapping for mapping in FORM_08.field_mappings}


def mapping(field_id: str) -> FormFieldMapping:
    return _MAPPINGS[field_id]


def confirmed(
    fact_type_id: str,
    value: object,
    *,
    fact_id: str = "fact_synthetic",
    version: int = 1,
    evidence: tuple[str, ...] = ("ev_synthetic",),
) -> ConfirmedFactValue:
    return ConfirmedFactValue(
        fact_id=fact_id,
        fact_type_id=fact_type_id,
        value=value,
        version=version,
        evidence_reference_ids=evidence,
    )


# ── Rule 1: never invent a value ─────────────────────────────────────────────


def test_an_unconfirmed_critical_fact_renders_the_token_and_never_a_value() -> None:
    resolution = resolve_field(mapping("transferee_nic"), confirmed=None)
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.NO_FACT

    form_field = _field(mapping("transferee_nic"), resolution.unresolved_reason)
    assert form_field.display_value() == "[[UNRESOLVED: transferee_nic]]"


def test_a_critical_field_refuses_a_candidate_at_full_confidence() -> None:
    """§6.4 — a critical fact has no confidence bypass, including at 1.00."""
    resolution = resolve_field(
        mapping("transferor_nic"),
        confirmed=None,
        candidates=(candidate("rta.party.transferor_nic", "SYNTHETIC-NIC-Z", confidence=1.0),),
    )
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.FACT_NOT_CONFIRMED
    assert resolution.ai_suggested is False


def test_an_unresolved_field_never_renders_blank_space() -> None:
    for mapping_ in FORM_08.field_mappings:
        resolution = resolve_field(mapping_, confirmed=None)
        form_field = _field(mapping_, resolution.unresolved_reason)
        assert form_field.display_value() == unresolved_token(mapping_.field_id)
        assert form_field.display_value().strip() == form_field.display_value()


# ── Rule 2: a non-critical field may prefill ─────────────────────────────────


def test_a_high_confidence_noncritical_candidate_prefills_as_ai_suggested() -> None:
    resolution = resolve_field(
        mapping("notary_name"),
        confirmed=None,
        candidates=(candidate("rta.instrument.notary_name", "Synthetic Notary Three"),),
    )
    assert resolution.rendered_value == "Synthetic Notary Three"
    assert resolution.ai_suggested is True
    assert resolution.fact_id == "fact_candidate"


def test_a_low_confidence_noncritical_candidate_does_not_prefill() -> None:
    resolution = resolve_field(
        mapping("notary_name"),
        confirmed=None,
        candidates=(candidate("rta.instrument.notary_name", "Synthetic Notary", confidence=0.5),),
    )
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.FACT_NOT_CONFIRMED


def test_dirty_ocr_blocks_a_noncritical_prefill_however_high_the_score() -> None:
    resolution = resolve_field(
        mapping("notary_code"),
        confirmed=None,
        candidates=(
            candidate("rta.instrument.notary_code", "SYN-1", confidence=1.0, clean_ocr=False),
        ),
    )
    assert resolution.rendered_value is None


def test_the_highest_confidence_candidate_wins_deterministically() -> None:
    low = candidate("rta.instrument.notary_name", "Lower", fact_id="fact_b", confidence=0.96)
    high = candidate("rta.instrument.notary_name", "Higher", fact_id="fact_a", confidence=0.99)
    assert (
        resolve_field(mapping("notary_name"), confirmed=None, candidates=(low, high)).rendered_value
        == "Higher"
    )
    assert (
        resolve_field(mapping("notary_name"), confirmed=None, candidates=(high, low)).rendered_value
        == "Higher"
    )


# ── Rule 3: a populated critical field carries its whole chain ───────────────


def test_every_populated_critical_field_carries_fact_id_version_and_evidence() -> None:
    resolutions = resolve_template(FORM_08, facts=fact_tier(CONFIRMED_TRANSFER))
    populated_critical = [r for r in resolutions if r.mapping.critical and r.rendered_value]
    assert populated_critical
    for resolution in populated_critical:
        assert resolution.fact_id is not None
        assert resolution.fact_version is not None
        assert resolution.evidence_reference_ids


def test_an_unevidenced_confirmed_critical_fact_is_refused_not_rendered() -> None:
    with pytest.raises(CriticalFieldEvidenceMissingError):
        resolve_field(
            mapping("transferor_name"),
            confirmed=confirmed("rta.party.transferor_name", "Synthetic Seller One", evidence=()),
        )


def test_the_row_guard_refuses_a_critical_value_with_no_evidence() -> None:
    form_field = _field(mapping("transferor_name"), None)
    form_field.rendered_value = "Synthetic Seller One"
    form_field.fact_id = "fact_1"
    form_field.fact_version = 1
    with pytest.raises(CriticalFieldEvidenceMissingError):
        guard_populated_critical_field(form_field)


def test_a_noncritical_field_may_be_populated_without_evidence() -> None:
    """Only §9.3's critical row demands the evidence chain."""
    form_field = _field(mapping("village"), None)
    form_field.rendered_value = "Synthetic Village"
    guard_populated_critical_field(form_field)


# ── Rule 4: conflicts ────────────────────────────────────────────────────────


def test_two_conflicting_facts_leave_the_field_unresolved_with_both_candidates() -> None:
    left = candidate("rta.party.transferor_name", "Synthetic Seller One", fact_id="fact_l")
    right = candidate("rta.party.transferor_name", "Synthetic Seller Won", fact_id="fact_r")
    resolution = resolve_field(
        mapping("transferor_name"),
        confirmed=confirmed("rta.party.transferor_name", "Synthetic Seller One"),
        candidates=(left, right),
        conflicted=True,
    )
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.FACT_CONFLICTED
    assert resolution.conflicting_candidates == (left, right)


def test_a_conflict_beats_a_confirmed_value_rather_than_being_resolved_for_the_lawyer() -> None:
    resolution = resolve_field(
        mapping("extent"),
        confirmed=confirmed("rta.parcel.extent", "0.0500 ha"),
        conflicted=True,
    )
    assert resolution.rendered_value is None


# ── Rule 5: negative propositions ────────────────────────────────────────────


def test_a_negative_proposition_is_not_populated_without_a_current_search() -> None:
    negative = FormFieldMapping(
        field_id="mortgage_status",
        label_key="rta.form.synthetic.field.mortgage_status.label",
        fact_type_id="rta.interest.mortgage_status",
        required=True,
        critical=True,
        human_confirmation_required=True,
        order=1,
        allowed_transformation_ids=("EXACT_COPY",),
    )
    resolution = resolve_field(
        negative,
        confirmed=confirmed("rta.interest.mortgage_status", "NOT_FOUND_IN_CURRENT_SEARCH"),
        has_current_search_evidence=False,
    )
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.NO_FACT

    with_search = resolve_field(
        negative,
        confirmed=confirmed("rta.interest.mortgage_status", "NOT_FOUND_IN_CURRENT_SEARCH"),
        has_current_search_evidence=True,
    )
    assert with_search.rendered_value == "NOT_FOUND_IN_CURRENT_SEARCH"


def test_a_candidate_negative_is_refused_at_any_confidence_without_a_search() -> None:
    """A model's reading of silence is not a negative finding (§6.4)."""
    negative = FormFieldMapping(
        field_id="servitude_present",
        label_key="rta.form.synthetic.field.servitude_present.label",
        fact_type_id="rta.interest.caveat_or_notice_status",
        required=False,
        critical=False,
        human_confirmation_required=True,
        order=1,
        allowed_transformation_ids=("EXACT_COPY",),
    )
    resolution = resolve_field(
        negative,
        confirmed=None,
        candidates=(
            candidate("rta.interest.caveat_or_notice_status", "NOT_FOUND_IN_CURRENT_SEARCH"),
        ),
        has_current_search_evidence=False,
    )
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.NO_FACT


def test_a_boolean_conclusion_has_no_prescribed_rendering() -> None:
    assert render_exact_copy(True) is None
    assert render_exact_copy(False) is None
    assert render_exact_copy("  spaced  ") == "spaced"
    assert render_exact_copy("") is None
    assert render_exact_copy(7) == "7"


# ── Rule 6: never pre-certified ──────────────────────────────────────────────


def test_attestation_is_never_pre_certified() -> None:
    assert is_pre_certification(mapping("attestation_date")) is True
    resolution = resolve_field(
        mapping("attestation_date"),
        confirmed=confirmed("rta.instrument.attestation_date", "2026-08-14"),
    )
    assert resolution.rendered_value is None
    assert resolution.unresolved_reason is UnresolvedReason.NO_FACT


def test_naming_the_notary_is_ordinary_drafting_not_pre_certification() -> None:
    """The attestation *act* is withheld; the notary's identity is a particular."""
    assert is_pre_certification(mapping("notary_name")) is False
    assert is_pre_certification(mapping("notary_code")) is False


# ── Template selection (§9.1) ────────────────────────────────────────────────


def test_a_transfer_selects_form_8_and_never_its_companion_by_default() -> None:
    subtype = require_subtype(TRANSFER_SUBTYPE_ID)
    assert select_template(subtype, None) == FORM_08_TEMPLATE_ID
    assert select_template(subtype, TIRE_31_TEMPLATE_ID) == TIRE_31_TEMPLATE_ID


def test_a_template_the_subtype_does_not_select_is_refused() -> None:
    subtype = require_subtype(TRANSFER_SUBTYPE_ID)
    with pytest.raises(TemplateNotAvailableForSubtypeError):
        select_template(subtype, "rta.reg.2022.form.12")


def test_a_subtype_with_no_registered_template_cannot_be_drafted() -> None:
    with pytest.raises(TemplateNotAvailableForSubtypeError):
        select_template(require_subtype("lk.rta.instrument.other_declared_instrument"), None)


# ── Generation gates ─────────────────────────────────────────────────────────


def test_a_provisional_subtype_cannot_generate() -> None:
    with pytest.raises(SubtypeNotConfirmedError):
        guard_generation(
            subtype_id=TRANSFER_SUBTYPE_ID,
            subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL,
            issue_gates=IssueGateSummary(),
        )


def test_a_blocking_issue_stops_generation_and_a_high_risk_one_does_not() -> None:
    with pytest.raises(FormGenerationBlockedError):
        guard_generation(
            subtype_id=TRANSFER_SUBTYPE_ID,
            subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
            issue_gates=IssueGateSummary(
                blocks_draft_generation=True, open_blocking_issue_ids=("iss_1",)
            ),
        )
    assert (
        guard_generation(
            subtype_id=TRANSFER_SUBTYPE_ID,
            subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
            issue_gates=IssueGateSummary(blocks_approval=True),
        )
        == TRANSFER_SUBTYPE_ID
    )


# ── Preflight (§9.4, §14.6) ──────────────────────────────────────────────────


def _form(state: GeneratedFormState = GeneratedFormState.GENERATED_DRAFT) -> GeneratedForm:
    return GeneratedForm(
        id="frm_synthetic",
        user_id=USER_ID,
        matter_id=MATTER_ID,
        template_id=FORM_08.id,
        template_version=FORM_08.version,
        form_version=1,
        state=state,
        subtype_id=TRANSFER_SUBTYPE_ID,
        rule_pack_version=RULE_PACK_VERSION,
        created_by=USER_ID,
        created_at=NOW,
        updated_at=NOW,
    )


def _field(mapping_: FormFieldMapping, reason: UnresolvedReason | None) -> GeneratedFormField:
    return GeneratedFormField(
        id=f"fld_{mapping_.field_id}",
        user_id=USER_ID,
        matter_id=MATTER_ID,
        generated_form_id="frm_synthetic",
        field_id=mapping_.field_id,
        critical=mapping_.critical,
        required=mapping_.required,
        order=mapping_.order,
        unresolved_reason=reason,
    )


def _fields(facts: FactTierSummary) -> list[GeneratedFormField]:
    rows: list[GeneratedFormField] = []
    for resolution in resolve_template(FORM_08, facts=facts):
        row = _field(resolution.mapping, resolution.unresolved_reason)
        row.rendered_value = resolution.rendered_value
        row.fact_id = resolution.fact_id
        row.fact_version = resolution.fact_version
        row.evidence_reference_ids = resolution.evidence_reference_ids
        row.transformation_id = resolution.transformation_id
        rows.append(row)
    return rows


def _preflight(
    facts: FactTierSummary,
    *,
    form: GeneratedForm | None = None,
    gates: IssueGateSummary | None = None,
    requirements: tuple[str, ...] = (),
) -> PreflightResult:
    the_form = form or _form()
    return preflight(
        form=the_form,
        fields=_fields(facts),
        template=FORM_08,
        facts=facts,
        issue_gates=gates or IssueGateSummary(),
        blocking_requirement_ids=requirements,
        evaluated_at=NOW,
    )


def test_an_unresolved_required_field_makes_registration_ready_false() -> None:
    without_nic = {k: v for k, v in CONFIRMED_TRANSFER.items() if k != "rta.party.transferee_nic"}
    result = _preflight(fact_tier(without_nic))
    assert result.registration_ready is False
    assert result.review_ready is False
    codes = {(item.code, item.subject_id) for item in result.blocking}
    assert (PreflightCode.UNRESOLVED_REQUIRED_FIELD, "transferee_nic") in codes


def test_registration_ready_is_false_even_when_nothing_is_unresolved() -> None:
    """§9.5 — no template here is a lawyer-approved production rendering."""
    result = _preflight(fact_tier(CONFIRMED_TRANSFER))
    assert result.review_ready is True
    assert result.approval_ready is True
    assert result.registration_ready is False
    assert result.template_registration_ready_capable is False
    codes = {item.code for item in result.blocking}
    assert PreflightCode.TEMPLATE_NOT_VALIDATED in codes
    assert PreflightCode.SOURCE_REVERIFICATION_REQUIRED in codes


def test_no_template_in_this_repository_can_back_a_registration_ready_export() -> None:
    for template in FORM_TEMPLATES:
        assert template.registration_ready_capable is False
        assert source_reverification_required(template) is True


def test_preflight_consults_all_four_sources() -> None:
    result = _preflight(
        fact_tier(CONFIRMED_TRANSFER, unconfirmed_critical=("rta.regime.coverage_confirmed",)),
        gates=IssueGateSummary(
            blocks_draft_generation=True,
            blocks_approval=True,
            blocks_registration_ready_export=True,
            open_blocking_issue_ids=("iss_1",),
            open_statutory_blocker_ids=("iss_1",),
        ),
        requirements=("REQ_SYNTHETIC",),
    )
    codes = {(item.code, item.subject_id) for item in result.blocking}
    assert (PreflightCode.CRITICAL_FACT_UNCONFIRMED, "rta.regime.coverage_confirmed") in codes
    assert (PreflightCode.OPEN_BLOCKING_ISSUE, "iss_1") in codes
    assert (PreflightCode.OPEN_STATUTORY_BLOCKER, "iss_1") in codes
    assert (PreflightCode.CHECKLIST_REQUIREMENT_BLOCKING, "REQ_SYNTHETIC") in codes
    assert result.review_ready is False


def test_a_clean_form_is_still_not_approval_ready_while_a_critical_fact_is_unconfirmed() -> None:
    """§14.6 — the fact tier is a stop condition in its own right."""
    result = _preflight(
        fact_tier(CONFIRMED_TRANSFER, unconfirmed_critical=("rta.regime.coverage_confirmed",))
    )
    assert result.review_ready is True
    assert result.approval_ready is False


def test_a_checklist_blocker_stops_approval_but_not_the_working_draft() -> None:
    result = _preflight(fact_tier(CONFIRMED_TRANSFER), requirements=("REQ_SYNTHETIC",))
    assert result.review_ready is True
    assert result.approval_ready is False
    item = next(
        i for i in result.blocking if i.code is PreflightCode.CHECKLIST_REQUIREMENT_BLOCKING
    )
    assert item.gate is PreflightGate.APPROVAL


def test_an_unacknowledged_warning_only_stops_registration_ready_export() -> None:
    result = _preflight(
        fact_tier(CONFIRMED_TRANSFER),
        gates=IssueGateSummary(blocks_registration_ready_export=True),
    )
    assert result.approval_ready is True
    assert PreflightCode.UNACKNOWLEDGED_WARNING_ISSUE in {i.code for i in result.blocking}


def test_a_conflicted_field_is_reported_as_a_conflict_not_as_a_gap() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER, conflicted=("rta.party.transferor_name",))
    result = _preflight(facts)
    codes = {(item.code, item.subject_id) for item in result.blocking}
    assert (PreflightCode.FIELD_CONFLICTED, "transferor_name") in codes
    assert (PreflightCode.UNRESOLVED_REQUIRED_FIELD, "transferor_name") not in codes


def test_a_confirmed_value_is_never_badged_as_an_ai_suggestion() -> None:
    """§9.3 — the badge marks a prefill, not "nobody has looked at this yet"."""
    facts = fact_tier(CONFIRMED_TRANSFER)
    row = next(f for f in _fields(facts) if f.field_id == "notary_name")
    assert row.awaiting_confirmation is True
    assert is_ai_suggested(row, mapping("notary_name"), facts) is False

    prefilled = row
    prefilled.fact_id = "fact_candidate"
    assert is_ai_suggested(prefilled, mapping("notary_name"), facts) is True


def test_a_critical_field_is_never_an_ai_suggestion() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    row = next(f for f in _fields(facts) if f.field_id == "transferor_nic")
    row.fact_id = "fact_candidate"
    assert is_ai_suggested(row, mapping("transferor_nic"), facts) is False


def test_an_optional_unresolved_field_is_a_warning_not_a_blocker() -> None:
    result = _preflight(fact_tier(CONFIRMED_TRANSFER))
    warnings = {(item.code, item.subject_id) for item in result.warnings}
    assert (PreflightCode.UNRESOLVED_OPTIONAL_FIELD, "village") in warnings
    assert (PreflightCode.UNRESOLVED_OPTIONAL_FIELD, "attestation_date") in warnings
    assert all(item.blocking is False for item in result.warnings)


def test_the_report_is_deterministic() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    first, second = _preflight(facts), _preflight(facts)
    assert [(i.code, i.subject_id) for i in first.items] == [
        (i.code, i.subject_id) for i in second.items
    ]
    assert [(i.code, i.subject_id) for i in first.items] == sorted(
        [(i.code, i.subject_id) for i in first.items],
        key=lambda pair: (list(PreflightCode).index(pair[0]), pair[1]),
    )


def test_derive_state_reads_the_review_ready_gate_only() -> None:
    assert (
        derive_state(_preflight(fact_tier(CONFIRMED_TRANSFER))) is GeneratedFormState.REVIEW_READY
    )
    without_nic = {k: v for k, v in CONFIRMED_TRANSFER.items() if k != "rta.party.transferee_nic"}
    assert derive_state(_preflight(fact_tier(without_nic))) is GeneratedFormState.UNRESOLVED


# ── Staleness (§9.5, §10.5, §10.7) ───────────────────────────────────────────


def test_a_corrected_fact_makes_the_form_stale() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    fields = _fields(facts)
    corrected = fact_tier(
        {**CONFIRMED_TRANSFER, "rta.party.transferee_nic": "SYNTHETIC-NIC-C"},
        version=2,
        fact_id_suffix="b",
    )
    reason = detect_staleness(
        form=_form(),
        fields=fields,
        template=FORM_08,
        facts=corrected,
        rule_pack_version=RULE_PACK_VERSION,
    )
    assert reason is StaleReason.FACT_SUPERSEDED
    assert stale_bindings(fields, FORM_08, corrected)


def test_an_unchanged_record_is_not_stale() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    assert (
        detect_staleness(
            form=_form(),
            fields=_fields(facts),
            template=FORM_08,
            facts=facts,
            rule_pack_version=RULE_PACK_VERSION,
        )
        is None
    )


def test_a_declared_reason_never_overrides_an_observed_one() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    stale_form = _form()
    stale_form.template_version = "0.0.1"
    reason = detect_staleness(
        form=stale_form,
        fields=_fields(facts),
        template=FORM_08,
        facts=facts,
        rule_pack_version=RULE_PACK_VERSION,
        declared=StaleReason.CHECKLIST_RECOMPILED,
    )
    assert reason is StaleReason.TEMPLATE_VERSION_CHANGED


def test_a_declared_checklist_recompile_is_honoured_when_nothing_else_moved() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    assert (
        detect_staleness(
            form=_form(),
            fields=_fields(facts),
            template=FORM_08,
            facts=facts,
            rule_pack_version=RULE_PACK_VERSION,
            declared=StaleReason.CHECKLIST_RECOMPILED,
        )
        is StaleReason.CHECKLIST_RECOMPILED
    )


def test_an_approved_form_goes_stale_after_approval_whatever_the_reason() -> None:
    approved = _form(GeneratedFormState.APPROVED)
    approved.approved_artifact_hash = "sha256:synthetic"
    for reason in StaleReason:
        assert stale_state(approved, reason) is GeneratedFormState.STALE_AFTER_APPROVAL


def test_an_unapproved_form_lands_by_reason() -> None:
    draft = _form()
    assert (
        stale_state(draft, StaleReason.TEMPLATE_VERSION_CHANGED)
        is GeneratedFormState.STALE_TEMPLATE
    )
    assert stale_state(draft, StaleReason.FACT_SUPERSEDED) is GeneratedFormState.UNRESOLVED


def test_an_ai_prefill_is_not_stale_merely_because_nobody_confirmed_it() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)
    fields = _fields(facts)
    prefilled = next(f for f in fields if f.field_id == "village")
    prefilled.rendered_value = "Synthetic Village"
    prefilled.unresolved_reason = None
    prefilled.fact_id = "fact_candidate"
    prefilled.fact_version = 1
    assert not [row for row, _ in stale_bindings(fields, FORM_08, facts) if row is prefilled]


# ── Artifact hash (§9.6) ─────────────────────────────────────────────────────


def test_the_artifact_hash_pins_the_bindings_not_the_moment() -> None:
    facts = fact_tier(CONFIRMED_TRANSFER)

    def digest(fields: list[GeneratedFormField]) -> str:
        return draft_artifact_hash(
            template_id=FORM_08.id,
            template_version=FORM_08.version,
            rule_pack_version=RULE_PACK_VERSION,
            subtype_id=TRANSFER_SUBTYPE_ID,
            fields=fields,
        )

    assert digest(_fields(facts)) == digest(_fields(facts))
    changed = _fields(facts)
    changed[0].rendered_value = "Different Synthetic Value"
    assert digest(changed) != digest(_fields(facts))


def test_a_field_review_does_not_change_the_artifact_hash() -> None:
    """The hash pins what was bound, not who has looked at it."""
    facts = fact_tier(CONFIRMED_TRANSFER)
    reviewed = _fields(facts)
    reviewed[0].reviewed_by = USER_ID
    reviewed[0].reviewed_at = datetime(2026, 8, 18, tzinfo=UTC)
    reviewed[0].review_decision_id = "dec_synthetic"

    def digest(fields: list[GeneratedFormField]) -> str:
        return draft_artifact_hash(
            template_id=FORM_08.id,
            template_version=FORM_08.version,
            rule_pack_version=RULE_PACK_VERSION,
            subtype_id=TRANSFER_SUBTYPE_ID,
            fields=fields,
        )

    assert digest(reviewed) == digest(_fields(facts))


def test_a_candidate_carries_its_own_status_and_score() -> None:
    value = candidate("rta.instrument.notary_name", "Synthetic Notary Three")
    assert isinstance(value, FactCandidate)
    assert value.model_reported_confidence == 0.99

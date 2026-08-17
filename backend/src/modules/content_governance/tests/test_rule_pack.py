"""Rule-pack integrity, source governance, and the check catalogue's severities.

`validate_rule_pack` is the build gate: it resolves every cross-reference between
the independently authored catalogues, so a dangling id fails here rather than on
a lawyer's screen.
"""

from __future__ import annotations

from src.modules.content_governance.domain.enums import (
    BlockerKind,
    IssueSeverity,
    SourceClass,
    SourceCurrencyStatus,
)
from src.modules.content_governance.domain.rta import checklist, checks, documents, questions
from src.modules.content_governance.domain.rta.rulepack import (
    CURRENT_VERSIONS,
    validate_rule_pack,
)
from src.modules.content_governance.domain.sources import SEED_SOURCE_RECORDS


def test_the_rule_pack_has_no_dangling_references() -> None:
    validate_rule_pack()


def test_every_catalogue_reports_a_version() -> None:
    versions = CURRENT_VERSIONS.as_dict()
    assert set(versions) == {
        "rulePack",
        "taxonomy",
        "questions",
        "checklist",
        "checks",
        "forms",
        "documentClasses",
        "compiler",
        "eligibility",
    }
    assert all(value for value in versions.values())


# ── Source governance (§13) ──────────────────────────────────────────────────


def test_no_seed_source_is_lawyer_approved() -> None:
    """The accurate state today; §13.2.2 requires a named lawyer to change it."""
    for record in SEED_SOURCE_RECORDS:
        assert record.lawyer_approval is None, record.id


def test_every_seed_source_requires_reverification() -> None:
    """§13.2.6 — an unverified source must be labelled, not relied on."""
    for record in SEED_SOURCE_RECORDS:
        assert record.requires_reverification is True, record.id


def test_the_undated_fee_page_is_never_marked_current() -> None:
    """§13.4 — a stale fee must not be representable as final."""
    charges = next(r for r in SEED_SOURCE_RECORDS if r.id == "src.lk.rgd.ops.charges")
    assert charges.currency_status is not SourceCurrencyStatus.CURRENT
    assert charges.effective_from is None


def test_the_tire31_scan_is_unverified_and_not_a_gazette_form() -> None:
    scan = next(r for r in SEED_SOURCE_RECORDS if r.id == "src.lk.rgd.ops.tire31")
    assert scan.source_class is SourceClass.UNVERIFIED
    assert scan.notes is not None
    assert "Form 31" in scan.notes


def test_the_act_and_the_gazette_are_primary_sources() -> None:
    by_id = {r.id: r for r in SEED_SOURCE_RECORDS}
    assert by_id["src.lk.rta.act.1998"].source_class is SourceClass.LAW
    assert by_id["src.lk.rta.gazette.2308_27.2022"].source_class is SourceClass.REG


def test_the_2014_gazette_is_marked_superseded() -> None:
    older = next(r for r in SEED_SOURCE_RECORDS if r.id == "src.lk.rta.gazette.1886_58.2014")
    assert older.currency_status is SourceCurrencyStatus.SUPERSEDED


# ── Requirements (§5.1, §5.4) ────────────────────────────────────────────────


def test_all_twenty_three_checklist_modules_exist() -> None:
    assert len(checklist.CHECKLIST_MODULES) == 23
    assert checklist.all_module_ids()[0] == "C00_MATTER_ADMIN"
    assert checklist.all_module_ids()[-1] == "C22_COOWNERS"


def test_every_module_has_at_least_one_requirement() -> None:
    for module in checklist.CHECKLIST_MODULES:
        assert module.requirement_ids, module.id


def test_the_v0_modules_are_substantively_populated() -> None:
    """§14.2 — the always-on modules carry real depth, not a placeholder item."""
    for module_id in (
        "C00_MATTER_ADMIN",
        "C01_IDENTITY_CAPACITY",
        "C02_RTA_TITLE",
        "C03_REGISTRY_SEARCH",
        "C04_SURVEY_CADASTRAL",
        "C06_ENCUMBRANCES",
        "C07_MORTGAGE_RELEASE",
        "C18_CANCELLATION_RELEASE",
        "C20_STAMP_REGISTRATION",
    ):
        assert len(checklist.requirements_for_module(module_id)) >= 4, module_id


def test_no_requirement_asserts_a_rule_without_a_source() -> None:
    for requirement in checklist.REQUIREMENTS:
        assert requirement.sources, requirement.id


def test_a_statutory_requirement_can_never_be_waived() -> None:
    for requirement in checklist.REQUIREMENTS:
        if requirement.unsatisfied_blocker_kind is BlockerKind.STATUTORY:
            assert requirement.waivable is False, requirement.id


def test_a_non_waivable_requirement_is_never_role_overridable() -> None:
    overridable = {BlockerKind.OFFICE_POLICY, BlockerKind.PROFESSIONAL_JUDGMENT}
    for requirement in checklist.REQUIREMENTS:
        if not requirement.waivable:
            assert requirement.unsatisfied_blocker_kind not in overridable, requirement.id


def test_local_authority_requirements_are_scoped_and_never_global() -> None:
    """§13.2.8 — a rule for one council cannot activate everywhere."""
    local = checklist.requirements_for_module("C11_LOCAL_AUTHORITY")
    assert local
    for requirement in local:
        assert requirement.local_authority_scoped is True, requirement.id


def test_street_line_and_building_line_stay_separate_requirements() -> None:
    """§1.2 — a deck slide conflated them; the enquiries are different."""
    ids = {r.id for r in checklist.requirements_for_module("C11_LOCAL_AUTHORITY")}
    assert "R_C11_STREET_LINE" in ids
    assert "R_C11_BUILDING_LINE" in ids


def test_the_original_inspection_requirement_demands_a_human_event() -> None:
    """§5.4 — no scan may satisfy it, so it is also not waivable."""
    requirement = checklist.require_requirement("R_C20_ORIGINAL_TITLE_CERTIFICATE_INSPECTED")
    assert requirement.physical_original_policy.value == "ORIGINAL_INSPECTED"
    assert requirement.waivable is False


def test_registration_packs_cover_every_prescribed_instrument() -> None:
    assert len(checklist.SUBTYPE_REGISTRATION_PACKS) == 22
    for subtype_id, pack_ids in checklist.SUBTYPE_REGISTRATION_PACKS.items():
        assert pack_ids, subtype_id
        for pack_id in pack_ids:
            assert checklist.get_registration_pack(pack_id) is not None, pack_id


def test_the_transfer_pack_includes_the_duplicate_rule_and_the_tire31_application() -> None:
    """§5.6 — RP-BASE + RP-DUP + RP-TC for a Form 8 transfer."""
    packs = checklist.SUBTYPE_REGISTRATION_PACKS["lk.rta.instrument.transfer_sale"]
    assert set(packs) == {"RP-BASE", "RP-DUP", "RP-TC"}


def test_every_registration_pack_requirement_resolves() -> None:
    for pack in checklist.REGISTRATION_PACKS:
        assert pack.requirement_ids, pack.id
        for requirement_id in pack.requirement_ids:
            assert checklist.get_requirement(requirement_id) is not None, requirement_id


# ── Checks (§7.2, §7.3) ──────────────────────────────────────────────────────


def test_the_essential_v0_checks_are_all_defined() -> None:
    defined = {check.id for check in checks.CHECK_DEFINITIONS}
    for check_id in (
        "CHK_OWNER_TRANSFEROR",
        "CHK_PARTY_IDENTITY",
        "CHK_TITLE_REFERENCE",
        "CHK_PARCEL_ID",
        "CHK_EXTENT",
        "CHK_WHOLE_PART",
        "CHK_COOWNERSHIP",
        "CHK_MORTGAGE_STATUS",
        "CHK_LEASE_STATUS",
        "CHK_CAVEAT_LITIGATION",
        "CHK_FORM_REQUIRED_FIELDS",
        "CHK_DOCUMENT_CURRENCY",
        "CHK_ATTESTATION_DEADLINE",
    ):
        assert check_id in defined, check_id


def test_the_section_47_and_48_checks_are_statutory_blockers() -> None:
    for check_id in ("CHK_WHOLE_PART", "CHK_COOWNERSHIP"):
        definition = checks.require_check(check_id)
        assert definition.failure_severity is IssueSeverity.BLOCKING, check_id
        assert definition.failure_blocker_kind is BlockerKind.STATUTORY, check_id


def test_the_owner_transferor_check_blocks_drafting() -> None:
    definition = checks.require_check("CHK_OWNER_TRANSFEROR")
    assert definition.failure_severity is IssueSeverity.BLOCKING
    assert definition.blocks_draft_generation is True


def test_the_mortgage_check_blocks_approval_and_refuses_to_read_silence() -> None:
    definition = checks.require_check("CHK_MORTGAGE_STATUS")
    assert definition.failure_severity is IssueSeverity.HIGH_RISK
    assert definition.blocks_approval is True
    assert definition.absence_is_not_evidence is True


def test_the_assessment_name_check_is_only_a_warning() -> None:
    """§Executive 9 — a council record must never conclude a lack of title."""
    definition = checks.require_check("CHK_ASSESSMENT_NAME")
    assert definition.failure_severity is IssueSeverity.WARNING
    assert definition.failure_blocker_kind is not BlockerKind.STATUTORY
    assert definition.blocks_approval is False
    assert definition.blocks_draft_generation is False


#: Checks whose inputs are decided by the selected template or by document
#: metadata rather than by a fixed set of fact types, so a static input list
#: would be wrong rather than merely absent.
_TEMPLATE_DRIVEN_CHECKS = frozenset({"CHK_FORM_REQUIRED_FIELDS"})


def test_every_check_names_its_issue_type_its_safety_rule_and_its_source() -> None:
    for definition in checks.CHECK_DEFINITIONS:
        assert definition.issue_type_id.startswith("rta.issue."), definition.id
        assert definition.safety_rule_key, definition.id
        assert definition.sources, definition.id


def test_every_fact_driven_check_names_the_facts_it_compares() -> None:
    for definition in checks.CHECK_DEFINITIONS:
        if definition.id in _TEMPLATE_DRIVEN_CHECKS:
            continue
        assert definition.input_fact_type_ids, definition.id


def test_a_blocking_check_always_blocks_approval() -> None:
    for definition in checks.CHECK_DEFINITIONS:
        if definition.failure_severity is IssueSeverity.BLOCKING:
            assert definition.blocks_approval is True, definition.id


# ── Questions (§4) ───────────────────────────────────────────────────────────


def test_the_routing_interview_is_seven_questions() -> None:
    assert len(questions.ROUTING_QUESTIONS) == 7
    assert [q.id for q in questions.ROUTING_QUESTIONS][0] == "Q01_REGIME"


def test_all_twenty_five_questions_are_defined() -> None:
    assert len(questions.ALL_QUESTIONS) == 25


def test_question_ids_are_unique() -> None:
    ids = [q.id for q in questions.ALL_QUESTIONS]
    assert len(ids) == len(set(ids))


def test_the_originals_question_is_never_inferable() -> None:
    """§4.3 Q18 — human attestation per item, never derived."""
    originals = questions.require_question("Q18_ORIGINALS")
    assert originals.inferable is False
    assert originals.lawyer_confirmation_required is True


def test_the_upload_step_is_not_a_legal_answer() -> None:
    upload = questions.require_question("Q07_UPLOAD")
    assert upload.lawyer_confirmation_required is False


def test_the_regime_question_comes_first_and_gates_eligibility() -> None:
    regime = questions.require_question("Q01_REGIME")
    assert regime.order == 1
    assert regime.controls_v0_eligibility is True
    assert regime.allows_unknown is True


def test_the_v0_question_set_matches_the_spec() -> None:
    """§14.3 — Q01-Q07 plus the named conditional set."""
    expected = {
        "Q01_REGIME",
        "Q02_INTENT",
        "Q03_SCOPE",
        "Q04_PARCEL_KIND",
        "Q05_PARTY_CONTEXT",
        "Q06_DISPUTE",
        "Q07_UPLOAD",
        "Q10_MORTGAGE",
        "Q11_LEASE_OCCUPATION",
        "Q14_ENCUMBRANCE",
        "Q18_ORIGINALS",
        "Q19_MISSING_ORIGINAL",
        "Q20_COOWNERS",
        "Q23_SEARCH_CUTOFF",
        "Q24_CONSIDERATION",
        "Q25_DEADLINE",
    }
    assert set(questions.v0_question_ids()) == expected


# ── Document classes and confidence policy (§6.4, §14.4) ─────────────────────


def test_unidentified_and_combined_certificate_are_real_supported_outcomes() -> None:
    assert documents.get_document_class(documents.UNIDENTIFIED_DOCUMENT_CLASS_ID) is not None
    assert documents.get_document_class(documents.COMBINED_CERTIFICATE_CLASS_ID) is not None


def test_the_combined_certificate_may_satisfy_several_requirements() -> None:
    combined = documents.require_document_class(documents.COMBINED_CERTIFICATE_CLASS_ID)
    assert combined.may_satisfy_multiple_requirements is True


def test_the_tire31_application_is_its_own_document_class() -> None:
    """§14.4 item 3 — separate class and namespace from Gazette Form 31."""
    assert documents.get_document_class("rta.doc.tire31_application") is not None


def test_red_flag_and_exclusion_classes_exist() -> None:
    assert documents.red_flag_class_ids()
    assert documents.exclusion_indicator_class_ids()


def test_a_critical_fact_can_never_be_auto_confirmed_at_any_confidence() -> None:
    """§6.4 — no confidence bypass, even at 1.00."""
    for confidence in (0.0, 0.5, 0.949, 0.95, 0.999, 1.0, 1.5):
        assert documents.may_auto_confirm_critical_fact(confidence) is False


def test_boundary_auto_split_needs_high_confidence_and_no_anomaly() -> None:
    assert documents.may_auto_split_boundary(0.98, continuity_anomaly=False) is True
    assert documents.may_auto_split_boundary(0.98, continuity_anomaly=True) is False
    assert documents.may_auto_split_boundary(0.90, continuity_anomaly=False) is False


def test_class_auto_organize_needs_both_confidence_and_margin() -> None:
    assert documents.may_auto_organize_class(0.96, 0.20) is True
    assert documents.may_auto_organize_class(0.96, 0.10) is False
    assert documents.may_auto_organize_class(0.90, 0.20) is False


def test_noncritical_prefill_refuses_conflicts_and_dirty_ocr() -> None:
    assert documents.may_prefill_noncritical(0.97, conflicting=False, clean_ocr=True) is True
    assert documents.may_prefill_noncritical(0.97, conflicting=True, clean_ocr=True) is False
    assert documents.may_prefill_noncritical(0.97, conflicting=False, clean_ocr=False) is False

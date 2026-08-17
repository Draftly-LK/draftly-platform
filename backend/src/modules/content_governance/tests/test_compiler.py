"""Checklist compiler — determinism, provenance, and non-destructive recompiles."""

from __future__ import annotations

from dataclasses import replace

from src.modules.content_governance.domain.enums import (
    ApplicabilityStatus,
    BlockerKind,
    MandatoryBasis,
)
from src.modules.content_governance.domain.rta import checklist, compiler
from src.modules.content_governance.domain.rta.compiler import (
    CompilerInput,
    InclusionReason,
    ReviewedItemMemo,
    compile_checklist,
    diff_checklists,
)

TRANSFER = "lk.rta.instrument.transfer_sale"
MORTGAGE_CANCEL = "lk.rta.instrument.mortgage_cancel"


def test_compilation_is_deterministic() -> None:
    data = CompilerInput(subtype_id=TRANSFER)
    first, second = compile_checklist(data), compile_checklist(data)
    assert first.item_ids() == second.item_ids()
    assert first.fingerprint == second.fingerprint


def test_item_order_is_stable_regardless_of_input_set_ordering() -> None:
    """Sets are unordered; the compiled output must not be."""
    a = compile_checklist(
        CompilerInput(
            subtype_id=TRANSFER,
            activated_conditional_module_ids=frozenset(
                {"lk.rta.module.mortgage_present", "lk.rta.module.lease_or_occupation"}
            ),
        )
    )
    b = compile_checklist(
        CompilerInput(
            subtype_id=TRANSFER,
            activated_conditional_module_ids=frozenset(
                {"lk.rta.module.lease_or_occupation", "lk.rta.module.mortgage_present"}
            ),
        )
    )
    assert a.item_ids() == b.item_ids()
    assert a.fingerprint == b.fingerprint


def test_base_and_regime_modules_are_always_compiled() -> None:
    compiled = compile_checklist(CompilerInput())
    assert "C00_MATTER_ADMIN" in compiled.module_definition_ids
    assert "C02_RTA_TITLE" in compiled.module_definition_ids


def test_an_unrouted_matter_still_gets_a_usable_checklist() -> None:
    """A matter with no subtype yet is scoped, not empty."""
    compiled = compile_checklist(CompilerInput())
    assert compiled.items


def test_the_exact_instrument_pulls_in_its_own_modules() -> None:
    compiled = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    modules = set(compiled.module_definition_ids)
    for module_id in ("C01_IDENTITY_CAPACITY", "C04_SURVEY_CADASTRAL", "C20_STAMP_REGISTRATION"):
        assert module_id in modules


def test_form_12_compiles_the_mortgage_release_and_cancellation_modules() -> None:
    compiled = compile_checklist(CompilerInput(subtype_id=MORTGAGE_CANCEL))
    modules = set(compiled.module_definition_ids)
    assert "C07_MORTGAGE_RELEASE" in modules
    assert "C18_CANCELLATION_RELEASE" in modules


def test_a_conditional_module_adds_items_and_records_what_triggered_them() -> None:
    without = compile_checklist(CompilerInput(subtype_id=MORTGAGE_CANCEL))
    with_company = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
        )
    )
    added = set(with_company.item_ids()) - set(without.item_ids())
    assert added
    for item in with_company.items:
        if item.requirement_definition_id in added:
            assert item.inclusion_reason is InclusionReason.CONDITIONAL_MODULE
            assert item.inclusion_trigger_id == "lk.rta.module.company_party"


def test_every_item_records_why_it_is_present() -> None:
    """§5.1 — a lawyer must be able to see where a requirement came from."""
    compiled = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    for item in compiled.items:
        assert item.inclusion_reason in set(InclusionReason)
        assert item.label_key
        assert item.explanation_key
        assert item.mandatory_basis in set(MandatoryBasis)
        assert item.source_record_ids


def test_a_suppressed_conditional_module_is_honoured() -> None:
    compiled = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
            suppressed_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
        )
    )
    assert "C10_COMPANY_AUTHORITY" not in compiled.module_definition_ids


def test_conditionally_included_requirements_are_never_flatly_required() -> None:
    """A fact still under review put them there, so they are not certainties.

    Either the requirement's own default is already ``CONDITIONAL``, or the
    compiler promotes a ``REQUIRED`` default to ``PROVISIONAL_REQUIRED``. What
    must never happen is a conditionally triggered item presenting as settled.
    """
    compiled = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset(
                {
                    "lk.rta.module.company_party",
                    "lk.rta.module.local_authority_clearance",
                    "lk.rta.module.building_present",
                }
            ),
        )
    )
    triggered = [
        item
        for item in compiled.items
        if item.inclusion_reason is InclusionReason.CONDITIONAL_MODULE
    ]
    assert triggered
    for item in triggered:
        assert item.applicability in {
            ApplicabilityStatus.CONDITIONAL,
            ApplicabilityStatus.PROVISIONAL_REQUIRED,
        }, item.requirement_definition_id


def test_a_required_default_is_promoted_to_provisional_when_conditionally_included() -> None:
    compiled = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
            office_policy_module_ids=frozenset({"C04_SURVEY_CADASTRAL"}),
        )
    )
    office_added = [
        item for item in compiled.items if item.inclusion_reason is InclusionReason.OFFICE_POLICY
    ]
    assert office_added
    promoted = [
        item
        for item in office_added
        if checklist.require_requirement(item.requirement_definition_id).default_applicability
        is ApplicabilityStatus.REQUIRED
    ]
    assert promoted
    for item in promoted:
        assert item.applicability is ApplicabilityStatus.PROVISIONAL_REQUIRED


def test_a_requirement_reachable_twice_appears_once() -> None:
    compiled = compile_checklist(
        CompilerInput(
            subtype_id=TRANSFER,
            activated_conditional_module_ids=frozenset({"lk.rta.module.mortgage_present"}),
            office_policy_module_ids=frozenset({"C02_RTA_TITLE", "C07_MORTGAGE_RELEASE"}),
        )
    )
    ids = compiled.item_ids()
    assert len(ids) == len(set(ids))


def test_local_authority_items_are_scoped_to_the_named_authority() -> None:
    """§13.2.8 — a council rule must not activate globally."""
    compiled = compile_checklist(
        CompilerInput(
            subtype_id=TRANSFER,
            activated_conditional_module_ids=frozenset({"lk.rta.module.local_authority_clearance"}),
            local_authority_id="la-synthetic-001",
        )
    )
    local_items = [
        item for item in compiled.items if item.module_definition_id == "C11_LOCAL_AUTHORITY"
    ]
    assert local_items
    for item in local_items:
        assert item.local_authority_id == "la-synthetic-001"
        assert item.mandatory_basis is MandatoryBasis.LOCAL_AUTHORITY


def test_non_local_items_carry_no_authority_scope() -> None:
    compiled = compile_checklist(
        CompilerInput(subtype_id=TRANSFER, local_authority_id="la-synthetic-001")
    )
    for item in compiled.items:
        if item.module_definition_id != "C11_LOCAL_AUTHORITY":
            assert item.local_authority_id is None


def test_a_reviewed_requirement_is_retained_when_it_stops_being_triggered() -> None:
    """§5.1 — it never silently removes a previously reviewed requirement."""
    with_company = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
        )
    )
    reviewed = next(
        item.requirement_definition_id
        for item in with_company.items
        if item.module_definition_id == "C10_COMPANY_AUTHORITY"
    )
    recompiled = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            previous_items=(
                ReviewedItemMemo(requirement_definition_id=reviewed, was_reviewed=True),
            ),
        )
    )
    retained = [item for item in recompiled.items if item.requirement_definition_id == reviewed]
    assert len(retained) == 1
    assert retained[0].inclusion_reason is InclusionReason.RETAINED_AFTER_REVIEW
    assert retained[0].applicability is ApplicabilityStatus.NOT_APPLICABLE


def test_an_unreviewed_requirement_is_simply_dropped() -> None:
    """Retention protects human work, not every item that ever existed."""
    with_company = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
        )
    )
    untouched = next(
        item.requirement_definition_id
        for item in with_company.items
        if item.module_definition_id == "C10_COMPANY_AUTHORITY"
    )
    recompiled = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            previous_items=(
                ReviewedItemMemo(requirement_definition_id=untouched, was_reviewed=False),
            ),
        )
    )
    assert untouched not in recompiled.item_ids()


def test_the_delta_reports_added_removed_and_retained() -> None:
    before = compile_checklist(CompilerInput(subtype_id=MORTGAGE_CANCEL))
    after = compile_checklist(
        CompilerInput(
            subtype_id=MORTGAGE_CANCEL,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
        )
    )
    delta = diff_checklists(before, after)
    assert delta.added
    assert delta.removed == ()
    assert not delta.is_empty

    reverse = diff_checklists(after, before)
    assert reverse.removed
    assert reverse.added == ()


def test_an_unchanged_recompile_produces_an_empty_delta() -> None:
    compiled = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    assert diff_checklists(compiled, compiled).is_empty


def test_the_fingerprint_changes_when_the_inputs_change() -> None:
    a = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    b = compile_checklist(
        CompilerInput(
            subtype_id=TRANSFER,
            activated_conditional_module_ids=frozenset({"lk.rta.module.company_party"}),
        )
    )
    assert a.fingerprint != b.fingerprint


def test_the_snapshot_pins_every_rule_version_it_used() -> None:
    compiled = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    assert compiled.compiler_version == compiler.COMPILER_VERSION
    assert compiled.checklist_version == checklist.CHECKLIST_VERSION
    assert compiled.taxonomy_version


def test_statutory_items_are_not_waivable() -> None:
    compiled = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    for item in compiled.items:
        if item.unsatisfied_blocker_kind is BlockerKind.STATUTORY:
            assert item.waivable is False


def test_a_v0_transfer_compiles_the_essential_module_set() -> None:
    """§14.2 — the always-on modules for the pilot."""
    compiled = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    modules = set(compiled.module_definition_ids)
    for module_id in (
        "C00_MATTER_ADMIN",
        "C01_IDENTITY_CAPACITY",
        "C02_RTA_TITLE",
        "C03_REGISTRY_SEARCH",
        "C04_SURVEY_CADASTRAL",
        "C06_ENCUMBRANCES",
        "C20_STAMP_REGISTRATION",
    ):
        assert module_id in modules, module_id


def test_compiling_an_unknown_subtype_degrades_rather_than_crashing() -> None:
    compiled = compile_checklist(CompilerInput(subtype_id="lk.rta.instrument.nonexistent"))
    assert compiled.items
    assert all(
        item.inclusion_reason is not InclusionReason.EXACT_INSTRUMENT for item in compiled.items
    )


def test_an_unknown_conditional_module_is_ignored_not_fatal() -> None:
    compiled = compile_checklist(
        CompilerInput(
            subtype_id=TRANSFER,
            activated_conditional_module_ids=frozenset({"lk.rta.module.nonexistent"}),
        )
    )
    baseline = compile_checklist(CompilerInput(subtype_id=TRANSFER))
    assert compiled.item_ids() == baseline.item_ids()


def test_changing_only_the_local_authority_changes_the_fingerprint() -> None:
    a = compile_checklist(CompilerInput(subtype_id=TRANSFER, local_authority_id="la-a"))
    b = compile_checklist(CompilerInput(subtype_id=TRANSFER, local_authority_id="la-b"))
    assert a.fingerprint != b.fingerprint


def test_replace_on_the_input_does_not_leak_state_between_compiles() -> None:
    base = CompilerInput(subtype_id=TRANSFER)
    first = compile_checklist(base)
    compile_checklist(replace(base, subtype_id=MORTGAGE_CANCEL))
    assert compile_checklist(base).item_ids() == first.item_ids()

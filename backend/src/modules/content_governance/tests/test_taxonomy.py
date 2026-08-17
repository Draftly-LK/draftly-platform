"""Taxonomy tests — the 22 instruments, the families, and legacy migration.

These are acceptance criteria from the workflow spec §17, not incidental unit
tests. "No user can reach approved Form 8/Form 12 export by selecting legacy
`other`" and "Gazette Form 31 and operational Ti.Re.31 coexist without ID or
template collision" are both checked here.
"""

from __future__ import annotations

import pytest

from src.modules.content_governance.domain.enums import (
    MatterFamily,
    ReleaseTier,
    SubtypeKind,
)
from src.modules.content_governance.domain.rta import taxonomy
from src.modules.content_governance.domain.sources import get_source_record


def test_exactly_twenty_two_prescribed_instruments() -> None:
    assert len(taxonomy.PRESCRIBED_INSTRUMENTS) == 22


def test_every_subtype_id_is_unique() -> None:
    ids = [subtype.id for subtype in taxonomy.ALL_SUBTYPES]
    assert len(ids) == len(set(ids))


def test_every_subtype_id_is_namespaced_under_the_regime() -> None:
    for subtype in taxonomy.ALL_SUBTYPES:
        assert subtype.id.startswith("lk.rta."), subtype.id


def test_prescribed_instruments_use_the_instrument_namespace() -> None:
    for subtype in taxonomy.PRESCRIBED_INSTRUMENTS:
        assert subtype.id.startswith("lk.rta.instrument.")
        assert subtype.kind is SubtypeKind.PRESCRIBED_INSTRUMENT


def test_every_prescribed_instrument_names_a_gazette_form_and_template() -> None:
    for subtype in taxonomy.PRESCRIBED_INSTRUMENTS:
        assert subtype.gazette_form_number, subtype.id
        assert subtype.form_template_id, subtype.id


def test_gazette_form_numbers_are_unique_across_the_twenty_two() -> None:
    numbers = [subtype.gazette_form_number for subtype in taxonomy.PRESCRIBED_INSTRUMENTS]
    assert len(numbers) == len(set(numbers))


def test_processes_and_services_are_not_counted_among_the_twenty_two() -> None:
    """§3.4 — initial compilation is a different statutory process, not a form."""
    prescribed_ids = {s.id for s in taxonomy.PRESCRIBED_INSTRUMENTS}
    for subtype in (*taxonomy.ADDITIONAL_PROCESSES, *taxonomy.REGISTRY_SERVICES):
        assert subtype.id not in prescribed_ids
        assert subtype.kind is not SubtypeKind.PRESCRIBED_INSTRUMENT


def test_six_transaction_families_and_three_separate_ones() -> None:
    transaction = [f for f in taxonomy.FAMILIES if f.is_transaction_family]
    separate = [f for f in taxonomy.FAMILIES if not f.is_transaction_family]
    assert {f.id for f in transaction} == {
        MatterFamily.OWNERSHIP_CHANGE,
        MatterFamily.AGREEMENT_SECURITY,
        MatterFamily.USE_INTEREST,
        MatterFamily.CANCEL_RELEASE,
        MatterFamily.NOTICE_ADMIN,
        MatterFamily.PARCEL_STRUCTURE,
    }
    assert {f.id for f in separate} == {
        MatterFamily.TITLE_SETTLEMENT,
        MatterFamily.DISPUTE_RECTIFICATION,
        MatterFamily.CONTROLLED_OTHER,
    }


def test_every_subtype_belongs_to_a_declared_family() -> None:
    known = {family.id for family in taxonomy.FAMILIES}
    for subtype in taxonomy.ALL_SUBTYPES:
        assert subtype.family_id in known, subtype.id


def test_every_family_that_holds_transactions_has_at_least_one_subtype() -> None:
    for family in taxonomy.FAMILIES:
        if family.is_transaction_family:
            assert taxonomy.subtypes_in_family(family.id), family.id


def test_only_the_two_pilot_instruments_plus_tire31_are_v0() -> None:
    """§14.1 — V0 is intentionally narrow; nothing else produces automated output."""
    assert set(taxonomy.v0_subtype_ids()) == {
        "lk.rta.instrument.transfer_sale",
        "lk.rta.instrument.mortgage_cancel",
        "lk.rta.service.new_title_certificate_application",
    }


def test_transfer_sale_carries_the_tire31_companion() -> None:
    transfer = taxonomy.require_subtype("lk.rta.instrument.transfer_sale")
    assert "rta.ops.tire.31" in transfer.companion_template_ids


def test_gazette_form_31_and_operational_tire_31_are_different_templates() -> None:
    """§Executive 11 — the two must never be interchangeable."""
    address = taxonomy.require_subtype("lk.rta.instrument.address_register")
    title_certificate = taxonomy.require_subtype("lk.rta.service.new_title_certificate_application")
    assert address.form_template_id == "rta.reg.2022.form.31"
    assert title_certificate.form_template_id == "rta.ops.tire.31"
    assert address.form_template_id != title_certificate.form_template_id
    assert address.id != title_certificate.id


def test_non_v0_subtypes_explain_why_they_are_excluded() -> None:
    for subtype in taxonomy.ALL_SUBTYPES:
        if subtype.release_tier is not ReleaseTier.V0:
            assert subtype.out_of_v0_reason_key, subtype.id


def test_controlled_other_requires_a_declared_legal_basis() -> None:
    """§3.2 — never a default classification."""
    fallback = taxonomy.require_subtype("lk.rta.instrument.other_declared_instrument")
    assert fallback.requires_declared_legal_basis is True
    assert fallback.release_tier is ReleaseTier.MANUAL_ONLY
    assert fallback.family_id is MatterFamily.CONTROLLED_OTHER


def test_no_subtype_other_than_the_fallback_requires_a_declared_basis() -> None:
    requiring = [s.id for s in taxonomy.ALL_SUBTYPES if s.requires_declared_legal_basis]
    assert requiring == ["lk.rta.instrument.other_declared_instrument"]


def test_every_subtype_cites_a_resolvable_source() -> None:
    for subtype in taxonomy.ALL_SUBTYPES:
        assert subtype.sources, subtype.id
        for citation in subtype.sources:
            assert get_source_record(citation.source_record_id) is not None, citation


# ── Legacy migration (§3.6) ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        ("transfer", "lk.rta.instrument.transfer_sale"),
        ("gift", "lk.rta.instrument.gift"),
        ("lease", "lk.rta.instrument.lease"),
        ("mortgage", "lk.rta.instrument.mortgage"),
        ("other", "lk.rta.instrument.other_declared_instrument"),
    ],
)
def test_legacy_matter_types_migrate_to_the_documented_targets(legacy: str, expected: str) -> None:
    result = taxonomy.migrate_legacy_matter_type(legacy)
    assert result.subtype_id == expected
    assert taxonomy.get_subtype(result.subtype_id) is not None


def test_migration_never_confirms_the_subtype_itself() -> None:
    """A migration is a data move, not a lawyer's decision."""
    for legacy in taxonomy.LEGACY_MATTER_TYPE_MAP:
        assert taxonomy.migrate_legacy_matter_type(legacy).needs_lawyer_confirmation is True


def test_migration_marks_legacy_documents_unreviewed_rather_than_other() -> None:
    """§3.6 — it must not preserve the false assumption that every type is `other`."""
    result = taxonomy.migrate_legacy_matter_type("transfer")
    assert result.legacy_document_classification_status == "UNREVIEWED_LEGACY"


def test_migrating_gift_activates_life_interest_screening() -> None:
    result = taxonomy.migrate_legacy_matter_type("gift")
    assert "lk.rta.module.life_interest" in result.activated_conditional_module_ids


def test_migrating_mortgage_activates_mortgage_screening() -> None:
    result = taxonomy.migrate_legacy_matter_type("mortgage")
    assert "lk.rta.module.mortgage_present" in result.activated_conditional_module_ids


def test_migrating_other_requires_a_declared_legal_basis() -> None:
    """Legacy `other` can never auto-approve into a drafting path."""
    result = taxonomy.migrate_legacy_matter_type("other")
    assert result.requires_declared_legal_basis is True


def test_an_unmapped_legacy_type_is_refused_rather_than_guessed() -> None:
    with pytest.raises(KeyError):
        taxonomy.migrate_legacy_matter_type("conveyance")


# ── Conditional modules (§3.5) ───────────────────────────────────────────────


def test_conditional_module_ids_are_unique_and_namespaced() -> None:
    ids = [module.id for module in taxonomy.CONDITIONAL_MODULES]
    assert len(ids) == len(set(ids))
    for module_id in ids:
        assert module_id.startswith("lk.rta.module.")


def test_the_v0_excluding_conditional_modules_are_marked_as_such() -> None:
    """A company, estate, POA, co-owner, life-interest, or dispute matter leaves V0."""
    excluding = {m.id for m in taxonomy.CONDITIONAL_MODULES if m.excludes_v0}
    for module_id in (
        "lk.rta.module.company_party",
        "lk.rta.module.estate_or_deceased_owner",
        "lk.rta.module.power_of_attorney",
        "lk.rta.module.coowners",
        "lk.rta.module.life_interest",
        "lk.rta.module.active_notice_or_litigation",
        "lk.rta.module.condominium_strata",
        "lk.rta.module.subdivision_amalgamation",
    ):
        assert module_id in excluding, module_id

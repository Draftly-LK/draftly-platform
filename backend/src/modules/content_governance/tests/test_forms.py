"""Form template registry — namespacing, and the honest approval state.

The §17 acceptance criterion "Gazette Form 31 and operational Ti.Re.31 coexist
without ID or template collision" is checked here from the template side; the
taxonomy side is checked in `test_taxonomy.py`.

The other thing this file pins down is that **nothing in this repository is a
lawyer-approved production rendering**. If that ever changes it must change
deliberately, with a named approver — not because a template quietly acquired a
`VALIDATED` status.
"""

from __future__ import annotations

import pytest

from src.modules.content_governance.domain.enums import (
    TemplateNamespace,
    TemplateStatus,
)
from src.modules.content_governance.domain.rta import forms, taxonomy
from src.modules.content_governance.domain.rta.facts import get_fact_type
from src.modules.content_governance.domain.sources import get_source_record

FORM_08 = "rta.reg.2022.form.08"
FORM_12 = "rta.reg.2022.form.12"
GAZETTE_FORM_31 = "rta.reg.2022.form.31"
OPS_TIRE_31 = "rta.ops.tire.31"
OPS_TIRE_30 = "rta.ops.tire.30"
GAZETTE_FORM_30 = "rta.reg.2022.form.30"


def test_template_ids_are_unique() -> None:
    forms.assert_no_id_collision()
    ids = [template.id for template in forms.FORM_TEMPLATES]
    assert len(ids) == len(set(ids))


def test_all_twenty_two_prescribed_instruments_have_a_registered_template() -> None:
    for subtype in taxonomy.PRESCRIBED_INSTRUMENTS:
        assert subtype.form_template_id is not None
        assert forms.get_template(subtype.form_template_id) is not None, subtype.id


def test_gazette_form_31_registers_an_address_in_the_regulation_namespace() -> None:
    template = forms.require_template(GAZETTE_FORM_31)
    assert template.namespace is TemplateNamespace.REGULATION
    assert template.form_number == "31"
    assert "lk.rta.instrument.address_register" in template.subtype_ids


def test_operational_tire_31_is_a_title_certificate_application_in_its_own_namespace() -> None:
    template = forms.require_template(OPS_TIRE_31)
    assert template.namespace is TemplateNamespace.OPERATIONAL
    assert "lk.rta.service.new_title_certificate_application" in template.subtype_ids


def test_the_two_form_31s_cannot_collide() -> None:
    gazette = forms.require_template(GAZETTE_FORM_31)
    operational = forms.require_template(OPS_TIRE_31)
    assert gazette.id != operational.id
    assert gazette.namespace is not operational.namespace
    assert set(gazette.subtype_ids).isdisjoint(operational.subtype_ids)


def test_the_two_form_30s_cannot_collide_either() -> None:
    """§Executive 11 gives Ti.Re.30 versus Gazette Form 30 the same protection."""
    gazette = forms.require_template(GAZETTE_FORM_30)
    operational = forms.require_template(OPS_TIRE_30)
    assert gazette.id != operational.id
    assert gazette.namespace is not operational.namespace


def test_a_form_number_alone_never_identifies_a_template() -> None:
    """§9.1 — form number is not a primary key. Number 30 and 31 each appear twice."""
    for number in ("30", "31"):
        matching = [t for t in forms.FORM_TEMPLATES if t.form_number == number]
        assert len(matching) > 1, number
        assert len({t.id for t in matching}) == len(matching)


def test_no_template_is_lawyer_approved() -> None:
    """The accurate state of this repository (§9.5, §16.1 items 2 and 3)."""
    for template in forms.FORM_TEMPLATES:
        assert template.approved_by_lawyer_id is None, template.id
        assert template.status is TemplateStatus.DRAFT_TRANSCRIPTION, template.id


def test_no_template_claims_a_production_layout() -> None:
    for template in forms.FORM_TEMPLATES:
        assert template.production_layout_available is False, template.id


def test_no_template_is_registration_ready_capable() -> None:
    """Registration-ready export must be impossible today, by construction."""
    for template in forms.FORM_TEMPLATES:
        assert template.registration_ready_capable is False, template.id


def test_the_2022_forms_record_their_known_source_defects() -> None:
    """§1.2, §9.5 — document the defect, never silently correct the source."""
    defective = [t for t in forms.FORM_TEMPLATES if t.known_source_defect_keys]
    assert defective
    for template in defective:
        for key in template.known_source_defect_keys:
            assert key.startswith("rta.form.defect."), key


def test_tire_31_records_that_its_translation_is_unverified() -> None:
    template = forms.require_template(OPS_TIRE_31)
    assert template.known_source_defect_keys
    assert template.official_artifact_source_record_id == "src.lk.rgd.ops.tire31"


@pytest.mark.parametrize("template_id", [FORM_08, FORM_12, OPS_TIRE_31])
def test_the_three_v0_templates_have_field_mappings(template_id: str) -> None:
    template = forms.require_template(template_id)
    assert template.field_mappings, template_id


def test_form_8_covers_the_prescribed_parcel_party_and_consideration_fields() -> None:
    template = forms.require_template(FORM_08)
    fact_type_ids = {m.fact_type_id for m in template.field_mappings if m.fact_type_id}
    for expected in (
        "rta.parcel.cadastral_map_number",
        "rta.parcel.block_number",
        "rta.parcel.sheet_number",
        "rta.parcel.parcel_number",
        "rta.parcel.extent",
        "rta.title.certificate_no",
        "rta.party.transferor_name",
        "rta.party.transferee_name",
        "rta.instrument.consideration",
    ):
        assert expected in fact_type_ids, expected


def test_every_mapped_fact_type_exists() -> None:
    for template in forms.FORM_TEMPLATES:
        for mapping in template.field_mappings:
            if mapping.fact_type_id is not None:
                assert get_fact_type(mapping.fact_type_id) is not None, mapping.fact_type_id


def test_a_field_bound_to_a_critical_fact_requires_human_confirmation() -> None:
    """§9.3 — a critical field is populated only from a confirmed fact."""
    for template in forms.FORM_TEMPLATES:
        for mapping in template.field_mappings:
            if mapping.critical:
                assert mapping.human_confirmation_required is True, (
                    template.id,
                    mapping.field_id,
                )


def test_field_ids_are_unique_within_a_template() -> None:
    for template in forms.FORM_TEMPLATES:
        field_ids = [m.field_id for m in template.field_mappings]
        assert len(field_ids) == len(set(field_ids)), template.id


def test_every_template_cites_a_resolvable_source() -> None:
    for template in forms.FORM_TEMPLATES:
        assert template.sources, template.id
        for citation in template.sources:
            assert get_source_record(citation.source_record_id) is not None, citation


def test_every_template_subtype_reference_resolves() -> None:
    for template in forms.FORM_TEMPLATES:
        for subtype_id in template.subtype_ids:
            assert taxonomy.get_subtype(subtype_id) is not None, (template.id, subtype_id)


def test_templates_for_subtype_finds_the_transfer_form_and_its_companion() -> None:
    found = {t.id for t in forms.templates_for_subtype("lk.rta.instrument.transfer_sale")}
    assert FORM_08 in found


def test_one_prescribed_instrument_maps_to_one_regulation_template() -> None:
    forms.assert_one_template_per_instrument_subtype()

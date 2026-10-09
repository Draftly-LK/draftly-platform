"""Recognition precedes checklist routing; it never claims evidence sufficiency."""

from src.modules.content_governance.contracts import DOCUMENT_CLASSES, fact_type_for_field
from src.modules.document.infrastructure.matter_document_types import (
    GovernedMatterDocumentTypesAdapter,
)


async def test_governed_recognition_and_supported_fields_do_not_require_form_routing() -> None:
    result = await GovernedMatterDocumentTypesAdapter().for_matter(
        user_id="usr_synthetic", matter_id="mat_synthetic_intake"
    )

    assert set(result.allowed_type_ids) == {definition.id for definition in DOCUMENT_CLASSES}
    assert set(result.extraction_schemas) == {
        "rta.doc.nic",
        "rta.doc.title_certificate",
        "rta.doc.survey_plan",
        "rta.doc.form8_instrument",
    }
    assert "holderNic" in {field.key for field in result.extraction_schemas["rta.doc.nic"]}
    assert all(
        fact_type_for_field(field.key) is not None
        for fields in result.extraction_schemas.values()
        for field in fields
    )
    # Recognition is broader than supported extraction. Never invent field schemas.
    assert "rta.doc.title_register_extract" in result.allowed_type_ids
    assert "rta.doc.title_register_extract" not in result.extraction_schemas
    assert "rta.doc.unidentified" not in result.extraction_schemas

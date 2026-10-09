"""Governed recognition and extraction, independent of requirement routing."""

from __future__ import annotations

from src.modules.content_governance.contracts import (
    DOCUMENT_CLASSES,
    fact_type_for_field,
    get_document_class,
)
from src.modules.document.domain.registry import get_template
from src.modules.document.ports import (
    ExtractionFieldSchema,
    MatterDocumentTypes,
)

_TEMPLATE_BY_CLASS_ID = {
    "rta.doc.nic": "identity-card",
    "rta.doc.title_certificate": "title-certificate",
    "rta.doc.survey_plan": "survey-plan",
    "rta.doc.form8_instrument": "form8-instrument",
    # Retained for older checklist snapshots created before the governed class ID.
    "rta.doc.prescribed_instrument": "form8-instrument",
}


def template_kind_for_class(class_id: str) -> str | None:
    """The extraction template a governed document class reads with, if it has one."""
    return _TEMPLATE_BY_CLASS_ID.get(class_id)


class GovernedMatterDocumentTypesAdapter:
    """Offer catalogue classes before a form exists; never accept model-invented types.

    The ingestion owner authorizes the source/matter before calling this port.
    This projection reads no matter data and creates no checklist or requirement.
    Catalogue recognition does not assert extraction support or legal sufficiency.
    """

    async def for_matter(self, *, user_id: str, matter_id: str) -> MatterDocumentTypes:
        allowed = sorted(definition.id for definition in DOCUMENT_CLASSES)
        schemas: dict[str, tuple[ExtractionFieldSchema, ...]] = {}
        for class_id in allowed:
            definition = get_document_class(class_id)
            kind = definition.extraction_template_kind if definition else None
            template = get_template(kind) if kind else None
            if template is None:
                continue
            schemas[class_id] = tuple(
                ExtractionFieldSchema(key=field.key, description=field.label)
                for field in template.fields
                if fact_type_for_field(field.key) is not None
            )
        return MatterDocumentTypes(tuple(allowed), schemas)

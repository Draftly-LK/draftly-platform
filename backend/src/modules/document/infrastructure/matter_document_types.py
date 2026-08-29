"""Checklist-backed adapter for V1 classification types and extraction schemas."""

from __future__ import annotations

from src.modules.content_governance.contracts import fact_type_for_field
from src.modules.document.domain.registry import get_template
from src.modules.document.ports import (
    ExtractionFieldSchema,
    MatterDocumentTypes,
)
from src.modules.task.application.checklist_service import ChecklistService
from src.modules.task.domain.errors import ChecklistSnapshotNotFoundError

_TEMPLATE_BY_CLASS_ID = {
    "rta.doc.nic": "identity-card",
    "rta.doc.title_certificate": "title-certificate",
    "rta.doc.survey_plan": "survey-plan",
    "rta.doc.form8_instrument": "form8-instrument",
    # Retained for older checklist snapshots created before the governed class ID.
    "rta.doc.prescribed_instrument": "form8-instrument",
}


class ChecklistMatterDocumentTypesAdapter:
    """Reads the current governed checklist; never accepts a model-invented type."""

    def __init__(self, checklist: ChecklistService) -> None:
        self._checklist = checklist

    async def for_matter(self, *, user_id: str, matter_id: str) -> MatterDocumentTypes:
        try:
            checklist = await self._checklist.get_checklist(user_id=user_id, matter_id=matter_id)
        except ChecklistSnapshotNotFoundError:
            return MatterDocumentTypes(allowed_type_ids=(), extraction_schemas={})

        allowed = sorted(
            {
                class_id
                for item in checklist.items
                for class_id in item.requirement.accepted_document_class_ids
            }
        )
        schemas: dict[str, tuple[ExtractionFieldSchema, ...]] = {}
        for class_id in allowed:
            kind = _TEMPLATE_BY_CLASS_ID.get(class_id)
            template = get_template(kind) if kind else None
            if template is None:
                continue
            schemas[class_id] = tuple(
                ExtractionFieldSchema(key=field.key, description=field.label)
                for field in template.fields
                if fact_type_for_field(field.key) is not None
            )
        return MatterDocumentTypes(tuple(allowed), schemas)

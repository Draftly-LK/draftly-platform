"""Wire schemas for lawyer-reviewed facts and their evidence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class BoundingBoxRead(_CamelModel):
    x: float
    y: float
    width: float
    height: float
    coordinate_space: str


class FactEvidenceRead(_CamelModel):
    id: str
    source_file_id: str
    detected_document_id: str | None
    page_number: int
    bounding_box: BoundingBoxRead | None


class FactRead(_CamelModel):
    id: str
    matter_id: str
    fact_type_id: str
    field_key: str | None
    label_key: str
    value: Any
    status: str
    model_reported_confidence: float | None
    evidence: list[FactEvidenceRead]
    reviewed_by: str | None
    reviewed_at: str | None
    version: int
    created_at: str


class FactListRead(_CamelModel):
    items: list[FactRead]

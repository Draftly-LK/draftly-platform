"""Wire schemas for the document-processing API (camelCase like auth)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CandidateFieldRead(_CamelModel):
    """One candidate particular. ``region`` is deliberately absent: the
    Gemini-only pipeline has page-level provenance and never fabricates
    bounding boxes."""

    key: str
    value: str | None
    page_no: int
    source: str
    model_reported_confidence: float
    format_valid: bool | None


class ProcessingReportRead(_CamelModel):
    outcome: str  # "extracted" | "manual_review" | "unsupported"
    kind: str
    kind_model_confidence: float
    page_count: int
    provider: str
    fields: list[CandidateFieldRead]
    transcripts: dict[int, str]
    reasons: list[str]
    ai_extraction_calls: int
    pages_processed: int

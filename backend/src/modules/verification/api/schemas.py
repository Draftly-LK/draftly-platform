"""Wire schemas for lawyer-reviewed facts and their evidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.modules.content_governance.contracts import FactStatus
from src.platform.api.pagination import PageInfo


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
    source_sha256: str = ""
    extraction_run_id: str | None = None
    supporting_text: str | None = None
    page_text: str | None = None
    precision: Literal["page", "text"] = "page"
    candidate_id: str | None = None
    candidate_version: int | None = None


class FactRead(_CamelModel):
    id: str
    matter_id: str
    fact_type_id: str
    field_key: str | None
    label_key: str
    value: Any
    status: FactStatus
    model_reported_confidence: float | None
    evidence: list[FactEvidenceRead]
    reviewed_by: str | None
    reviewed_at: str | None
    version: int
    created_at: str
    original_value: Any = None
    origin: Literal["legacy", "machine", "lawyer"] = "legacy"
    transaction_id: str | None = None
    subject_id: str | None = None
    scope_status: Literal["legacy-unassigned", "unassigned", "assigned"] = "legacy-unassigned"
    evidence_stale: bool = False
    source_candidate_id: str | None = None
    manual_reason: str | None = None
    lineage_id: str | None = None
    supersedes_fact_id: str | None = None
    superseded_by_fact_id: str | None = None
    scope_token: str | None = None
    conflict_fact_ids: list[str] = Field(default_factory=list)


class FactListRead(_CamelModel):
    items: list[FactRead]
    page: PageInfo = Field(default_factory=PageInfo)


class EvidenceInput(_CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    source_file_id: str = Field(max_length=64)
    page_number: int = Field(ge=1)
    source_sha256: str = Field(pattern="^[a-fA-F0-9]{64}$")
    extraction_run_id: str | None = Field(default=None, max_length=64)
    detected_document_id: str | None = Field(default=None, max_length=64)
    candidate_id: str | None = Field(default=None, max_length=64)
    candidate_version: int | None = Field(default=None, ge=1)
    snippet: str | None = Field(default=None, max_length=2000)


class ManualFactRequest(_CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    fact_type_id: str = Field(max_length=128)
    value: str | int | float | bool | None
    reason: str = Field(min_length=1, max_length=2000)
    transaction_id: str | None = Field(default=None, max_length=64)
    subject_id: str | None = Field(default=None, max_length=64)
    evidence: EvidenceInput | None = None


class ReviewFactRequest(_CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    value: str | int | float | bool | None = None
    transaction_id: str | None = Field(default=None, max_length=64)
    subject_id: str | None = Field(default=None, max_length=64)
    expected_scope_token: str | None = Field(default=None, max_length=64)
    resolve_fact_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence: EvidenceInput | None = None


class FactDecisionRead(_CamelModel):
    id: str
    target_id: str
    decision: str
    reviewer_id: str
    reviewer_role: str
    created_at: str
    previous_value: Any
    new_value: Any
    reason: str | None
    resolved_fact_ids: list[str]


class FactHistoryRead(_CamelModel):
    items: list[FactRead]
    decisions: list[FactDecisionRead]
    page: PageInfo

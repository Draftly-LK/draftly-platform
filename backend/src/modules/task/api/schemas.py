"""Wire contract for the checklist module.

The read model exposes all seven statuses plus the derived lifecycle, because
the checklist is the matter's home navigation and each dimension answers a
different lawyer question (§11.2).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _StrictCamel(_Camel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class SatisfactionDecisionRequest(_StrictCamel):
    """Any subset of the six settable dimensions.

    ``resolution`` deliberately cannot be ``SATISFIED``: that value is computed
    from the requirement's policy, and the service rejects the attempt (§5.4).
    """

    applicability: str | None = None
    collection: str | None = None
    digital_review: str | None = None
    currency: str | None = None
    consistency: str | None = None
    resolution: str | None = None
    reason: str | None = None
    assigned_to: str | None = None


class OriginalInspectionRequest(_StrictCamel):
    """The reviewer is the authenticated actor and is not accepted here."""

    method: str = Field(min_length=1, max_length=128)
    location: str | None = None
    note: str | None = None


class LinkDocumentRequest(_StrictCamel):
    detected_document_id: str
    evidence_reference_ids: list[str] = Field(default_factory=list)
    lawyer_confirmed: bool = False
    note: str | None = None


class SatisfactionLinkRead(_Camel):
    id: str
    checklist_item_id: str
    detected_document_id: str
    digital_review: str
    evidence_reference_ids: list[str]
    reviewed_by: str | None
    reviewed_at: str | None
    review_note: str | None
    superseded_by_link_id: str | None
    is_live: bool
    created_at: str


class OriginalInspectionRead(_Camel):
    reviewer_id: str
    inspected_at: str
    method: str
    location: str | None
    note: str | None


class ChecklistItemRead(_Camel):
    id: str
    requirement_definition_id: str
    module_definition_id: str
    inclusion_reason: str
    inclusion_trigger_id: str | None
    label_key: str
    explanation_key: str
    mandatory_basis: str
    group: str
    source_record_ids: list[str]
    accepted_document_class_ids: list[str]
    may_be_satisfied_by_combined_document: bool
    physical_original_policy: str
    waivable: bool
    local_authority_id: str | None
    # The seven orthogonal statuses (§5.4)
    applicability: str
    collection: str
    digital_review: str
    physical_original: str
    currency: str
    consistency: str
    resolution: str
    # Derived, never stored as truth (§10.4)
    lifecycle: str
    computed_resolution: str
    blocks_approval: bool
    live_link_count: int
    applicability_reason: str | None
    original_inspection: OriginalInspectionRead | None
    assigned_to: str | None
    due_at: str | None
    version: int


class ChecklistRead(_Camel):
    snapshot_id: str
    matter_id: str
    fingerprint: str
    rule_pack_version: str
    compiler_version: str
    taxonomy_version: str
    checklist_version: str
    module_definition_ids: list[str]
    supersedes_id: str | None
    created_at: str
    items: list[ChecklistItemRead]
    blocking_requirement_ids: list[str]

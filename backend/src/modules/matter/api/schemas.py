"""Wire contract for the matter module.

Domain objects are never serialised directly (api-conventions §9). Every field
that is a legal state is a closed enum on the wire, so the frontend can switch
on it instead of parsing prose.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _StrictCamel(_Camel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# ── Requests ─────────────────────────────────────────────────────────────────


class CreateMatterRequest(_StrictCamel):
    """Creation never accepts a subtype: the exact instrument is a lawyer's
    decision made after routing, not a field on the create form (§12.4)."""

    reference: str = Field(min_length=1, max_length=128)
    client_reference: str | None = Field(default=None, max_length=128)
    instrument_language: Literal["en", "si", "ta"] = "en"
    local_authority_id: str | None = None
    #: Only set by the migration path for a record from the retired M2 vocabulary.
    legacy_matter_type: Literal["transfer", "gift", "lease", "mortgage", "other"] | None = None


class SaveAnswerRequest(_StrictCamel):
    value: Any = None
    #: True only when the responsible lawyer is answering, not when a model
    #: proposed the value. The server records provenance either way (§4.4).
    lawyer_confirmed: bool = False
    reason: str | None = None
    inferred_from_fact_ids: list[str] = Field(default_factory=list)


class ConfirmSubtypeRequest(_StrictCamel):
    subtype_id: str
    declared_legal_basis: str | None = None


# ── Reads ────────────────────────────────────────────────────────────────────


class MatterRead(_Camel):
    id: str
    reference: str
    client_reference: str | None
    responsible_lawyer_id: str
    regime_id: str
    family_id: str | None
    subtype_id: str | None
    subtype_decision_status: str
    legacy_matter_type: str | None
    lifecycle_status: str
    state: str
    automation_scope: str
    title_status: str
    parcel_kind: str
    disposition_scope: str
    dispute_stage: str
    instrument_language: str
    local_authority_id: str | None
    active_checklist_snapshot_id: str | None
    party_contexts: list[str]
    activated_conditional_module_ids: list[str]
    automation_exclusion_reason_keys: list[str]
    created_at: str
    updated_at: str
    version: int


class PageInfo(_Camel):
    next_cursor: str | None
    has_more: bool
    limit: int


class MatterListRead(_Camel):
    items: list[MatterRead]
    page: PageInfo


class IntakeAnswerRead(_Camel):
    id: str
    question_definition_id: str
    value: Any
    status: str
    answered_by: str | None
    answer_reason: str | None
    supersedes_id: str | None
    inferred_from_fact_ids: list[str]
    created_at: str


class GateRead(_Camel):
    """One evaluated eligibility predicate or stop condition."""

    id: str
    satisfied: bool
    severity: str
    blocker_kind: str
    reason_key: str
    source_record_ids: list[str]
    is_v0_predicate: bool


class RoutingRead(_Camel):
    matter: MatterRead
    automation_scope: str
    gates: list[GateRead]
    unmet_gate_ids: list[str]
    statutory_blocker_ids: list[str]
    next_question_ids: list[str]
    activated_conditional_module_ids: list[str]


class ChecklistItemRead(_Camel):
    requirement_definition_id: str
    module_definition_id: str
    inclusion_reason: str
    inclusion_trigger_id: str | None
    label_key: str
    explanation_key: str
    mandatory_basis: str
    group: str
    applicability: str
    source_record_ids: list[str]
    accepted_document_class_ids: list[str]
    may_be_satisfied_by_combined_document: bool
    physical_original_policy: str
    currency_max_age_days: int | None
    unsatisfied_severity: str
    unsatisfied_blocker_kind: str
    waivable: bool
    local_authority_id: str | None


class ChecklistDeltaRead(_Camel):
    added: list[str]
    removed: list[str]
    changed: list[dict[str, str]]
    retained_after_review: list[str]


class ChecklistSnapshotRead(_Camel):
    snapshot_id: str
    matter_id: str
    fingerprint: str
    rule_pack_versions: dict[str, str]
    module_definition_ids: list[str]
    items: list[ChecklistItemRead]
    delta: ChecklistDeltaRead | None

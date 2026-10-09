"""Wire contract for the drafting module.

Every field carries its whole evidence chain — fact id, fact version, evidence
reference ids, transformation, reviewer, and the template's own field/schema
version — because §9.3 makes those part of the field rather than metadata about
it. A lawyer must be able to see what a value rests on before signing the
instrument that carries it.

``displayValue`` is what a working draft renders: the value, or the §9.4
``[[UNRESOLVED: <field_id>]]`` token. It is never an empty string.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _StrictCamel(_Camel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class PageInfo(_Camel):
    next_cursor: str | None = None
    has_more: bool = False
    limit: int = 50


class FormScopeRead(_StrictCamel):
    transaction_id: str = Field(min_length=1, max_length=64)
    association_version: int = Field(ge=1)
    parcel_subject_id: str | None = Field(default=None, max_length=64)
    transferor_subject_id: str | None = Field(default=None, max_length=64)
    transferee_subject_id: str | None = Field(default=None, max_length=64)


class GenerateFormRequest(_StrictCamel):
    """Nothing legal is accepted from the client.

    ``templateId`` selects between the templates the *confirmed subtype* already
    permits — the prescribed instrument and its operational companions. It can
    never introduce one the subtype does not select (§9.1).
    """

    template_id: str | None = None
    scope: FormScopeRead | None = None
    predecessor_form_id: str | None = Field(default=None, max_length=64)


class FieldDecisionRequest(_StrictCamel):
    """One recorded decision about one field binding.

    The reviewer is the authenticated actor and is not accepted here. ``value``
    is only read for ``CORRECT``, and only on a template field that permits
    lawyer-authored text (§9.4).
    """

    field_id: str = Field(min_length=1, max_length=128)
    action: str
    value: str | None = None
    reason: str | None = None


class MarkStaleRequest(_StrictCamel):
    """Re-evaluate the form against its current inputs.

    ``reason`` declares the one upstream change this module cannot observe — a
    checklist recompile. Fact and template staleness are always recomputed
    server-side and take precedence, so a declared reason can never talk a form
    out of the staleness it actually has.
    """

    reason: str | None = None


class FactCandidateRead(_Camel):
    """One side of a §9.4 conflict, shown beside the other, never chosen for."""

    fact_id: str
    fact_type_id: str
    value: Any
    version: int
    status: str
    evidence_reference_ids: list[str]
    model_reported_confidence: float | None


class FormFieldRead(_Camel):
    id: str
    field_id: str
    label_key: str
    section_key: str | None
    order: int
    critical: bool
    required: bool
    #: The value, or the §9.4 unresolved token. Never blank.
    display_value: str
    rendered_value: str | None
    unresolved_reason: str | None
    missing_cause: str | None = None
    fact_id: str | None
    fact_version: int | None
    evidence_reference_ids: list[str]
    transformation_id: str | None
    allowed_transformation_ids: list[str]
    validation_rule_ids: list[str]
    lawyer_authored_allowed: bool
    human_confirmation_required: bool
    #: §9.3 — a high-confidence non-critical prefill, badged as such until a
    #: lawyer decides it. Never true of a value that came from a confirmed fact.
    ai_suggested: bool
    #: Populated, but no lawyer has decided this field yet. True for a prefill
    #: and for a confirmed-fact value alike: §9.3 needs both confirmed.
    awaiting_confirmation: bool
    review_decision_id: str | None
    reviewed_by: str | None
    reviewed_at: str | None
    #: Populated only for a ``FACT_CONFLICTED`` field.
    conflicting_candidates: list[FactCandidateRead]


class PreflightItemRead(_Camel):
    code: str
    subject_id: str
    explanation_key: str
    #: The earliest gate this item stops. A later gate implies the earlier ones.
    gate: str
    blocking: bool


class PreflightRead(_Camel):
    form_id: str
    template_id: str
    template_version: str
    rule_pack_version: str
    blocking: list[PreflightItemRead]
    warnings: list[PreflightItemRead]
    review_ready: bool
    approval_ready: bool
    #: False for every form in this repository: no template here is a
    #: lawyer-approved production rendering (§9.5).
    registration_ready: bool
    template_registration_ready_capable: bool
    #: §9.4 — the working draft carries this on every page.
    watermark_key: str
    evaluated_at: str


class GeneratedFormRead(_Camel):
    id: str
    matter_id: str
    template_id: str
    template_version: str
    title_key: str
    form_number: str
    namespace: str
    form_version: int
    state: str
    subtype_id: str
    rule_pack_version: str
    draft_artifact_hash: str | None
    approved_artifact_hash: str | None
    approval_id: str | None
    stale_reason: str | None
    scope: FormScopeRead | None = None
    predecessor_form_id: str | None = None
    known_source_defect_keys: list[str]
    fields: list[FormFieldRead]
    preflight: PreflightRead
    created_at: str
    updated_at: str
    version: int


class GeneratedFormSummaryRead(_Camel):
    """List projection — no fields and no preflight, so a page stays cheap."""

    id: str
    matter_id: str
    template_id: str
    template_version: str
    form_version: int
    state: str
    subtype_id: str
    rule_pack_version: str
    draft_artifact_hash: str | None
    approved_artifact_hash: str | None
    approval_id: str | None
    stale_reason: str | None
    scope: FormScopeRead | None = None
    predecessor_form_id: str | None = None
    created_at: str
    updated_at: str
    version: int


class GeneratedFormListRead(_Camel):
    items: list[GeneratedFormSummaryRead]
    page: PageInfo

"""Wire contract for approval, export, and registration events.

Two shapes here exist to stop a client asserting a legal conclusion.

An approval request carries a declaration version and the warnings the lawyer
disposed of, and nothing else. There is no form version, no template version, no
fact list, and no hash: every one of those is read from the server's own record
of the form (§9.6).

An export response always says what it is not. ``registrationReady`` is false
for every export this repository can produce, ``watermarked`` says whether the
§9.4 draft notice travels with it, and ``artifactKind`` names a *record* — no
PDF, no Word file, and no page layout is produced, because no template here has
a lawyer-approved production rendering (§9.5).
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


class ApproveFormRequest(_StrictCamel):
    """The lawyer's two contributions to the record.

    ``disposedWarningIds`` must name exactly the warnings the server computed:
    §9.6 requires the approval to carry the unresolved warnings that were
    accepted, and a list that does not match them is not a record of what was
    accepted.
    """

    disposed_warning_ids: list[str] = Field(default_factory=list)
    #: The declaration the interface displayed. Defaulted server-side to the
    #: current version rather than accepted as free text.
    declaration_version: str | None = None


class ExportFormRequest(_StrictCamel):
    """``format`` selects a record, never a document. See the module docstring."""

    format: str


class RecordRegistrationEventRequest(_StrictCamel):
    """One official act. The recorder is the authenticated actor, not the body."""

    event_type: str
    #: ISO date. A day, not an instant: the s. 45(1) clock counts days.
    event_date: str
    evidence_reference_ids: list[str] = Field(default_factory=list)
    generated_form_id: str | None = None
    day_book_reference: str | None = None
    registry_office: str | None = None
    result_note: str | None = None


class ApprovalGateItemRead(_Camel):
    id: str
    code: str
    subject_id: str
    explanation_key: str
    blocking: bool


class ApprovalGateRead(_Camel):
    form_id: str
    template_id: str
    template_version: str
    rule_pack_version: str
    blocking: list[ApprovalGateItemRead]
    warnings: list[ApprovalGateItemRead]
    approval_ready: bool
    #: False for every form in this repository (§9.5).
    registration_ready: bool
    template_registration_ready_capable: bool


class ApprovalRead(_Camel):
    id: str
    matter_id: str
    target_type: str
    target_id: str
    target_version: str
    approver_id: str
    approver_workflow_role: str
    declaration_version: str
    #: ``pending-sha256:`` while the prescribed wording is unregistered — the
    #: declaration text is human-owned and is not authored in this repository.
    declaration_text_hash: str
    snapshot_hash: str
    confirmed_fact_hash: str
    warning_disposition_ids: list[str]
    template_id: str
    template_version: str
    rule_pack_version: str
    revoked_by_approval_id: str | None
    created_at: str


class ApprovalCreatedRead(_Camel):
    approval: ApprovalRead
    gate: ApprovalGateRead


class FormExportRead(_Camel):
    id: str
    matter_id: str
    generated_form_id: str
    approval_id: str | None
    #: A record kind, not a file type. No page is produced (§9.5).
    artifact_kind: str
    artifact_hash: str
    artifact_key: str
    #: §9.4 — the draft notice travels on every page of a working draft.
    watermarked: bool
    watermark_key: str | None
    #: False for every export in this repository.
    registration_ready: bool
    registration_ready_blocked_by: list[str]
    manifest: dict[str, Any]
    created_by: str
    created_at: str


class FormExportListRead(_Camel):
    items: list[FormExportRead]
    page: PageInfo


class PresentationDeadlineRead(_Camel):
    """The s. 45(1) forwarding task. Always provisional (§16.4)."""

    attested_on: str
    due_on: str
    working_days: int
    basis_key: str
    provisional: bool
    unverified_reason_key: str


class RegistrationEventRead(_Camel):
    id: str
    matter_id: str
    generated_form_id: str | None
    event_type: str
    event_date: str
    evidence_reference_ids: list[str]
    day_book_reference: str | None
    registry_office: str | None
    result_note: str | None
    recorded_by: str
    created_at: str


class RegistrationEventCreatedRead(_Camel):
    event: RegistrationEventRead
    #: The §10.1 state this act implies. ``null`` for an attestation: it is an
    #: act on the instrument, not a registry act on the matter.
    implied_matter_state: str | None
    #: Present only for a confirmed attestation date (§17).
    deadline: PresentationDeadlineRead | None


class RegistrationEventListRead(_Camel):
    items: list[RegistrationEventRead]
    page: PageInfo


class ApprovalListRead(_Camel):
    """Every approval of one form, newest first, plus the live gate.

    The gate travels with the history because it is where the interface gets the
    warning ids an approval has to dispose of (§9.6): the lawyer sees what is
    outstanding on the same read that shows what has already been signed.
    """

    items: list[ApprovalRead]
    page: PageInfo
    gate: ApprovalGateRead
    #: The approval currently in force, if any. ``null`` once one is superseded.
    current_approval_id: str | None

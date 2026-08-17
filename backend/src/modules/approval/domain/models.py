"""Approval, export, and registration-event entities.

All three are **append-only records of human acts**. None of them is a
projection that can be recomputed, and none may be edited after the fact:

``Approval`` is the §9.6 signed application event. It is frozen, and the single
mutable field in the whole aggregate is ``revoked_by_approval_id`` — written
only when a *later* approval supersedes it, which is why revocation cannot exist
without the approval that caused it.

``FormExport`` records that a projection of a snapshot left the system. It is
not an instrument and never changes the legal state of anything (§9.6: "Export
is not attestation, presentation, or registration").

``RegistrationEvent`` records one official act, dated by the human who observed
it and backed by evidence. Time never creates one.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from src.modules.content_governance.contracts import (
    ApprovalTargetType,
    RegistrationEventType,
    RtaWorkflowRole,
)

#: The same governed key the drafting module stamps on a working draft. §9.4
#: prescribes the English wording; the wording itself is product copy owned by
#: the team, so what travels between services is the key.
DRAFT_WATERMARK_KEY = "rta.form.watermark.draft_not_approved"

#: Every artifact this module produces is an internal review record, never a
#: submittable instrument. Carried on every manifest so a downstream renderer
#: cannot lose the qualification on the way to a page.
INTERNAL_REVIEW_NOTICE_KEY = "rta.form.export.internal_review_artifact_only"


class ExportFormat(str, enum.Enum):
    """What this module can actually produce today.

    Deliberately not ``PDF`` or ``DOCX``. §9.6 describes an approved PDF with
    stable pagination and an optional Word version, and neither exists here: no
    template in this repository has an approved production layout (§9.5), so a
    rendered page would be a fabricated one. Each member names a *record*, and a
    consumer that wants a document has to be told that none was produced.
    """

    #: The §9.4 internal-review projection of an unapproved draft. Watermarked.
    WORKING_DRAFT_MANIFEST = "WORKING_DRAFT_MANIFEST"
    #: The §9.6 projection of an approved snapshot, pinned to its approval.
    APPROVED_MANIFEST = "APPROVED_MANIFEST"
    #: The §9.6 "evidence/field audit schedule for the file" — the field-to-fact
    #: -to-evidence chain, for the file rather than for the registry.
    EVIDENCE_SCHEDULE = "EVIDENCE_SCHEDULE"


@dataclass(frozen=True)
class Approval:
    """One §9.6 signed application event, immutable once written.

    ``snapshot_hash`` and ``confirmed_fact_hash`` are computed by the server from
    the form snapshot it read, never from the request: an approval that pinned a
    client-supplied version would pin whatever the client wished had been true.
    """

    id: str
    user_id: str
    matter_id: str
    target_type: ApprovalTargetType
    target_id: str
    #: The form version approved, as a string per §12.2 ``Approval``.
    target_version: str
    approver_id: str
    approver_workflow_role: RtaWorkflowRole
    declaration_version: str
    declaration_text_hash: str
    snapshot_hash: str
    confirmed_fact_hash: str
    template_id: str
    template_version: str
    rule_pack_version: str
    created_at: datetime
    #: The warnings the lawyer positively disposed of when signing (§9.6).
    warning_disposition_ids: tuple[str, ...] = field(default_factory=tuple)
    #: Written only by a later approval of the same target. The one field of
    #: this record that is ever updated, and it can never be cleared.
    revoked_by_approval_id: str | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_by_approval_id is not None


@dataclass(frozen=True)
class FormExport:
    """One projection of a form that left the system (§9.6).

    ``registration_ready`` is stored rather than derived at read time because it
    records what was true when the export was taken. It is false for every
    export in this repository: no template here is a lawyer-approved production
    rendering (§9.5).
    """

    id: str
    user_id: str
    matter_id: str
    generated_form_id: str
    approval_id: str | None
    export_format: ExportFormat
    artifact_hash: str
    #: Where the artifact lives. Today the manifest in this row *is* the
    #: artifact — no bytes are written, because no storage port exists and no
    #: page may be fabricated — so the key names the row, not an object.
    artifact_key: str
    watermarked: bool
    registration_ready: bool
    manifest: dict[str, Any]
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class RegistrationEvent:
    """One official act, recorded by a human from evidence (§9.6, §10.1).

    ``event_date`` is a date and not a timestamp on purpose: what the registry
    records, and what the s. 45(1) clock runs from, is a day.
    """

    id: str
    user_id: str
    matter_id: str
    generated_form_id: str | None
    event_type: RegistrationEventType
    event_date: date
    recorded_by: str
    created_at: datetime
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    day_book_reference: str | None = None
    registry_office: str | None = None
    result_note: str | None = None


__all__ = [
    "DRAFT_WATERMARK_KEY",
    "INTERNAL_REVIEW_NOTICE_KEY",
    "Approval",
    "ExportFormat",
    "FormExport",
    "RegistrationEvent",
]

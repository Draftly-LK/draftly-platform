"""The approval, export, and registration rules. This file is the deliverable.

Six rules carry the legal safety of this module, and each is a named function
here rather than a condition buried in the service:

1. **Only the responsible lawyer for that matter may approve.**
   `require_responsible_lawyer` re-asserts locally what the capability map
   already encodes, because §12.5's "no system/service account may impersonate a
   human approval" is the one invariant that must not depend on a table lookup
   staying correct.
2. **An approval pins an exact snapshot.** `approval_snapshot_hash` and
   `confirmed_fact_hash` are computed from the form snapshot the server read.
   Nothing in either payload comes from the request.
3. **Approval is refused while preflight is unclean.** `evaluate_approval_gate`
   consults the form, the fact tier, the issue gates, and the checklist
   separately — §14.6 lists them as separate stop conditions — and
   `guard_approval` refuses on any of them. A statutory blocker gets its own
   refusal because no role can override it.
4. **Export is not registration.** `build_manifest` produces a record, not a
   page, and `matter_state_for_export` can return ``EXPORTED`` and nothing else.
   `registration_ready` is a conjunction that includes the template's own
   capability, which is False for every template in this repository (§9.5).
5. **Attestation, presentation, and registration are three separate events**,
   each needing a human, a date, and evidence (`guard_registration_event`). The
   s. 45(1) clock is started only by a confirmed attestation date, and
   `presentation_deadline` marks its own answer provisional because the Sri
   Lankan public-holiday calendar is not verified (§16.4).
6. **A correction after approval prevents reuse of the old approval.**
   `superseded_bindings` compares each pinned fact against the tier's current
   confirmed value, so a correction is detected here even if nobody re-evaluated
   the form (§10.5, §17).
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from src.modules.approval.domain.errors import (
    ApprovalFormNotReviewableError,
    ApprovalFormStaleError,
    ApprovalPreflightUncleanError,
    ApprovalStatutoryBlockerError,
    ApprovalWarningsNotDisposedError,
    ApproverNotResponsibleLawyerError,
    RegistrationAlreadyRecordedError,
    RegistrationDayBookReferenceRequiredError,
    RegistrationEventDateInFutureError,
    RegistrationEventFormRequiredError,
    RegistrationEvidenceRequiredError,
    RegistrationOutOfOrderError,
    RegistrationResultNoteRequiredError,
)
from src.modules.approval.domain.models import (
    DRAFT_WATERMARK_KEY,
    INTERNAL_REVIEW_NOTICE_KEY,
    Approval,
    ExportFormat,
    RegistrationEvent,
)
from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    CAP_FORM_APPROVE,
    FormTemplateDefinition,
    GeneratedFormState,
    MatterState,
    RegistrationEventType,
    RtaWorkflowRole,
    TemplateStatus,
)
from src.modules.draft.contracts import BoundFact, FormSnapshot
from src.modules.matter.contracts import (
    MatterAccessSummary,
    require_rta_capability,
    workflow_role_for,
)
from src.modules.verification.contracts import FactTierSummary
from src.platform.errors import NotFoundError

#: The states a form may be approved from (§10.7). ``GENERATED_DRAFT`` and
#: ``UNRESOLVED`` are absent because the review has not happened yet, and the
#: approved and stale states are absent because the snapshot is already closed.
APPROVABLE_STATES: frozenset[GeneratedFormState] = frozenset(
    {
        GeneratedFormState.REVIEW_READY,
        GeneratedFormState.LAWYER_REVIEWED,
        GeneratedFormState.APPROVAL_PENDING,
    }
)

_STALE_STATES: frozenset[GeneratedFormState] = frozenset(
    {GeneratedFormState.STALE_TEMPLATE, GeneratedFormState.STALE_AFTER_APPROVAL}
)

#: s. 45(1) — the attestor forwards the instrument within seven working days of
#: attestation. The number is statutory; the calendar it is counted on is not
#: yet verified, which is what `presentation_deadline` reports.
FORWARDING_WORKING_DAYS = 7

#: §16.4 open question 5. Travels with every computed deadline so no interface
#: can present the date as final.
HOLIDAY_CALENDAR_UNVERIFIED_KEY = "rta.registration.deadline.holiday_calendar_unverified"
FORWARDING_DEADLINE_BASIS_KEY = "rta.registration.deadline.basis.s45_1"

#: Events that record an act performed on one identified instrument. A recorded
#: attestation with no instrument would start the s. 45(1) clock on nothing.
_FORM_REQUIRED_EVENTS: frozenset[RegistrationEventType] = frozenset(
    {RegistrationEventType.ATTESTED, RegistrationEventType.REGISTERED}
)

#: Presentation, in either of the two shapes a registry records it in.
_PRESENTATION_EVENTS: frozenset[RegistrationEventType] = frozenset(
    {RegistrationEventType.PRESENTED, RegistrationEventType.DAY_BOOK_ENTERED}
)


# ── Rule 1: who may approve (§12.5) ──────────────────────────────────────────


def require_responsible_lawyer(
    *, account_role: str, actor_id: str, matter: MatterAccessSummary
) -> RtaWorkflowRole:
    """Authorize an approval, or raise.

    Three checks in this order, and the order is the point.

    An actor with no standing on the matter gets 404, so a stranger cannot learn
    that the matter exists. An actor with standing but a workflow role other than
    ``RESPONSIBLE_LAWYER`` is refused **here**, before the capability map is
    consulted — this is the check that keeps holding if someone ever widens
    `RTA_CAPABILITY_MAP`, because §12.5 makes approval personal to the lawyer
    responsible for this file and it must not depend on a table staying correct.
    The map is then consulted anyway: this function narrows who may ask, it never
    grants.
    """
    role = workflow_role_for(account_role=account_role, actor_id=actor_id, matter=matter)
    if role is None or matter.user_id != actor_id:
        raise NotFoundError("The requested matter was not found.")
    if role is not RtaWorkflowRole.RESPONSIBLE_LAWYER:
        raise ApproverNotResponsibleLawyerError(
            capability=CAP_FORM_APPROVE, workflowRole=role.value
        )
    return require_rta_capability(
        account_role=account_role,
        actor_id=actor_id,
        matter=matter,
        capability=CAP_FORM_APPROVE,
    )


# ── Rule 2: what an approval pins (§9.6) ─────────────────────────────────────


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _binding_payload(bindings: Sequence[BoundFact]) -> list[dict[str, Any]]:
    return [
        {
            "fieldId": binding.field_id,
            "factId": binding.fact_id,
            "factVersion": binding.version,
            "evidenceReferenceIds": list(binding.evidence_reference_ids),
        }
        for binding in sorted(bindings, key=lambda b: b.field_id)
    ]


def approval_snapshot_hash(snapshot: FormSnapshot) -> str:
    """Digest of everything an approval certifies about one form.

    The form's ``state`` and ``stale_reason`` are deliberately excluded: both
    change *because* of the approval or after it, and an approval whose hash
    stopped matching the moment it was written would be useless for detecting
    the changes it exists to detect. Content lives in ``draft_artifact_hash``,
    which the drafting module recomputes on every binding change.
    """
    return _digest(
        {
            "formId": snapshot.form_id,
            "formVersion": snapshot.form_version,
            "templateId": snapshot.template_id,
            "templateVersion": snapshot.template_version,
            "rulePackVersion": snapshot.rule_pack_version,
            "subtypeId": snapshot.subtype_id,
            "draftArtifactHash": snapshot.draft_artifact_hash,
            "unresolvedFieldIds": sorted(snapshot.unresolved_field_ids),
            "criticalFactBindings": _binding_payload(snapshot.critical_fact_bindings),
        }
    )


def confirmed_fact_hash(snapshot: FormSnapshot) -> str:
    """Digest of the confirmed critical facts, §9.6's "list/hash".

    Kept separate from the snapshot hash so an auditor can answer "were these
    the same facts?" without also asking "was this the same template?".
    """
    return _digest({"criticalFactBindings": _binding_payload(snapshot.critical_fact_bindings)})


# ── Rule 3: the approval gate (§9.4, §14.6) ──────────────────────────────────


class ApprovalGateCode(str, enum.Enum):
    """Why this form may not be approved, in §14.6's vocabulary."""

    UNRESOLVED_REQUIRED_FIELD = "UNRESOLVED_REQUIRED_FIELD"
    CRITICAL_FIELD_UNPOPULATED = "CRITICAL_FIELD_UNPOPULATED"
    CRITICAL_FIELD_EVIDENCE_MISSING = "CRITICAL_FIELD_EVIDENCE_MISSING"
    CRITICAL_FACT_UNCONFIRMED = "CRITICAL_FACT_UNCONFIRMED"
    OPEN_STATUTORY_BLOCKER = "OPEN_STATUTORY_BLOCKER"
    OPEN_BLOCKING_ISSUE = "OPEN_BLOCKING_ISSUE"
    ISSUE_BLOCKS_APPROVAL = "ISSUE_BLOCKS_APPROVAL"
    CHECKLIST_REQUIREMENT_BLOCKING = "CHECKLIST_REQUIREMENT_BLOCKING"
    FORM_STALE = "FORM_STALE"
    FORM_NOT_REVIEWABLE = "FORM_NOT_REVIEWABLE"
    # Warnings — recorded and disposed of, never silently ignored (§9.6).
    UNRESOLVED_OPTIONAL_FIELD = "UNRESOLVED_OPTIONAL_FIELD"
    TEMPLATE_NOT_VALIDATED = "TEMPLATE_NOT_VALIDATED"
    SOURCE_REVERIFICATION_REQUIRED = "SOURCE_REVERIFICATION_REQUIRED"
    TEMPLATE_SOURCE_DEFECT = "TEMPLATE_SOURCE_DEFECT"


_WARNING_CODES: frozenset[ApprovalGateCode] = frozenset(
    {
        ApprovalGateCode.UNRESOLVED_OPTIONAL_FIELD,
        ApprovalGateCode.TEMPLATE_NOT_VALIDATED,
        ApprovalGateCode.SOURCE_REVERIFICATION_REQUIRED,
        ApprovalGateCode.TEMPLATE_SOURCE_DEFECT,
    }
)

#: Warnings that do not stop an approval but do stop a registration-ready
#: export. §9.5 lets a lawyer approve the content of a transcribed template; it
#: does not let that transcription be submitted to a registry.
_REGISTRATION_BLOCKING_WARNINGS: frozenset[ApprovalGateCode] = frozenset(
    {
        ApprovalGateCode.TEMPLATE_NOT_VALIDATED,
        ApprovalGateCode.SOURCE_REVERIFICATION_REQUIRED,
    }
)

#: Report order, fixed so two runs over the same state produce the same list. A
#: disposition list is diffed against this one, and a set that reshuffles is a
#: set a lawyer cannot check.
_ORDER: dict[ApprovalGateCode, int] = {code: index for index, code in enumerate(ApprovalGateCode)}


@dataclass(frozen=True)
class ApprovalGateItem:
    code: ApprovalGateCode
    subject_id: str
    explanation_key: str
    blocking: bool

    @property
    def id(self) -> str:
        """Stable identifier a disposition names (§9.6)."""
        return f"{self.code.value}:{self.subject_id}"


@dataclass(frozen=True)
class ApprovalGateResult:
    """A deterministic report over the form, the facts, the issues, and the checklist."""

    form_id: str
    template_id: str
    template_version: str
    rule_pack_version: str
    items: tuple[ApprovalGateItem, ...]
    #: Read from the template definition, never asserted. False for every
    #: template in this repository (§9.5).
    template_registration_ready_capable: bool

    @property
    def blocking(self) -> tuple[ApprovalGateItem, ...]:
        return tuple(item for item in self.items if item.blocking)

    @property
    def warnings(self) -> tuple[ApprovalGateItem, ...]:
        return tuple(item for item in self.items if not item.blocking)

    @property
    def warning_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.warnings)

    @property
    def approval_ready(self) -> bool:
        return not self.blocking

    @property
    def registration_ready(self) -> bool:
        """§9.4 — impossible while anything blocks or the template cannot back one."""
        return self.template_registration_ready_capable and not self.blocking


def _item(code: ApprovalGateCode, subject_id: str) -> ApprovalGateItem:
    return ApprovalGateItem(
        code=code,
        subject_id=subject_id,
        explanation_key=f"rta.approval.gate.{code.value.lower()}",
        blocking=code not in _WARNING_CODES,
    )


def source_reverification_required(template: FormTemplateDefinition) -> bool:
    """§9.5 — whether the template's own source still needs re-verification.

    True while the record is a transcription, while the official page image is
    not held, or while a known defect of the source text is unresolved. The same
    three conditions the drafting module reports; they belong on
    `FormTemplateDefinition` beside ``registration_ready_capable`` so the two
    modules cannot drift, which is a rule-pack change and not one this module
    may make.
    """
    return (
        template.status is not TemplateStatus.VALIDATED
        or template.official_artifact_source_record_id is None
        or bool(template.known_source_defect_keys)
    )


def evaluate_approval_gate(
    *,
    snapshot: FormSnapshot,
    template: FormTemplateDefinition,
    facts: FactTierSummary,
    issue_gates: IssueGateSummary,
    blocking_requirement_ids: Sequence[str],
) -> ApprovalGateResult:
    """Decide whether this exact snapshot may be approved.

    Recomputed here rather than trusted from the drafting module's own report:
    approval is the act the gate exists to stop, so the module that performs it
    reads the four sources itself.
    """
    mappings = {mapping.field_id: mapping for mapping in template.field_mappings}
    bound = {binding.field_id: binding for binding in snapshot.critical_fact_bindings}
    items: list[ApprovalGateItem] = []
    if not snapshot.scope_current:
        items.append(_item(ApprovalGateCode.FORM_STALE, snapshot.form_id))
    items.extend(
        _item(ApprovalGateCode.FORM_NOT_REVIEWABLE, field_id)
        for field_id in snapshot.unreviewed_field_ids
    )
    items.extend(
        _item(ApprovalGateCode.FORM_STALE, field_id)
        for field_id in superseded_bindings(snapshot, template, facts)
    )

    for field_id in snapshot.unresolved_field_ids:
        mapping = mappings.get(field_id)
        # A field the template no longer declares is treated as required: an
        # unresolved token of unknown standing is not something to wave through.
        required = mapping is None or mapping.required
        items.append(
            _item(
                ApprovalGateCode.UNRESOLVED_REQUIRED_FIELD
                if required
                else ApprovalGateCode.UNRESOLVED_OPTIONAL_FIELD,
                field_id,
            )
        )

    for mapping in template.field_mappings:
        if not (mapping.critical and mapping.required):
            continue
        binding = bound.get(mapping.field_id)
        if binding is None:
            # §9.3 — a critical field is populated only from a lawyer-confirmed
            # fact, so a required one with no binding is not merely blank.
            items.append(_item(ApprovalGateCode.CRITICAL_FIELD_UNPOPULATED, mapping.field_id))
        elif not binding.evidence_reference_ids:
            items.append(_item(ApprovalGateCode.CRITICAL_FIELD_EVIDENCE_MISSING, mapping.field_id))

    items.extend(
        _item(ApprovalGateCode.CRITICAL_FACT_UNCONFIRMED, fact_type_id)
        for fact_type_id in facts.unconfirmed_critical_fact_type_ids
    )
    items.extend(
        _item(ApprovalGateCode.OPEN_STATUTORY_BLOCKER, issue_id)
        for issue_id in issue_gates.open_statutory_blocker_ids
    )
    items.extend(
        _item(ApprovalGateCode.OPEN_BLOCKING_ISSUE, issue_id)
        for issue_id in issue_gates.open_blocking_issue_ids
    )
    if issue_gates.blocks_approval and not issue_gates.open_blocking_issue_ids:
        # The summary carries ids only for the blocking and statutory sets, so a
        # HIGH_RISK gate is reported against the matter rather than an invented id.
        items.append(_item(ApprovalGateCode.ISSUE_BLOCKS_APPROVAL, snapshot.matter_id))
    items.extend(
        _item(ApprovalGateCode.CHECKLIST_REQUIREMENT_BLOCKING, requirement_id)
        for requirement_id in blocking_requirement_ids
    )

    if snapshot.state in _STALE_STATES:
        items.append(_item(ApprovalGateCode.FORM_STALE, snapshot.stale_reason or snapshot.form_id))
    elif snapshot.state not in APPROVABLE_STATES:
        items.append(_item(ApprovalGateCode.FORM_NOT_REVIEWABLE, snapshot.state.value))

    if not template.registration_ready_capable:
        items.append(_item(ApprovalGateCode.TEMPLATE_NOT_VALIDATED, template.id))
    if source_reverification_required(template):
        items.append(_item(ApprovalGateCode.SOURCE_REVERIFICATION_REQUIRED, template.id))
    items.extend(
        _item(ApprovalGateCode.TEMPLATE_SOURCE_DEFECT, defect_key)
        for defect_key in template.known_source_defect_keys
    )

    return ApprovalGateResult(
        form_id=snapshot.form_id,
        template_id=template.id,
        template_version=snapshot.template_version,
        rule_pack_version=snapshot.rule_pack_version,
        items=tuple(sorted(items, key=lambda i: (_ORDER[i.code], i.subject_id))),
        template_registration_ready_capable=template.registration_ready_capable,
    )


def guard_approval(result: ApprovalGateResult, *, disposed_warning_ids: Sequence[str]) -> None:
    """Refuse an approval the gate does not permit.

    Ordered from the most specific refusal to the least, because the code is
    what the interface acts on: "this cannot be waived by anyone" and "your
    inputs moved" lead to different screens than "something is still open".
    """
    statutory = [
        item.subject_id
        for item in result.blocking
        if item.code is ApprovalGateCode.OPEN_STATUTORY_BLOCKER
    ]
    if statutory:
        raise ApprovalStatutoryBlockerError(openStatutoryBlockerIds=statutory)
    for item in result.blocking:
        if item.code is ApprovalGateCode.FORM_STALE:
            raise ApprovalFormStaleError(formId=result.form_id, staleReason=item.subject_id)
        if item.code is ApprovalGateCode.FORM_NOT_REVIEWABLE:
            raise ApprovalFormNotReviewableError(formId=result.form_id, state=item.subject_id)
    if result.blocking:
        raise ApprovalPreflightUncleanError(
            formId=result.form_id,
            blocking=[item.id for item in result.blocking],
        )

    expected = set(result.warning_ids)
    disposed = set(disposed_warning_ids)
    if expected != disposed:
        raise ApprovalWarningsNotDisposedError(
            missing=sorted(expected - disposed),
            unknown=sorted(disposed - expected),
        )


# ── Rule 6: a correction after approval (§10.5, §17) ─────────────────────────


def superseded_bindings(
    snapshot: FormSnapshot, template: FormTemplateDefinition, facts: FactTierSummary
) -> tuple[str, ...]:
    """Field ids whose pinned fact is no longer the tier's confirmed value.

    A correction writes a new fact id at a new version and supersedes the old
    one, so the pinned row is precisely the thing that has gone (§10.5). Checked
    against the *current* tier rather than against the form's recorded state,
    because a correction made after approval does not have to have passed
    through the drafting module's staleness sweep to have happened.
    """
    mappings = {mapping.field_id: mapping for mapping in template.field_mappings}
    moved: list[str] = []
    for binding in snapshot.critical_fact_bindings:
        mapping = mappings.get(binding.field_id)
        if mapping is None or mapping.fact_type_id is None:
            continue
        if snapshot.scope is not None:
            matches = [
                value
                for value in facts.scoped_confirmed
                if value.fact_id == binding.fact_id
                and value.transaction_id == snapshot.scope.transaction_id
            ]
            current = matches[0] if len(matches) == 1 and snapshot.scope_current else None
        else:
            current = facts.confirmed.get(mapping.fact_type_id)
        if (
            current is None
            or current.fact_id != binding.fact_id
            or current.version != binding.version
        ):
            moved.append(binding.field_id)
    return tuple(sorted(moved))


def approval_matches_snapshot(approval: Approval, snapshot: FormSnapshot) -> bool:
    """Whether this approval still pins the form as it stands."""
    return not approval.is_revoked and approval.snapshot_hash == approval_snapshot_hash(snapshot)


# ── Rule 4: export (§9.4, §9.6) ──────────────────────────────────────────────


def export_watermarked(export_format: ExportFormat, approval: Approval | None) -> bool:
    """§9.4 — anything that is not a projection of a current approval is a draft."""
    return export_format is not ExportFormat.APPROVED_MANIFEST or approval is None


def export_registration_ready(
    *, export_format: ExportFormat, approval: Approval | None, result: ApprovalGateResult
) -> bool:
    """§9.4 — a registration-ready export needs an approval *and* a real template.

    False for every export in this repository, and computed rather than hard
    coded so the answer changes by itself the day a lawyer-approved production
    rendering exists.
    """
    if export_format is not ExportFormat.APPROVED_MANIFEST or approval is None:
        return False
    return result.registration_ready


def build_manifest(
    *,
    snapshot: FormSnapshot,
    template: FormTemplateDefinition,
    export_format: ExportFormat,
    approval: Approval | None,
    result: ApprovalGateResult,
    watermarked: bool,
    registration_ready: bool,
) -> dict[str, Any]:
    """The exported record.

    Not a document. §9.5 leaves every template in this repository without an
    approved production rendering, so a laid-out page would be a fabricated one;
    what is produced instead is the binding record, its evidence chain, and the
    qualifications that travel with it. Deliberately free of a timestamp: the
    row records when, and a manifest that hashed the clock could never show that
    two exports of one snapshot are the same artifact.
    """
    manifest: dict[str, Any] = {
        "manifestVersion": "1",
        "kind": export_format.value,
        "noticeKey": INTERNAL_REVIEW_NOTICE_KEY,
        "formId": snapshot.form_id,
        "matterId": snapshot.matter_id,
        "formVersion": snapshot.form_version,
        "subtypeId": snapshot.subtype_id,
        "templateId": snapshot.template_id,
        "templateVersion": snapshot.template_version,
        "rulePackVersion": snapshot.rule_pack_version,
        "draftArtifactHash": snapshot.draft_artifact_hash,
        "knownSourceDefectKeys": list(template.known_source_defect_keys),
        "unresolvedFieldIds": sorted(snapshot.unresolved_field_ids),
        "criticalFactBindings": _binding_payload(snapshot.critical_fact_bindings),
        "registrationReady": registration_ready,
        "registrationReadyBlockedBy": sorted(
            {item.id for item in result.blocking}
            | {item.id for item in result.warnings if item.code in _REGISTRATION_BLOCKING_WARNINGS}
        ),
        "approvalId": approval.id if approval else None,
        "approvedSnapshotHash": approval.snapshot_hash if approval else None,
        "declarationVersion": approval.declaration_version if approval else None,
        # §9.4 — every page of a working draft carries the notice. No page is
        # produced here, so the renderer that eventually produces one is told
        # from the record rather than from a convention it has to remember.
        "watermark": ({"key": DRAFT_WATERMARK_KEY, "everyPage": True} if watermarked else None),
    }
    if export_format is ExportFormat.EVIDENCE_SCHEDULE:
        # §9.6 — the file's own audit schedule, not normally submitted.
        manifest["evidenceSchedule"] = [
            {
                "fieldId": binding.field_id,
                "factId": binding.fact_id,
                "factVersion": binding.version,
                "evidenceReferenceIds": list(binding.evidence_reference_ids),
            }
            for binding in sorted(snapshot.critical_fact_bindings, key=lambda b: b.field_id)
        ]
    return manifest


def export_artifact_hash(manifest: dict[str, Any]) -> str:
    """Digest over the manifest bytes. The manifest *is* the artifact today."""
    return _digest(manifest)


def export_artifact_key(export_id: str) -> str:
    """Where the artifact lives.

    ``inline:`` because it lives in this row: no bytes are written, there is no
    storage port yet, and a key that named an object store location would name
    an object that does not exist.
    """
    return f"inline:manifest/{export_id}"


def matter_state_for_export(
    export_format: ExportFormat, approval: Approval | None
) -> MatterState | None:
    """§10.1 — exporting an approved snapshot is the only export that moves anything.

    ``REGISTERED`` is unreachable from here by construction: §9.6 says export is
    not attestation, presentation, or registration, and §17 requires that export
    does not mark the matter registered.
    """
    if export_format is ExportFormat.APPROVED_MANIFEST and approval is not None:
        return MatterState.EXPORTED
    return None


# ── Rule 5: registration events (§9.6, §10.1, §17) ───────────────────────────


def matter_state_for_event(event_type: RegistrationEventType) -> MatterState | None:
    """§10.1 — presentation submits; only an official result registers.

    Attestation moves nothing: it is an execution event on the instrument, not a
    registry event on the matter, and the state machine has no state for it. A
    refusal or return leaves the matter where it is — the instrument is back
    with the lawyer, which is a task, not a state.
    """
    if event_type in _PRESENTATION_EVENTS:
        return MatterState.SUBMITTED
    if event_type is RegistrationEventType.REGISTERED:
        return MatterState.REGISTERED
    return None


def add_working_days(start: date, days: int) -> date:
    """Add working days, counting Monday to Friday only.

    Public holidays are **not** applied. There is no verified Sri Lankan
    holiday calendar in this repository (§16.4 open question 5), and quietly
    skipping a guessed set of holidays would produce a date that looks
    authoritative and is not. Every caller marks the result provisional.
    """
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


@dataclass(frozen=True)
class PresentationDeadline:
    """The s. 45(1) forwarding deadline, and why it is not final."""

    attested_on: date
    due_on: date
    working_days: int
    basis_key: str
    #: Always True today. The calculation is provisional until the holiday
    #: calendar is confirmed and a lawyer accepts the rule (§16.4).
    provisional: bool
    unverified_reason_key: str


def presentation_deadline(attested_on: date) -> PresentationDeadline:
    """The seven-working-day task, triggered only by a confirmed attestation date.

    Nothing else starts this clock — not export, not signature of a draft, not
    the passage of time (§9.6, §17). The date it returns is an operational
    prompt for the lawyer, never a legal conclusion.
    """
    return PresentationDeadline(
        attested_on=attested_on,
        due_on=add_working_days(attested_on, FORWARDING_WORKING_DAYS),
        working_days=FORWARDING_WORKING_DAYS,
        basis_key=FORWARDING_DEADLINE_BASIS_KEY,
        provisional=True,
        unverified_reason_key=HOLIDAY_CALENDAR_UNVERIFIED_KEY,
    )


def guard_registration_event(
    *,
    event_type: RegistrationEventType,
    event_date: date,
    today: date,
    evidence_reference_ids: Sequence[str],
    generated_form_id: str | None,
    day_book_reference: str | None,
    result_note: str | None,
    existing: Sequence[RegistrationEvent],
) -> None:
    """Refuse a registry record that is not a record of something observed."""
    if not evidence_reference_ids:
        raise RegistrationEvidenceRequiredError(eventType=event_type.value)
    if event_date > today:
        raise RegistrationEventDateInFutureError(eventType=event_type.value)
    if event_type in _FORM_REQUIRED_EVENTS and generated_form_id is None:
        raise RegistrationEventFormRequiredError(eventType=event_type.value)
    if (
        event_type is RegistrationEventType.DAY_BOOK_ENTERED
        and not (day_book_reference or "").strip()
    ):
        raise RegistrationDayBookReferenceRequiredError()
    if (
        event_type in {RegistrationEventType.REFUSED, RegistrationEventType.RETURNED}
        and not (result_note or "").strip()
    ):
        raise RegistrationResultNoteRequiredError(eventType=event_type.value)
    if event_type is RegistrationEventType.REGISTERED:
        _guard_registration_result(generated_form_id, existing)


def _guard_registration_result(
    generated_form_id: str | None, existing: Sequence[RegistrationEvent]
) -> None:
    """§10.1 — a registration follows a recorded presentation of the same instrument."""
    for event in existing:
        if (
            event.event_type is RegistrationEventType.REGISTERED
            and event.generated_form_id == generated_form_id
        ):
            raise RegistrationAlreadyRecordedError(
                generatedFormId=generated_form_id, registrationEventId=event.id
            )
    presented = any(
        event.event_type in _PRESENTATION_EVENTS
        and (event.generated_form_id is None or event.generated_form_id == generated_form_id)
        for event in existing
    )
    if not presented:
        raise RegistrationOutOfOrderError(generatedFormId=generated_form_id)


@dataclass(frozen=True)
class RegistrationStatus:
    """What the recorded events say about one matter. Never inferred from time."""

    attested_on: date | None = None
    presented_on: date | None = None
    registered_on: date | None = None
    refused_on: date | None = None
    deadline: PresentationDeadline | None = None

    @property
    def is_registered(self) -> bool:
        return self.registered_on is not None


def registration_status(events: Sequence[RegistrationEvent]) -> RegistrationStatus:
    """Fold the recorded events into the matter's registry position.

    Earliest date wins for each kind: the first presentation is the one the
    registry acted on, and the first attestation is the one s. 45(1) runs from.
    """

    def earliest(*types: RegistrationEventType) -> date | None:
        dates = [event.event_date for event in events if event.event_type in types]
        return min(dates) if dates else None

    attested_on = earliest(RegistrationEventType.ATTESTED)
    return RegistrationStatus(
        attested_on=attested_on,
        presented_on=earliest(*_PRESENTATION_EVENTS),
        registered_on=earliest(RegistrationEventType.REGISTERED),
        refused_on=earliest(RegistrationEventType.REFUSED, RegistrationEventType.RETURNED),
        deadline=presentation_deadline(attested_on) if attested_on is not None else None,
    )


__all__ = [
    "APPROVABLE_STATES",
    "FORWARDING_WORKING_DAYS",
    "ApprovalGateCode",
    "ApprovalGateItem",
    "ApprovalGateResult",
    "PresentationDeadline",
    "RegistrationStatus",
    "add_working_days",
    "approval_matches_snapshot",
    "approval_snapshot_hash",
    "build_manifest",
    "confirmed_fact_hash",
    "evaluate_approval_gate",
    "export_artifact_hash",
    "export_artifact_key",
    "export_registration_ready",
    "export_watermarked",
    "guard_approval",
    "guard_registration_event",
    "matter_state_for_event",
    "matter_state_for_export",
    "presentation_deadline",
    "registration_status",
    "require_responsible_lawyer",
    "source_reverification_required",
    "superseded_bindings",
]

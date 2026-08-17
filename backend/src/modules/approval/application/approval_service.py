"""Approval, export, and registration application service.

Three decisions in this file are product decisions, not implementation details.

**The server reads what it approves.** The only thing the request contributes to
an approval is the declaration version and the list of warnings the lawyer
disposed of. The form version, the template version, the fact versions, the
evidence, and every hash come from the snapshot this service read through
`draft.contracts.GeneratedFormReadPort` (§9.6). A client-supplied version would
pin whatever the client wished had been true.

**Export produces a record, not a document.** No template in this repository has
a lawyer-approved production rendering (§9.5), so a laid-out page here would be
a fabricated one. What is produced is a manifest: the binding record, its
evidence chain, and the qualifications that must travel with it. Every artifact
is an internal review artifact, and `registration_ready` is false in every case.

**Nothing in this file advances a legal state because time passed.** The matter
moves when a human records an act — approval, export of an approved snapshot,
presentation, registration — and the state each act implies is a pure function
of the act (`policies.matter_state_for_event`). Export can never imply
``REGISTERED``; only a recorded registration event can (§9.6, §17).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog

from src.modules.approval.contracts import ApprovalSummary, RegistrationSummary
from src.modules.approval.domain.declarations import (
    CURRENT_DECLARATION_VERSION,
    declaration_text_hash,
    get_declaration,
)
from src.modules.approval.domain.errors import (
    ApprovalAlreadyCurrentError,
    ApprovalDeclarationUnknownError,
    ApprovalSupersededError,
    ApprovalTargetNotFoundError,
    ApprovalTargetNotSupportedError,
    ExportRequiresApprovalError,
)
from src.modules.approval.domain.models import (
    Approval,
    ExportFormat,
    FormExport,
    RegistrationEvent,
)
from src.modules.approval.domain.policies import (
    ApprovalGateResult,
    PresentationDeadline,
    approval_matches_snapshot,
    approval_snapshot_hash,
    build_manifest,
    confirmed_fact_hash,
    evaluate_approval_gate,
    export_artifact_hash,
    export_artifact_key,
    export_registration_ready,
    export_watermarked,
    guard_approval,
    guard_registration_event,
    matter_state_for_event,
    matter_state_for_export,
    presentation_deadline,
    registration_status,
    superseded_bindings,
)
from src.modules.approval.ports import (
    ApprovalRepository,
    FormExportRepository,
    GeneratedFormCommandPort,
    MatterWorkflowCommandPort,
    RegistrationEventRepository,
)
from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.check.contracts import IssueGatePort
from src.modules.content_governance.contracts import (
    ApprovalTargetType,
    FormTemplateDefinition,
    MatterState,
    RegistrationEventType,
    RtaWorkflowRole,
    require_template,
)
from src.modules.draft.contracts import FormSnapshot, GeneratedFormReadPort
from src.modules.task.contracts import ChecklistBlockerPort
from src.modules.verification.contracts import ConfirmedFactReadPort, FactTierSummary
from src.platform import ids

log = structlog.get_logger(__name__)

#: The reason recorded on a form this module marks stale. §10.5 names the cause:
#: the fact bound into the approved snapshot has been corrected.
STALE_REASON_FACT_SUPERSEDED = "FACT_SUPERSEDED"


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class _Context:
    """One read of everything a decision about a form depends on."""

    snapshot: FormSnapshot
    template: FormTemplateDefinition
    facts: FactTierSummary
    gate: ApprovalGateResult


@dataclass(frozen=True)
class ApprovalView:
    """One approval plus the gate report it was granted against."""

    approval: Approval
    gate: ApprovalGateResult


@dataclass(frozen=True)
class RegistrationEventView:
    """One recorded event, the matter state it implies, and any clock it started."""

    event: RegistrationEvent
    #: ``None`` for an attestation: it is an act on the instrument, not a
    #: registry act on the matter, and §10.1 has no state for it.
    implied_matter_state: MatterState | None
    #: Present only for a confirmed attestation date (§9.6, §17).
    deadline: PresentationDeadline | None


class ApprovalService:
    """Owns approvals, exports, and the recorded registry events."""

    def __init__(
        self,
        *,
        approvals: ApprovalRepository,
        exports: FormExportRepository,
        events: RegistrationEventRepository,
        forms: GeneratedFormReadPort,
        facts: ConfirmedFactReadPort,
        issues: IssueGatePort,
        checklist: ChecklistBlockerPort,
        audit: AuditPort,
        form_commands: GeneratedFormCommandPort | None = None,
        matter_commands: MatterWorkflowCommandPort | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._approvals = approvals
        self._exports = exports
        self._events = events
        self._forms = forms
        self._facts = facts
        self._issues = issues
        self._checklist = checklist
        self._audit = audit
        # Optional: both write aggregates this module does not own. With neither
        # wired every legal fact recorded here is still recorded, and the two
        # other aggregates simply do not move. See `ports.py`.
        self._form_commands = form_commands
        self._matter_commands = matter_commands
        self._clock = clock

    # ── Approval (§9.6) ──────────────────────────────────────────────────────

    async def approve_form(
        self,
        *,
        user_id: str,
        form_id: str,
        actor_id: str,
        workflow_role: RtaWorkflowRole,
        correlation_id: str,
        disposed_warning_ids: Sequence[str],
        declaration_version: str = CURRENT_DECLARATION_VERSION,
    ) -> ApprovalView:
        """Approve one exact form snapshot.

        The caller has already been authorised as the matter's responsible
        lawyer (`policies.require_responsible_lawyer`); ``workflow_role`` is
        that result, recorded on the approval so the authority under which it
        was given survives a later reassignment of the file.
        """
        declaration = get_declaration(declaration_version)
        if declaration is None:
            raise ApprovalDeclarationUnknownError(declarationVersion=declaration_version)

        context = await self._read(user_id, form_id)
        snapshot, gate = context.snapshot, context.gate
        await self._refuse_if_superseded(context, user_id=user_id)
        guard_approval(gate, disposed_warning_ids=disposed_warning_ids)

        snapshot_hash = approval_snapshot_hash(snapshot)
        previous = await self._approvals.current_for_target(user_id, snapshot.form_id)
        if previous is not None and previous.snapshot_hash == snapshot_hash:
            # The same snapshot is already approved. A second signature over an
            # unchanged record is a duplicate submission, not a re-approval.
            raise ApprovalAlreadyCurrentError(formId=snapshot.form_id, approvalId=previous.id)

        approval = Approval(
            id=ids.new_id(ids.APPROVAL),
            user_id=user_id,
            matter_id=snapshot.matter_id,
            target_type=ApprovalTargetType.GENERATED_FORM,
            target_id=snapshot.form_id,
            # §9.6 — read from the server's own record of the form.
            target_version=str(snapshot.form_version),
            approver_id=actor_id,
            approver_workflow_role=workflow_role,
            declaration_version=declaration.version,
            declaration_text_hash=declaration_text_hash(declaration),
            snapshot_hash=snapshot_hash,
            confirmed_fact_hash=confirmed_fact_hash(snapshot),
            warning_disposition_ids=gate.warning_ids,
            template_id=snapshot.template_id,
            template_version=snapshot.template_version,
            rule_pack_version=snapshot.rule_pack_version,
            created_at=self._clock(),
        )
        saved = await self._approvals.create(approval)
        if previous is not None:
            # An earlier approval of the same target is superseded by this one,
            # and points at it: §17's "prevents reuse of the old approval" is a
            # property of the data, not of a code path remembering to check.
            await self._approvals.revoke(user_id, previous.id, saved.id)

        if self._form_commands is not None:
            await self._form_commands.record_approval(
                user_id=user_id,
                form_id=snapshot.form_id,
                approval_id=saved.id,
                approved_artifact_hash=saved.snapshot_hash,
                expected_version=snapshot.version,
            )
        await self._advance_matter(
            user_id=user_id,
            matter_id=snapshot.matter_id,
            state=MatterState.APPROVED,
            reason=AuditAction.RTA_FORM_APPROVED.value,
        )
        await self._record(
            user_id=user_id,
            matter_id=snapshot.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_FORM_APPROVED,
            target_type=AuditTargetType.APPROVAL,
            target_id=saved.id,
            before_ref=previous.id if previous else None,
            after_ref=f"{saved.target_id}#{saved.target_version}:{saved.snapshot_hash}",
        )
        return ApprovalView(approval=saved, gate=gate)

    async def list_approvals(
        self, *, user_id: str, form_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[Approval], str | None]:
        """Every approval of one form, newest first. Revoked ones included.

        A revoked approval is the record of a signature that was given; hiding
        it would make the history of the instrument unreadable.
        """
        snapshot = await self._snapshot(user_id, form_id)
        return await self._approvals.list_for_target(
            user_id, snapshot.form_id, limit=limit, cursor=cursor
        )

    async def approval_gate(self, *, user_id: str, form_id: str) -> ApprovalGateResult:
        """The gate report the lawyer sees before signing.

        Read-only, and the source of the warning ids an approval must dispose of
        (§9.6). Recomputed on every call rather than cached: the four sources it
        reads are exactly the four that move underneath a draft.
        """
        return (await self._read(user_id, form_id)).gate

    async def matter_id_for_form(self, *, user_id: str, form_id: str) -> str:
        """Which matter this form belongs to, for the router's authorization.

        Routes address a form without its matter (§12.4), so the matter has to
        be resolved before the caller can be authorized against it. Reading the
        snapshot under the caller's own ``user_id`` first means a form belonging
        to anyone else is already a 404 by the time the capability is checked.
        """
        return (await self._snapshot(user_id, form_id)).matter_id

    async def current_approval(self, user_id: str, form_id: str) -> ApprovalSummary | None:
        """Implements `approval.contracts.ApprovalReadPort`."""
        approval = await self._approvals.current_for_target(user_id, form_id)
        return _to_summary(approval) if approval is not None else None

    # ── Export (§9.4, §9.6) ──────────────────────────────────────────────────

    async def export_form(
        self,
        *,
        user_id: str,
        form_id: str,
        actor_id: str,
        correlation_id: str,
        export_format: ExportFormat,
    ) -> FormExport:
        """Produce one export record over the current snapshot.

        Not an instrument and not a submission. §9.6 is explicit that export is
        not attestation, presentation, or registration, so the only state this
        can move is ``APPROVED -> EXPORTED`` and only for a projection of a live
        approval.
        """
        context = await self._read(user_id, form_id)
        snapshot, gate = context.snapshot, context.gate
        approval = await self._approvals.current_for_target(user_id, snapshot.form_id)
        if approval is not None:
            # Both halves of §17: the bindings may have been rewritten, or the
            # facts under them corrected. Either way the approval is spent.
            if not approval_matches_snapshot(approval, snapshot):
                await self._mark_stale(user_id, snapshot.form_id)
                raise ApprovalSupersededError(
                    formId=snapshot.form_id, approvalId=approval.id, movedFieldIds=[]
                )
            await self._refuse_if_superseded(context, user_id=user_id, approval_id=approval.id)
        elif export_format is ExportFormat.APPROVED_MANIFEST:
            raise ExportRequiresApprovalError(formId=snapshot.form_id)

        watermarked = export_watermarked(export_format, approval)
        ready = export_registration_ready(
            export_format=export_format, approval=approval, result=gate
        )
        manifest = build_manifest(
            snapshot=snapshot,
            template=context.template,
            export_format=export_format,
            approval=approval,
            result=gate,
            watermarked=watermarked,
            registration_ready=ready,
        )
        export_id = ids.new_id(ids.EXPORT)
        saved = await self._exports.create(
            FormExport(
                id=export_id,
                user_id=user_id,
                matter_id=snapshot.matter_id,
                generated_form_id=snapshot.form_id,
                approval_id=approval.id if approval else None,
                export_format=export_format,
                artifact_hash=export_artifact_hash(manifest),
                artifact_key=export_artifact_key(export_id),
                watermarked=watermarked,
                registration_ready=ready,
                manifest=manifest,
                created_by=actor_id,
                created_at=self._clock(),
            )
        )
        state = matter_state_for_export(export_format, approval)
        if state is not None:
            await self._advance_matter(
                user_id=user_id,
                matter_id=snapshot.matter_id,
                state=state,
                reason=AuditAction.RTA_FORM_EXPORTED.value,
            )
        await self._record(
            user_id=user_id,
            matter_id=snapshot.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_FORM_EXPORTED,
            target_type=AuditTargetType.EXPORT,
            target_id=saved.id,
            after_ref=(
                f"{saved.export_format.value}:{saved.artifact_hash}"
                f"|registrationReady={str(saved.registration_ready).lower()}"
            ),
        )
        return saved

    async def list_exports(
        self, *, user_id: str, matter_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[FormExport], str | None]:
        return await self._exports.list_for_matter(user_id, matter_id, limit=limit, cursor=cursor)

    # ── Registration events (§10.1, §17) ─────────────────────────────────────

    async def record_registration_event(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        event_type: RegistrationEventType,
        event_date: date,
        evidence_reference_ids: Sequence[str],
        generated_form_id: str | None = None,
        day_book_reference: str | None = None,
        registry_office: str | None = None,
        result_note: str | None = None,
    ) -> RegistrationEventView:
        """Record one official act.

        Attestation, presentation, and registration are three separate events
        and none of them is inferred from another or from the clock. The
        recorder is the authenticated actor, never the body: §12.5 makes this a
        named human act.
        """
        if generated_form_id is not None:
            snapshot = await self._snapshot(user_id, generated_form_id)
            if snapshot.matter_id != matter_id:
                # Naming another matter's instrument is not a recordable act.
                raise ApprovalTargetNotFoundError()

        existing = await self._events.all_for_matter(user_id, matter_id)
        guard_registration_event(
            event_type=event_type,
            event_date=event_date,
            today=self._clock().date(),
            evidence_reference_ids=evidence_reference_ids,
            generated_form_id=generated_form_id,
            day_book_reference=day_book_reference,
            result_note=result_note,
            existing=existing,
        )
        saved = await self._events.create(
            RegistrationEvent(
                id=ids.new_id(ids.REGISTRATION_EVENT),
                user_id=user_id,
                matter_id=matter_id,
                generated_form_id=generated_form_id,
                event_type=event_type,
                event_date=event_date,
                evidence_reference_ids=tuple(evidence_reference_ids),
                day_book_reference=day_book_reference,
                registry_office=registry_office,
                result_note=result_note,
                recorded_by=actor_id,
                created_at=self._clock(),
            )
        )
        state = matter_state_for_event(saved.event_type)
        if state is not None:
            await self._advance_matter(
                user_id=user_id,
                matter_id=matter_id,
                state=state,
                reason=AuditAction.RTA_REGISTRATION_EVENT_RECORDED.value,
            )
        deadline = (
            presentation_deadline(saved.event_date)
            if saved.event_type is RegistrationEventType.ATTESTED
            else None
        )
        await self._record(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_REGISTRATION_EVENT_RECORDED,
            target_type=AuditTargetType.REGISTRATION_EVENT,
            target_id=saved.id,
            after_ref=(
                f"{saved.event_type.value}@{saved.event_date.isoformat()}"
                f"|matterState={state.value if state else 'unchanged'}"
            ),
            reason=saved.result_note,
        )
        return RegistrationEventView(event=saved, implied_matter_state=state, deadline=deadline)

    async def list_registration_events(
        self, *, user_id: str, matter_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[RegistrationEvent], str | None]:
        return await self._events.list_for_matter(user_id, matter_id, limit=limit, cursor=cursor)

    async def registration_summary(self, user_id: str, matter_id: str) -> RegistrationSummary:
        """Implements `approval.contracts.RegistrationReadPort`."""
        status = registration_status(await self._events.all_for_matter(user_id, matter_id))
        return RegistrationSummary(
            attested_on=status.attested_on,
            presented_on=status.presented_on,
            registered_on=status.registered_on,
            refused_on=status.refused_on,
            forwarding_due_on=status.deadline.due_on if status.deadline else None,
            forwarding_due_provisional=(status.deadline.provisional if status.deadline else True),
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _snapshot(self, user_id: str, form_id: str) -> FormSnapshot:
        snapshot = await self._forms.get_form_snapshot(user_id, form_id)
        if snapshot is None:
            # Absent and foreign are indistinguishable on purpose.
            raise ApprovalTargetNotFoundError()
        return snapshot

    async def _read(self, user_id: str, form_id: str) -> _Context:
        """Read the snapshot once and evaluate the four §14.6 sources over it."""
        snapshot = await self._snapshot(user_id, form_id)
        try:
            template = require_template(snapshot.template_id)
        except KeyError:
            # A form drafted against a template that has since left the registry
            # has nothing left to pin an approval to (§9.5).
            raise ApprovalTargetNotSupportedError(templateId=snapshot.template_id)
        facts = await self._facts.summarise(user_id, snapshot.matter_id)
        return _Context(
            snapshot=snapshot,
            template=template,
            facts=facts,
            gate=evaluate_approval_gate(
                snapshot=snapshot,
                template=template,
                facts=facts,
                issue_gates=await self._issues.gates(user_id, snapshot.matter_id),
                blocking_requirement_ids=await self._checklist.blocking_requirement_ids(
                    user_id=user_id, matter_id=snapshot.matter_id
                ),
            ),
        )

    async def _refuse_if_superseded(
        self, context: _Context, *, user_id: str, approval_id: str | None = None
    ) -> None:
        """§17 — a correction after approval marks the form stale and blocks reuse.

        Checked against the live fact tier rather than against the form's own
        recorded state: a correction does not have to have passed through the
        drafting module's staleness sweep in order to have happened.
        """
        moved = superseded_bindings(context.snapshot, context.template, context.facts)
        if not moved:
            return
        await self._mark_stale(user_id, context.snapshot.form_id)
        raise ApprovalSupersededError(
            formId=context.snapshot.form_id,
            approvalId=approval_id,
            movedFieldIds=list(moved),
        )

    async def _mark_stale(self, user_id: str, form_id: str) -> None:
        if self._form_commands is None:
            # Nothing to call yet. The refusal still stands: the old approval is
            # not reusable whether or not the form's own row records why.
            log.warning("approval.form_stale_not_recorded", form_id=form_id)
            return
        await self._form_commands.mark_stale(
            user_id=user_id, form_id=form_id, reason=STALE_REASON_FACT_SUPERSEDED
        )

    async def _advance_matter(
        self, *, user_id: str, matter_id: str, state: MatterState, reason: str
    ) -> None:
        if self._matter_commands is None:
            log.info("approval.matter_state_not_advanced", matter_id=matter_id, state=state.value)
            return
        await self._matter_commands.advance_state(
            user_id=user_id, matter_id=matter_id, state=state, reason=reason
        )

    async def _record(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        action: AuditAction,
        target_type: AuditTargetType,
        target_id: str,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=action.value,
                target_type=target_type.value,
                target_id=target_id,
                before_ref=before_ref,
                after_ref=after_ref,
                reason=reason,
                correlation_id=correlation_id,
            )
        )


def _to_summary(approval: Approval) -> ApprovalSummary:
    return ApprovalSummary(
        id=approval.id,
        matter_id=approval.matter_id,
        target_id=approval.target_id,
        target_version=approval.target_version,
        approver_id=approval.approver_id,
        snapshot_hash=approval.snapshot_hash,
        confirmed_fact_hash=approval.confirmed_fact_hash,
        declaration_version=approval.declaration_version,
        created_at=approval.created_at,
        revoked_by_approval_id=approval.revoked_by_approval_id,
    )


__all__ = [
    "ApprovalService",
    "ApprovalView",
    "RegistrationEventView",
]

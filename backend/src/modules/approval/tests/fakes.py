"""In-memory doubles and synthetic fixtures for the approval module's tests.

No database. The repository doubles keep the behaviours the real ones have that
the tests depend on: `current_for_target` skips revoked approvals, `revoke`
refuses to overwrite an existing successor, and every accessor hands back the
stored record rather than the caller's own object.

Every value here is invented. No real party, NIC, deed, parcel, notary, registry
office, day book reference, or matter appears anywhere in this module.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from src.modules.approval.domain.declarations import (
    CURRENT_DECLARATION_VERSION,
    DECLARATIONS,
    declaration_text_hash,
)
from src.modules.approval.domain.models import Approval, FormExport, RegistrationEvent
from src.modules.approval.domain.policies import approval_snapshot_hash, confirmed_fact_hash
from src.modules.auth.ports import AuditEventInput
from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    ApprovalTargetType,
    AutomationScope,
    FormTemplateDefinition,
    GeneratedFormState,
    MatterState,
    RtaWorkflowRole,
    SubtypeDecisionStatus,
    require_template,
)
from src.modules.draft.contracts import BoundFact, FormSnapshot
from src.modules.matter.contracts import MatterAccessSummary
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary

USER_ID = "usr_synthetic"
MATTER_ID = "mat_synthetic"
FORM_ID = "frm_synthetic"
LAWYER_ID = "usr_synthetic"
CORRELATION = "corr_synthetic"
TRANSFER_SUBTYPE_ID = "lk.rta.instrument.transfer_sale"
FORM_08_TEMPLATE_ID = "rta.reg.2022.form.08"

#: Fixed so a hash assertion does not depend on the day the suite runs.
NOW = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
TODAY = NOW.date()

FORM_08: FormTemplateDefinition = require_template(FORM_08_TEMPLATE_ID)

#: Every field Form 8 must carry from a lawyer-confirmed fact before it can be
#: approved. Derived from the rule pack rather than listed, so a template change
#: moves the fixture with it.
CRITICAL_REQUIRED_FIELD_IDS: tuple[str, ...] = tuple(
    mapping.field_id for mapping in FORM_08.field_mappings if mapping.critical and mapping.required
)

#: §9.3 never pre-certifies the attestation act, so that field is unresolved on
#: every working draft. The other two are simply optional particulars.
DEFAULT_UNRESOLVED_FIELD_IDS: tuple[str, ...] = (
    "attestation_date",
    "village",
    "assessment_number",
)


def _fact_id(field_id: str, suffix: str) -> str:
    return f"fact_{field_id}_{suffix}"


def bindings(
    *,
    suffix: str = "a",
    version: int = 1,
    without_evidence: tuple[str, ...] = (),
    omit: tuple[str, ...] = (),
) -> tuple[BoundFact, ...]:
    """One pinned confirmed fact per critical required field."""
    return tuple(
        BoundFact(
            field_id=field_id,
            fact_id=_fact_id(field_id, suffix),
            version=version,
            evidence_reference_ids=(
                () if field_id in without_evidence else (f"ev_{field_id}_{suffix}",)
            ),
        )
        for field_id in CRITICAL_REQUIRED_FIELD_IDS
        if field_id not in omit
    )


def fact_tier(
    *,
    suffix: str = "a",
    version: int = 1,
    unconfirmed_critical: tuple[str, ...] = (),
    conflicted: tuple[str, ...] = (),
) -> FactTierSummary:
    """The confirmed tier that matches `bindings` with the same suffix/version."""
    confirmed: dict[str, ConfirmedFactValue] = {}
    for mapping in FORM_08.field_mappings:
        if not (mapping.critical and mapping.required) or mapping.fact_type_id is None:
            continue
        confirmed[mapping.fact_type_id] = ConfirmedFactValue(
            fact_id=_fact_id(mapping.field_id, suffix),
            fact_type_id=mapping.fact_type_id,
            value=f"synthetic-{mapping.field_id}",
            version=version,
            evidence_reference_ids=(f"ev_{mapping.field_id}_{suffix}",),
        )
    return FactTierSummary(
        confirmed=confirmed,
        unconfirmed_critical_fact_type_ids=unconfirmed_critical,
        conflicted_fact_type_ids=conflicted,
        has_current_search_evidence=True,
    )


def form_snapshot(
    *,
    state: GeneratedFormState = GeneratedFormState.REVIEW_READY,
    unresolved_field_ids: tuple[str, ...] = DEFAULT_UNRESOLVED_FIELD_IDS,
    critical_fact_bindings: tuple[BoundFact, ...] | None = None,
    draft_artifact_hash: str = "sha256:synthetic-draft-hash",
    approved_artifact_hash: str | None = None,
    approval_id: str | None = None,
    stale_reason: str | None = None,
    form_version: int = 1,
    version: int = 3,
) -> FormSnapshot:
    """A Form 8 draft whose gate is clean unless a test dirties it."""
    return FormSnapshot(
        form_id=FORM_ID,
        user_id=USER_ID,
        matter_id=MATTER_ID,
        state=state,
        template_id=FORM_08_TEMPLATE_ID,
        template_version=FORM_08.version,
        form_version=form_version,
        subtype_id=TRANSFER_SUBTYPE_ID,
        rule_pack_version="1.0.0",
        draft_artifact_hash=draft_artifact_hash,
        approved_artifact_hash=approved_artifact_hash,
        approval_id=approval_id,
        stale_reason=stale_reason,
        version=version,
        critical_fact_bindings=(
            bindings() if critical_fact_bindings is None else critical_fact_bindings
        ),
        unresolved_field_ids=unresolved_field_ids,
    )


def approval_record(
    *,
    approval_id: str = "apr_synthetic",
    snapshot: FormSnapshot | None = None,
    revoked_by_approval_id: str | None = None,
) -> Approval:
    """An approval already pinned to ``snapshot``, as the repository would hold it."""
    pinned = snapshot if snapshot is not None else form_snapshot()
    declaration = DECLARATIONS[CURRENT_DECLARATION_VERSION]
    return Approval(
        id=approval_id,
        user_id=USER_ID,
        matter_id=MATTER_ID,
        target_type=ApprovalTargetType.GENERATED_FORM,
        target_id=pinned.form_id,
        target_version=str(pinned.form_version),
        approver_id=LAWYER_ID,
        approver_workflow_role=RtaWorkflowRole.RESPONSIBLE_LAWYER,
        declaration_version=declaration.version,
        declaration_text_hash=declaration_text_hash(declaration),
        snapshot_hash=approval_snapshot_hash(pinned),
        confirmed_fact_hash=confirmed_fact_hash(pinned),
        warning_disposition_ids=(),
        template_id=pinned.template_id,
        template_version=pinned.template_version,
        rule_pack_version=pinned.rule_pack_version,
        created_at=NOW,
        revoked_by_approval_id=revoked_by_approval_id,
    )


def matter_summary(
    *,
    user_id: str = USER_ID,
    responsible_lawyer_id: str = LAWYER_ID,
    state: MatterState = MatterState.APPROVAL_PENDING,
) -> MatterAccessSummary:
    return MatterAccessSummary(
        id=MATTER_ID,
        user_id=user_id,
        responsible_lawyer_id=responsible_lawyer_id,
        regime_id="lk.rta",
        subtype_id=TRANSFER_SUBTYPE_ID,
        subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
        rta_state=state,
        automation_scope=AutomationScope.V0_AUTOMATED,
        active_checklist_snapshot_id="cls_synthetic",
        version=4,
    )


class FakeFormReader:
    """Implements ``draft.contracts.GeneratedFormReadPort``."""

    def __init__(self, snapshot: FormSnapshot | None = None) -> None:
        self.snapshot = snapshot if snapshot is not None else form_snapshot()

    async def get_form_snapshot(self, user_id: str, form_id: str) -> FormSnapshot | None:
        if self.snapshot is None:
            return None
        if self.snapshot.user_id != user_id or self.snapshot.form_id != form_id:
            return None
        return self.snapshot


class FakeFactReader:
    """Implements ``ConfirmedFactReadPort``; the summary is swapped between calls."""

    def __init__(self, summary: FactTierSummary | None = None) -> None:
        self.summary = summary if summary is not None else fact_tier()

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
        return self.summary


class FakeIssueGates:
    """Implements ``IssueGatePort``."""

    def __init__(self, summary: IssueGateSummary | None = None) -> None:
        self.summary = summary or IssueGateSummary()

    async def gates(self, user_id: str, matter_id: str) -> IssueGateSummary:
        return self.summary


class FakeChecklistBlockers:
    """Implements ``ChecklistBlockerPort``."""

    def __init__(self, requirement_ids: tuple[str, ...] = ()) -> None:
        self.requirement_ids = requirement_ids

    async def blocking_requirement_ids(self, *, user_id: str, matter_id: str) -> tuple[str, ...]:
        return self.requirement_ids


class FakeApprovalRepository:
    """Implements ``ApprovalRepository`` in memory."""

    def __init__(self) -> None:
        self.approvals: dict[str, Approval] = {}

    async def create(self, approval: Approval) -> Approval:
        self.approvals[approval.id] = approval
        return approval

    async def list_for_target(
        self, user_id: str, target_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[Approval], str | None]:
        matching = [
            approval
            for approval in sorted(
                self.approvals.values(), key=lambda a: (a.created_at, a.id), reverse=True
            )
            if approval.user_id == user_id and approval.target_id == target_id
        ]
        return matching[:limit], None

    async def current_for_target(self, user_id: str, target_id: str) -> Approval | None:
        matching = [
            approval
            for approval in sorted(
                self.approvals.values(), key=lambda a: (a.created_at, a.id), reverse=True
            )
            if approval.user_id == user_id
            and approval.target_id == target_id
            and not approval.is_revoked
        ]
        return matching[0] if matching else None

    async def revoke(self, user_id: str, approval_id: str, revoked_by_approval_id: str) -> None:
        stored = self.approvals.get(approval_id)
        if stored is None or stored.user_id != user_id or stored.is_revoked:
            # The first successor is the one that superseded it.
            return
        self.approvals[approval_id] = replace(stored, revoked_by_approval_id=revoked_by_approval_id)


class FakeExportRepository:
    """Implements ``FormExportRepository`` in memory."""

    def __init__(self) -> None:
        self.exports: dict[str, FormExport] = {}

    async def create(self, export: FormExport) -> FormExport:
        self.exports[export.id] = export
        return export

    async def list_for_matter(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[FormExport], str | None]:
        matching = [
            export
            for export in sorted(
                self.exports.values(), key=lambda e: (e.created_at, e.id), reverse=True
            )
            if export.user_id == user_id and export.matter_id == matter_id
        ]
        return matching[:limit], None


class FakeRegistrationEventRepository:
    """Implements ``RegistrationEventRepository`` in memory."""

    def __init__(self, events: tuple[RegistrationEvent, ...] = ()) -> None:
        self.events: dict[str, RegistrationEvent] = {event.id: event for event in events}

    async def create(self, event: RegistrationEvent) -> RegistrationEvent:
        self.events[event.id] = event
        return event

    async def list_for_matter(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[RegistrationEvent], str | None]:
        matching = [
            event
            for event in sorted(
                self.events.values(), key=lambda e: (e.created_at, e.id), reverse=True
            )
            if event.user_id == user_id and event.matter_id == matter_id
        ]
        return matching[:limit], None

    async def all_for_matter(self, user_id: str, matter_id: str) -> list[RegistrationEvent]:
        return [
            event
            for event in sorted(self.events.values(), key=lambda e: (e.event_date, e.id))
            if event.user_id == user_id and event.matter_id == matter_id
        ]


class FakeFormCommands:
    """Implements ``GeneratedFormCommandPort``. Records the calls for assertion."""

    def __init__(self) -> None:
        self.approvals: list[dict[str, Any]] = []
        self.stale: list[dict[str, Any]] = []

    async def record_approval(
        self,
        *,
        user_id: str,
        form_id: str,
        approval_id: str,
        approved_artifact_hash: str,
        expected_version: int,
    ) -> None:
        self.approvals.append(
            {
                "form_id": form_id,
                "approval_id": approval_id,
                "approved_artifact_hash": approved_artifact_hash,
                "expected_version": expected_version,
            }
        )

    async def mark_stale(self, *, user_id: str, form_id: str, reason: str) -> None:
        self.stale.append({"form_id": form_id, "reason": reason})


class FakeMatterCommands:
    """Implements ``MatterWorkflowCommandPort``. Records the states requested."""

    def __init__(self) -> None:
        self.states: list[MatterState] = []

    async def advance_state(
        self, *, user_id: str, matter_id: str, state: MatterState, reason: str
    ) -> None:
        self.states.append(state)


class FakeAudit:
    """Implements ``AuditPort``. Records the events for assertion."""

    def __init__(self) -> None:
        self.events: list[AuditEventInput] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append(event)

    def actions(self) -> list[str]:
        return [event.action for event in self.events]


def registration_event(
    event_type: Any,
    *,
    event_id: str = "reg_synthetic",
    event_date: date | None = None,
    generated_form_id: str | None = FORM_ID,
    day_book_reference: str | None = None,
    result_note: str | None = None,
) -> RegistrationEvent:
    return RegistrationEvent(
        id=event_id,
        user_id=USER_ID,
        matter_id=MATTER_ID,
        generated_form_id=generated_form_id,
        event_type=event_type,
        event_date=event_date or date(2026, 8, 10),
        evidence_reference_ids=("ev_registry_synthetic",),
        day_book_reference=day_book_reference,
        registry_office="Synthetic Land Registry",
        result_note=result_note,
        recorded_by=LAWYER_ID,
        created_at=NOW,
    )

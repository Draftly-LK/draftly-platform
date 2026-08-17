"""Matter domain entities and the state machine over them.

The matter carries three orthogonal axes that older designs collapsed into one
``status`` field, and keeping them apart is the point:

```text
lifecycle_status  inquiry | active | closed | archived      (matter-service.md §7)
rta_state         the §10.1 workflow state machine
automation_scope  how much Draftly may automate  (§2.3)
```

A matter with a blocking finding is ``lifecycle_status=active`` and
``automation_scope=MANUAL_SUPPORTED``. It is not "closed", not "rejected", and
it keeps every uploaded file and every checklist decision.

`rta_state` lives on the matter row for V0 because `task_service`'s WorkflowRun
does not exist yet. When it lands, this field becomes the projection
`matter-service.md` §6 describes; the enum and transitions do not change.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.modules.content_governance.contracts import (
    AnswerStatus,
    AutomationScope,
    DispositionScope,
    DisputeStage,
    MatterFamily,
    MatterState,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
)


class MatterLifecycleStatus(str, enum.Enum):
    """Access lifecycle, owned by this service (matter-service.md §7)."""

    INQUIRY = "inquiry"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class InstrumentLanguage(str, enum.Enum):
    EN = "en"
    SI = "si"
    TA = "ta"


#: §10.1. A transition not listed here is refused, which is what stops a matter
#: from reaching ``APPROVED`` without passing through review.
_ALLOWED_TRANSITIONS: dict[MatterState, frozenset[MatterState]] = {
    MatterState.INTAKE_DRAFT: frozenset({MatterState.ROUTED, MatterState.CANCELLED}),
    MatterState.ROUTED: frozenset(
        {
            MatterState.EVIDENCE_COLLECTION,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    MatterState.EVIDENCE_COLLECTION: frozenset(
        {
            MatterState.REVIEW_REQUIRED,
            MatterState.LEGAL_REVIEW,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    MatterState.REVIEW_REQUIRED: frozenset(
        {
            MatterState.EVIDENCE_COLLECTION,
            MatterState.LEGAL_REVIEW,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    MatterState.LEGAL_REVIEW: frozenset(
        {
            MatterState.READY_TO_DRAFT,
            MatterState.REVIEW_REQUIRED,
            MatterState.EVIDENCE_COLLECTION,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    MatterState.READY_TO_DRAFT: frozenset(
        {
            MatterState.DRAFTING,
            MatterState.LEGAL_REVIEW,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    MatterState.DRAFTING: frozenset(
        {
            MatterState.APPROVAL_PENDING,
            MatterState.LEGAL_REVIEW,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    # Any upstream change after APPROVAL_PENDING invalidates preflight and
    # returns the matter to drafting or review (§10.1).
    MatterState.APPROVAL_PENDING: frozenset(
        {
            MatterState.APPROVED,
            MatterState.DRAFTING,
            MatterState.LEGAL_REVIEW,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LITIGATION_HOLD,
            MatterState.CANCELLED,
        }
    ),
    MatterState.APPROVED: frozenset(
        {MatterState.EXPORTED, MatterState.DRAFTING, MatterState.CANCELLED}
    ),
    # Export is not registration. Only a recorded official event advances these.
    MatterState.EXPORTED: frozenset(
        {MatterState.SUBMITTED, MatterState.DRAFTING, MatterState.CANCELLED}
    ),
    MatterState.SUBMITTED: frozenset({MatterState.REGISTERED, MatterState.CANCELLED}),
    MatterState.REGISTERED: frozenset({MatterState.CLOSED}),
    MatterState.CLOSED: frozenset(),
    # Neither exception state loses work; both can return once resolved.
    MatterState.MANUAL_SUPPORTED: frozenset(
        {
            MatterState.EVIDENCE_COLLECTION,
            MatterState.REVIEW_REQUIRED,
            MatterState.LEGAL_REVIEW,
            MatterState.LITIGATION_HOLD,
            MatterState.CLOSED,
            MatterState.CANCELLED,
        }
    ),
    MatterState.LITIGATION_HOLD: frozenset(
        {
            MatterState.EVIDENCE_COLLECTION,
            MatterState.MANUAL_SUPPORTED,
            MatterState.LEGAL_REVIEW,
            MatterState.CLOSED,
            MatterState.CANCELLED,
        }
    ),
    MatterState.CANCELLED: frozenset(),
}


def is_transition_allowed(current: MatterState, target: MatterState) -> bool:
    if current is target:
        return True
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


def allowed_transitions(current: MatterState) -> tuple[MatterState, ...]:
    return tuple(sorted(_ALLOWED_TRANSITIONS.get(current, frozenset()), key=lambda s: s.value))


@dataclass
class Matter:
    """The RTA matter root.

    ``user_id`` is the tenancy boundary this repository uses; the workflow
    spec calls it ``tenant_id``. Every query filters on it before any other
    check (plan §5.3 invariant 10).
    """

    id: str
    user_id: str
    reference: str
    responsible_lawyer_id: str
    regime_id: str
    lifecycle_status: MatterLifecycleStatus
    rta_state: MatterState
    automation_scope: AutomationScope
    subtype_decision_status: SubtypeDecisionStatus
    title_status: TitleStatus
    parcel_kind: ParcelKind
    disposition_scope: DispositionScope
    dispute_stage: DisputeStage
    created_at: datetime
    updated_at: datetime
    version: int = 1
    client_reference: str | None = None
    family_id: MatterFamily | None = None
    subtype_id: str | None = None
    #: Preserved verbatim when a matter arrives from the retired M2 vocabulary,
    #: so a legacy record stays readable and auditable after migration (§3.6).
    legacy_matter_type: str | None = None
    instrument_language: InstrumentLanguage = InstrumentLanguage.EN
    declared_legal_basis: str | None = None
    local_authority_id: str | None = None
    active_checklist_snapshot_id: str | None = None
    party_contexts: frozenset[PartyContext] = field(default_factory=frozenset)
    activated_conditional_module_ids: frozenset[str] = field(default_factory=frozenset)
    suppressed_conditional_module_ids: frozenset[str] = field(default_factory=frozenset)
    #: Why the matter left the automated path, as translation keys. Shown to
    #: the lawyer constructively rather than as a failure (§11.2).
    automation_exclusion_reason_keys: tuple[str, ...] = ()

    @property
    def is_mutable(self) -> bool:
        return self.lifecycle_status in {
            MatterLifecycleStatus.INQUIRY,
            MatterLifecycleStatus.ACTIVE,
        }


@dataclass
class IntakeAnswer:
    """One answer to one intake question, superseded rather than overwritten.

    A later conflicting extraction creates a review task; it never silently
    replaces a lawyer's answer (§4.4).
    """

    id: str
    user_id: str
    matter_id: str
    question_definition_id: str
    value: Any
    status: AnswerStatus
    created_at: datetime
    inferred_from_fact_ids: tuple[str, ...] = ()
    answered_by: str | None = None
    answer_reason: str | None = None
    supersedes_id: str | None = None

    @property
    def is_live(self) -> bool:
        return self.status is not AnswerStatus.SUPERSEDED

"""The only surface other modules may import from matter.

Downstream modules (task, document, verification, check, draft, approval) need
two things from the matter: enough of it to authorize the caller, and enough of
it to know which rule pack applies. They get exactly that here, and never the
matter aggregate, its ORM rows, or its repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.modules.content_governance.contracts import (
    AutomationScope,
    MatterAssignment,
    MatterState,
    RtaWorkflowRole,
    SubtypeDecisionStatus,
    is_rta_capability_granted,
    resolve_workflow_role,
)
from src.platform.errors import CapabilityDeniedError, NotFoundError


@dataclass(frozen=True)
class MatterAccessSummary:
    """What another module needs to authorize and route work on a matter."""

    id: str
    user_id: str
    responsible_lawyer_id: str
    regime_id: str
    subtype_id: str | None
    subtype_decision_status: SubtypeDecisionStatus
    rta_state: MatterState
    automation_scope: AutomationScope
    active_checklist_snapshot_id: str | None
    version: int


class MatterReadPort(Protocol):
    """Read-only access to a matter from another module."""

    async def get_access_summary(
        self, user_id: str, matter_id: str
    ) -> MatterAccessSummary | None: ...


def workflow_role_for(
    *,
    account_role: str,
    actor_id: str,
    matter: MatterAccessSummary,
) -> RtaWorkflowRole | None:
    """Resolve the actor's workflow role on this matter.

    Tenancy in this deployment is per user, so membership is simply "this
    matter belongs to the caller". Responsibility is a separate, narrower
    pointer: being the account's owner does not make you the responsible lawyer
    for every file on it.
    """
    return resolve_workflow_role(
        account_role,
        MatterAssignment(
            is_member=matter.user_id == actor_id,
            is_responsible_lawyer=matter.responsible_lawyer_id == actor_id,
        ),
    )


def require_rta_capability(
    *,
    account_role: str,
    actor_id: str,
    matter: MatterAccessSummary,
    capability: str,
) -> RtaWorkflowRole:
    """Authorize one RTA action, or raise.

    A caller with no standing on the matter gets 404 rather than 403 so the
    matter's existence is not leaked (api-conventions §5). A member who simply
    lacks the capability gets 403 with the capability named.
    """
    role = workflow_role_for(account_role=account_role, actor_id=actor_id, matter=matter)
    if role is None or matter.user_id != actor_id:
        raise NotFoundError("The requested matter was not found.")
    if not is_rta_capability_granted(role, capability):
        raise CapabilityDeniedError(
            f"This action requires the {capability} capability.",
            capability=capability,
            workflowRole=role.value,
        )
    return role

"""Inline confirmation actions: what a card is, and what confirming it does.

The agent proposes; a human confirms; only then does anything change. This
module holds both halves so the pair cannot drift: a card kind that can be
proposed but not executed would be a dead end, and one that executes without a
declared capability would be an escalation.

Confirmation re-reads authority from scratch. Nothing about the proposal is
trusted — not the capability, not the practising status, not the target
version. A card is a suggestion with an expiry, not a stored permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from src.modules.content_governance.contracts import DigitalReviewStatus
from src.modules.matter_agent.domain.errors import PendingActionStaleError
from src.modules.matter_agent.domain.models import PendingAction, PendingActionState
from src.platform import ids
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

#: How long a card stays confirmable. Short on purpose: the matter moves, and a
#: stale suggestion is worse than none.
DEFAULT_EXPIRY = timedelta(hours=8)

CHECKLIST_DECISION = "checklist-decision"


class UnknownActionKindError(DomainRuleError):
    """A card kind with no executor. Refused rather than marked confirmed."""

    code = "agent_action_kind_unknown"
    message = "This suggestion can no longer be applied."


@dataclass(frozen=True)
class ActionSpec:
    """What a card kind needs before it may be proposed or confirmed."""

    kind: str
    capability: str
    requires_practising: bool = False


#: The closed set of card kinds. Absent from here means unproposable *and*
#: unconfirmable, so the two paths cannot disagree.
ACTION_SPECS: dict[str, ActionSpec] = {
    CHECKLIST_DECISION: ActionSpec(
        kind=CHECKLIST_DECISION,
        capability="requirement.review",
        requires_practising=False,
    ),
}


class AuthorizationPort(Protocol):
    """Capability and practising-status checks, owned by ``auth_service``."""

    async def authorize(
        self, ctx: RequestContext, capability: str, matter_id: str | None = None
    ) -> None: ...

    async def require_practising_notary(
        self, ctx: RequestContext, matter_id: str | None = None
    ) -> None: ...


class ActionExecutor:
    """Applies a confirmed card through the service that owns the decision."""

    def __init__(self, *, checklist: Any) -> None:
        self._checklist = checklist

    async def execute(self, action: PendingAction, ctx: RequestContext) -> dict[str, Any]:
        if action.action_kind != CHECKLIST_DECISION:
            raise UnknownActionKindError()

        item_id = str(action.arguments.get("itemId", ""))
        review = str(action.arguments.get("digitalReview", ""))
        if not item_id or review not in DigitalReviewStatus.__members__:
            raise UnknownActionKindError()

        view = await self._checklist.decide_satisfaction(
            user_id=ctx.actor_id,
            matter_id=action.matter_id,
            item_id=item_id,
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
            expected_version=action.target_version,
            digital_review=DigitalReviewStatus[review],
        )
        return {
            "itemId": view.item.id,
            "version": view.item.version,
            "digitalReview": view.item.digital_review.value,
            "resolution": view.computed_resolution.value,
        }


def build_pending_action(
    *,
    session_id: str,
    matter_id: str,
    user_id: str,
    kind: str,
    arguments: dict[str, Any],
    target_ref: str,
    target_version: int,
    now: datetime | None = None,
) -> PendingAction:
    """Create a card. Raises if the kind has no executor."""
    if kind not in ACTION_SPECS:
        raise UnknownActionKindError()
    moment = now or datetime.now(tz=UTC)
    return PendingAction(
        id=ids.new_id(ids.PENDING_ACTION),
        session_id=session_id,
        matter_id=matter_id,
        user_id=user_id,
        action_kind=kind,
        arguments=arguments,
        target_ref=target_ref,
        target_version=target_version,
        state=PendingActionState.PROPOSED,
        expires_at=moment + DEFAULT_EXPIRY,
        created_at=moment,
    )


def guard_target_version(action: PendingAction, current_version: int) -> None:
    """A card whose target moved must be regenerated, never applied."""
    if current_version != action.target_version:
        raise PendingActionStaleError(
            "The target changed since this suggestion was made.",
            targetRef=action.target_ref,
        )

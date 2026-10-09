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

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from src.modules.content_governance.contracts import CAP_CHECKLIST_DECIDE, DigitalReviewStatus
from src.modules.document.contracts import RequirementDocumentPort
from src.modules.matter.contracts import require_rta_capability
from src.modules.matter_agent.domain.errors import PendingActionStaleError
from src.modules.matter_agent.domain.models import PendingAction, PendingActionState
from src.platform import ids
from src.platform.errors import DomainRuleError, NotFoundError
from src.platform.request_context import RequestContext

#: How long a card stays confirmable. Short on purpose: the matter moves, and a
#: stale suggestion is worse than none.
DEFAULT_EXPIRY = timedelta(hours=8)

CHECKLIST_DECISION = "checklist-decision"
REQUIREMENT_LINK = "requirement-link"
FACT_ACCEPT = "fact-accept"


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
    REQUIREMENT_LINK: ActionSpec(REQUIREMENT_LINK, "requirement.review"),
    FACT_ACCEPT: ActionSpec(FACT_ACCEPT, "particular.verify", True),
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

    def __init__(
        self,
        *,
        checklist: Any,
        matters: Any = None,
        facts: Any = None,
        documents: RequirementDocumentPort | None = None,
    ) -> None:
        self._checklist, self._matters, self._facts = checklist, matters, facts
        self._documents = documents

    async def authorize(self, action: PendingAction, ctx: RequestContext) -> None:
        if action.action_kind == FACT_ACCEPT:
            await self._facts.authorize_decision(
                ctx, action.matter_id, str(action.arguments["factId"])
            )
        elif self._matters is not None:
            matter = await self._matters.get_access_summary(ctx.actor_id, action.matter_id)
            if matter is None:
                raise NotFoundError()
            require_rta_capability(
                account_role=ctx.account_role.value,
                actor_id=ctx.actor_id,
                matter=matter,
                capability=CAP_CHECKLIST_DECIDE,
            )

    async def current(
        self, action: PendingAction, ctx: RequestContext
    ) -> tuple[int, dict[str, Any]]:
        if action.action_kind == FACT_ACCEPT:
            view = await self._facts.get_view(
                ctx, action.matter_id, str(action.arguments["factId"])
            )
            return view.fact.version, {
                "scopeToken": view.scope_token,
                "transactionId": view.fact.transaction_id,
                "subjectId": view.fact.subject_id,
                "evidenceStale": view.fact.evidence_stale,
                "factValue": view.fact.value,
            }
        view = await self._checklist.get_checklist(user_id=ctx.actor_id, matter_id=action.matter_id)
        item_id = str(action.arguments.get("itemId", ""))
        item = next((entry.item for entry in view.items if entry.item.id == item_id), None)
        if item is None:
            raise NotFoundError()
        links = await self._checklist.list_links(user_id=ctx.actor_id, item_id=item_id)
        pins: dict[str, Any] = {
            "support": sorted(
                [
                    (
                        link.id,
                        link.detected_document_id,
                        link.document_version,
                        link.interpretation_generation,
                    )
                    for link in links
                    if link.is_live
                ],
                key=lambda pin: pin[0],
            )
        }
        if self._documents is not None:
            document_ids = {link.detected_document_id for link in links if link.is_live}
            if action.action_kind == REQUIREMENT_LINK:
                document_ids.add(str(action.arguments["detectedDocumentId"]))
            documents = []
            for document_id in sorted(document_ids):
                document = await self._documents.requirement_document(
                    ctx.actor_id, action.matter_id, document_id
                )
                if (
                    action.action_kind == REQUIREMENT_LINK
                    and document_id == action.arguments["detectedDocumentId"]
                    and (
                        document.version != action.arguments["documentVersion"]
                        or document.interpretation_generation
                        != action.arguments["interpretationGeneration"]
                    )
                ):
                    raise PendingActionStaleError()
                documents.append(asdict(document))
            pins["documents"] = documents
        return item.version, pins

    async def execute(self, action: PendingAction, ctx: RequestContext) -> dict[str, Any]:
        args = action.arguments
        if action.action_kind == FACT_ACCEPT:
            from src.modules.verification.contracts import ReviewFactInput

            fact = await self._facts.decide(
                ctx,
                action.matter_id,
                str(args["factId"]),
                ReviewFactInput(
                    action="accept",
                    expected_version=action.target_version,
                    expected_scope_token=str(args["expectedScopeToken"]),
                    resolve_fact_ids=_string_list(args.get("resolveFactIds", [])),
                    reason=str(args["reason"]) if args.get("reason") is not None else None,
                ),
                key=f"agent-action:{action.id}",
            )
            return {"factId": fact.id, "version": fact.version}
        common = {
            "user_id": ctx.actor_id,
            "matter_id": action.matter_id,
            "item_id": str(args["itemId"]),
            "actor_id": ctx.actor_id,
            "correlation_id": ctx.correlation_id,
            "expected_version": action.target_version,
        }
        if action.action_kind == REQUIREMENT_LINK:
            link = await self._checklist.link_document(
                **common,
                detected_document_id=str(args["detectedDocumentId"]),
                document_version=args["documentVersion"],
                interpretation_generation=args["interpretationGeneration"],
                evidence_reference_ids=_string_list(args.get("evidenceReferenceIds", [])),
                lawyer_confirmed=False,
                note=args.get("reason"),
            )
            return {"linkId": link.id, "itemId": link.checklist_item_id}
        if action.action_kind != CHECKLIST_DECISION:
            raise UnknownActionKindError()
        view = await self._checklist.decide_satisfaction(
            **common, digital_review=DigitalReviewStatus(str(args["digitalReview"]))
        )
        return {
            "itemId": view.item.id,
            "version": view.item.version,
            "digitalReview": view.item.digital_review.value,
            "resolution": view.computed_resolution.value,
        }


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or any(not isinstance(item, str) for item in value):
        raise DomainRuleError("The suggestion contains invalid reference identifiers.")
    return tuple(value)


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

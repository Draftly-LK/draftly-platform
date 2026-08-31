"""Write tools, each bound to the application service that owns the concept.

Every one of these has already passed the executor's gates — allowlist, matter
ownership, capability set, practising status — so none re-checks authority. Each
does the work through the owning service, which is where the domain rules live.

The line these tools must not cross is recorded in the services themselves, not
here. ``ChecklistService.administer_item`` cannot reach applicability or
satisfaction; ``compute_resolution`` decides SATISFIED; ``edit_candidate``
leaves a candidate unverified. A tool cannot widen any of that by asking
differently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.modules.content_governance.contracts import CollectionStatus, DigitalReviewStatus
from src.modules.matter_agent.application.actions import CHECKLIST_DECISION, build_pending_action
from src.modules.matter_agent.application.read_tools import _BaseTool
from src.modules.matter_agent.domain.models import SuggestionOrigin
from src.modules.matter_agent.ports import ToolInvocation, ToolResult


class RunChecksTool(_BaseTool):
    """``check.run`` — run the deterministic rule pack over confirmed facts."""

    name = "run_checks"

    def __init__(self, checks: Any, matters: Any) -> None:
        self._checks = checks
        self._matters = matters

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        summary = await self._matters.get_access_summary(invocation.actor_id, invocation.matter_id)
        result = await self._checks.run_checks(
            user_id=invocation.actor_id,
            matter_id=invocation.matter_id,
            actor_id=invocation.actor_id,
            correlation_id="",
            subtype_id=getattr(summary, "subtype_id", None) if summary else None,
        )
        results = getattr(result, "results", ())
        issues = getattr(result, "issues", ())
        return ToolResult(
            summary=(
                f"Ran the rule pack: {len(results)} results, {len(issues)} open issues. "
                "A check result is a finding, not a legal conclusion."
            ),
            payload={
                "resultCount": len(results),
                "issueCount": len(issues),
                "issues": [
                    {
                        "issueId": getattr(issue, "id", None),
                        "code": getattr(issue, "code", None),
                        "severity": _enum(getattr(issue, "severity", None)),
                    }
                    for issue in issues
                ],
            },
            resource_refs=tuple(
                str(getattr(issue, "id", "")) for issue in issues if getattr(issue, "id", None)
            ),
        )


class GenerateWorkingDraftTool(_BaseTool):
    """``draft.create`` — a working draft from an approved template.

    Only verified facts reach a draft; the draft service enforces that. A
    generated form is never registration-ready in this release.
    """

    name = "generate_working_draft"
    properties = {"templateId": {"type": "string", "description": "Optional template id."}}

    def __init__(self, drafts: Any, matters: Any) -> None:
        self._drafts = drafts
        self._matters = matters

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        summary = await self._matters.get_access_summary(invocation.actor_id, invocation.matter_id)
        if summary is None:
            return ToolResult(summary="The matter could not be read.")
        view = await self._drafts.generate_form(
            user_id=invocation.actor_id,
            matter_id=invocation.matter_id,
            actor_id=invocation.actor_id,
            correlation_id="",
            subtype_id=getattr(summary, "subtype_id", None),
            subtype_decision_status=getattr(summary, "subtype_decision_status", None),
            template_id=_optional_str(invocation.arguments.get("templateId")),
        )
        form_id = getattr(getattr(view, "form", view), "id", "")
        return ToolResult(
            summary=f"Generated working draft {form_id}. It is a draft, not an approved form.",
            payload={"formId": form_id},
            resource_refs=(form_id,) if form_id else (),
        )


class _ChecklistAdminTool(_BaseTool):
    """Shared base for the four administrative checklist writes."""

    def __init__(self, checklist: Any) -> None:
        self._checklist = checklist

    async def _administer(
        self,
        invocation: ToolInvocation,
        *,
        assigned_to: str | None = None,
        due_at: datetime | None = None,
        collection: CollectionStatus | None = None,
    ) -> ToolResult:
        item_id = str(invocation.arguments.get("itemId", ""))
        if not item_id:
            return ToolResult(summary="No checklist item id was supplied.")
        expected_version = invocation.arguments.get("expectedVersion")
        if not isinstance(expected_version, int):
            return ToolResult(
                summary="An expectedVersion is required so a concurrent change is not overwritten."
            )
        view = await self._checklist.administer_item(
            user_id=invocation.actor_id,
            matter_id=invocation.matter_id,
            item_id=item_id,
            actor_id=invocation.actor_id,
            correlation_id="",
            expected_version=expected_version,
            assigned_to=assigned_to,
            due_at=due_at,
            collection=collection,
        )
        return ToolResult(
            summary=(
                f"Updated checklist item {item_id}: "
                f"collection {_enum(view.item.collection)}, "
                f"resolution {_enum(view.computed_resolution)} (computed)."
            ),
            payload={
                "itemId": view.item.id,
                "version": view.item.version,
                "collection": _enum(view.item.collection),
                "resolution": _enum(view.computed_resolution),
                "assignedTo": view.item.assigned_to,
                "dueAt": view.item.due_at.isoformat() if view.item.due_at else None,
            },
            resource_refs=(item_id,),
        )


_ITEM_ARGS: dict[str, Any] = {
    "itemId": {"type": "string", "description": "The checklist item id."},
    "expectedVersion": {"type": "integer", "description": "The item version you read."},
}


class AssignChecklistItemTool(_ChecklistAdminTool):
    name = "assign_checklist_item"
    properties = {**_ITEM_ARGS, "assignedTo": {"type": "string"}}
    required = ["itemId", "expectedVersion", "assignedTo"]

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        assignee = _optional_str(invocation.arguments.get("assignedTo"))
        if assignee is None:
            return ToolResult(summary="No assignee was supplied.")
        return await self._administer(invocation, assigned_to=assignee)


class UpdateChecklistDueDateTool(_ChecklistAdminTool):
    name = "update_checklist_due_date"
    properties = {
        **_ITEM_ARGS,
        "dueAt": {"type": "string", "description": "ISO-8601 timestamp."},
    }
    required = ["itemId", "expectedVersion", "dueAt"]

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        due = _parse_iso(invocation.arguments.get("dueAt"))
        if due is None:
            return ToolResult(summary="dueAt must be an ISO-8601 timestamp.")
        return await self._administer(invocation, due_at=due)


class RequestChecklistCollectionTool(_ChecklistAdminTool):
    """Ask for a document. Refuses if evidence has already arrived."""

    name = "request_checklist_collection"
    properties = dict(_ITEM_ARGS)
    required = ["itemId", "expectedVersion"]

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        return await self._administer(invocation, collection=CollectionStatus.REQUESTED)


class RecordDocumentReceiptTool(_ChecklistAdminTool):
    """Record that a document arrived.

    RECEIVED only. SATISFIED is computed from the requirement's policy and is
    unreachable from here — *we received something* is not *a lawyer accepted
    it as legally sufficient*.
    """

    name = "record_document_receipt"
    properties = dict(_ITEM_ARGS)
    required = ["itemId", "expectedVersion"]

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        return await self._administer(invocation, collection=CollectionStatus.RECEIVED)


class ProposeDocumentLinkTool(_BaseTool):
    """``document.propose-link`` — offer a document towards a requirement.

    Always ``lawyer_confirmed=False``: the link is a candidate. The
    specification also describes document-to-parcel links, but no parcel
    aggregate exists in the domain, so only the requirement link is offered
    rather than inventing a second shape.
    """

    name = "propose_document_link"
    properties = {
        "itemId": {"type": "string", "description": "The checklist item id."},
        "detectedDocumentId": {"type": "string", "description": "The detected document id."},
        "note": {"type": "string", "description": "Why this document may satisfy the item."},
    }
    required = ["itemId", "detectedDocumentId"]

    def __init__(self, checklist: Any) -> None:
        self._checklist = checklist

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        item_id = str(invocation.arguments.get("itemId", ""))
        document_id = str(invocation.arguments.get("detectedDocumentId", ""))
        if not (item_id and document_id):
            return ToolResult(summary="Both itemId and detectedDocumentId are required.")
        link = await self._checklist.link_document(
            user_id=invocation.actor_id,
            matter_id=invocation.matter_id,
            item_id=item_id,
            detected_document_id=document_id,
            actor_id=invocation.actor_id,
            correlation_id="",
            lawyer_confirmed=False,
            note=_optional_str(invocation.arguments.get("note")),
        )
        return ToolResult(
            summary=(
                f"Proposed document {document_id} towards item {item_id}. "
                "Unconfirmed until a lawyer accepts the evidence."
            ),
            payload={"linkId": getattr(link, "id", None), "lawyerConfirmed": False},
            resource_refs=(item_id, document_id),
        )


class ProposeChecklistDecisionTool(_BaseTool):
    """``requirement.review`` — propose a digital-review decision as a card.

    Creates a pending action and changes nothing. The decision is a legal one,
    so it waits for a human who holds the capability, and confirmation re-reads
    that capability rather than trusting this proposal.
    """

    name = "propose_checklist_decision"
    properties = {
        "itemId": {"type": "string", "description": "The checklist item id."},
        "expectedVersion": {"type": "integer", "description": "The item version you read."},
        "digitalReview": {
            "type": "string",
            "description": "Proposed digital review status, e.g. REVIEWED_OK.",
        },
        "rationale": {"type": "string", "description": "Why, in one sentence."},
    }
    required = ["itemId", "expectedVersion", "digitalReview"]

    def __init__(self, actions: Any, *, session_id: str) -> None:
        self._actions = actions
        self._session_id = session_id

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        item_id = str(invocation.arguments.get("itemId", ""))
        review = _optional_str(invocation.arguments.get("digitalReview"))
        expected_version = invocation.arguments.get("expectedVersion")
        if not item_id or review is None or not isinstance(expected_version, int):
            return ToolResult(summary="itemId, expectedVersion and digitalReview are all required.")
        if review not in DigitalReviewStatus.__members__:
            return ToolResult(summary=f"{review} is not a digital review status.")

        action = build_pending_action(
            session_id=self._session_id,
            matter_id=invocation.matter_id,
            user_id=invocation.actor_id,
            kind=CHECKLIST_DECISION,
            arguments={"itemId": item_id, "digitalReview": review},
            target_ref=f"checklist-item:{item_id}",
            target_version=expected_version,
        )
        await self._actions.create(action)
        return ToolResult(
            summary=(
                f"Proposed a digital-review decision on item {item_id}. "
                "Nothing has changed: a lawyer must confirm it."
            ),
            payload={"actionId": action.id, "actionKind": action.action_kind},
            resource_refs=(item_id,),
            pending_action_id=action.id,
        )


class UpdateFieldCandidateTool(_BaseTool):
    """``candidate.update`` — correct an unverified candidate value.

    The candidate stays unverified. A verified fact is never touched: the
    review service refuses an approved candidate outright.
    """

    name = "update_field_candidate"
    properties = {
        "candidateId": {"type": "string"},
        "value": {"type": "string"},
        "expectedVersion": {"type": "integer"},
    }
    required = ["candidateId", "value", "expectedVersion"]

    def __init__(self, review: Any) -> None:
        self._review = review

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        candidate_id = str(invocation.arguments.get("candidateId", ""))
        value = _optional_str(invocation.arguments.get("value"))
        expected_version = invocation.arguments.get("expectedVersion")
        if not candidate_id or value is None or not isinstance(expected_version, int):
            return ToolResult(summary="candidateId, value and expectedVersion are all required.")
        candidate = await self._review.edit_candidate(
            user_id=invocation.actor_id,
            actor_id=invocation.actor_id,
            candidate_id=candidate_id,
            value=value,
            expected_version=expected_version,
            correlation_id="",
        )
        return ToolResult(
            # Never echoes the value: a candidate value is matter content.
            summary=(
                f"Updated candidate {candidate_id} to version {candidate.version}. "
                "Still unverified — a lawyer must approve it."
            ),
            payload={
                "candidateId": candidate.id,
                "version": candidate.version,
                "reviewState": candidate.review_state,
            },
            resource_refs=(candidate_id,),
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _enum(value: Any) -> Any:
    return getattr(value, "value", value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_iso(value: Any) -> datetime | None:
    text = _optional_str(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


AI_SUGGESTED = SuggestionOrigin.AI_SUGGESTED.value

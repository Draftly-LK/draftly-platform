"""Current matter-scoped reads through their owning application contracts."""

from dataclasses import asdict
from typing import Any

from src.modules.matter_agent.application.read_tools import _BaseTool
from src.modules.matter_agent.domain.models import AgentCitation
from src.modules.matter_agent.ports import ToolInvocation, ToolResult
from src.platform.errors import DomainRuleError


class ReadRegisterTool(_BaseTool):
    name = "read_verified_facts"
    properties = {"after": {"type": "string", "description": "Next fact ID from a previous page."}}

    def __init__(self, facts: Any) -> None:
        self._facts = facts

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.context is None:
            raise DomainRuleError()
        views, more = await self._facts.list_facts(
            invocation.context,
            invocation.matter_id,
            limit=25,
            after=invocation.arguments.get("after"),
        )
        citations = []
        rows = []
        for view in views:
            fact = view.fact
            reviewed = (
                fact.status.value in ("LAWYER_CONFIRMED", "LOCKED_FOR_FORM")
                and not fact.evidence_stale
                and not view.conflict_fact_ids
                and fact.scope_status == "assigned"
            )
            evidence = view.evidence[0] if view.evidence else None
            citations.append(
                AgentCitation(
                    source_id=fact.id,
                    source_type="fact",
                    label=fact.fact_type_id,
                    verification_status="verified" if reviewed else "unverified",
                    version=fact.version,
                    transaction_id=fact.transaction_id,
                    subject_id=fact.subject_id,
                    source_file_id=evidence.source_file_id if evidence else None,
                    page=evidence.page_number if evidence else None,
                )
            )
            rows.append(
                {
                    "factId": fact.id,
                    "factTypeId": fact.fact_type_id,
                    "value": fact.value,
                    "version": fact.version,
                    "status": fact.status.value,
                    "reviewed": reviewed,
                    "transactionId": fact.transaction_id,
                    "subjectId": fact.subject_id,
                    "scopeStatus": fact.scope_status,
                    "evidenceStale": fact.evidence_stale,
                    "scopeToken": view.scope_token,
                    "conflictFactIds": list(view.conflict_fact_ids),
                    "evidence": [
                        {
                            "sourceFileId": e.source_file_id,
                            "page": e.page_number,
                            "evidenceId": e.id,
                        }
                        for e in view.evidence
                    ],
                }
            )
        return ToolResult(
            summary=f"Read {len(rows)} register entries; review state and scope are explicit.",
            payload={
                "facts": rows,
                "hasMore": more,
                "nextAfter": views[-1].fact.id if more and views else None,
            },
            resource_refs=tuple(c.source_id for c in citations),
            citations=tuple(citations),
        )


class ReadScopeInventoryTool(_BaseTool):
    name = "list_matter_inventory"
    properties = {"afterSubject": {"type": "string"}, "afterTransaction": {"type": "string"}}

    def __init__(self, scopes: Any) -> None:
        self._scopes = scopes

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.context is None:
            raise DomainRuleError()
        subjects = await self._scopes.list_subjects(
            invocation.context,
            invocation.matter_id,
            limit=100,
            after=invocation.arguments.get("afterSubject"),
        )
        transactions = await self._scopes.list_transactions(
            invocation.context,
            invocation.matter_id,
            limit=100,
            after=invocation.arguments.get("afterTransaction"),
        )
        return ToolResult(
            summary="Read explicit subject and transaction bindings with association revisions.",
            payload={
                "subjects": [asdict(s) for s in subjects],
                "transactions": [asdict(t) for t in transactions],
                "subjectsMayHaveMore": len(subjects) == 100,
                "transactionsMayHaveMore": len(transactions) == 100,
            },
            resource_refs=(invocation.matter_id,),
        )


class ReadReadinessTool(_BaseTool):
    name = "read_matter_readiness"

    def __init__(self, readiness: Any) -> None:
        self._readiness = readiness

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.context is None:
            raise DomainRuleError()
        state = await self._readiness.evaluate(invocation.context, invocation.matter_id)
        return ToolResult(
            summary=f"Operational readiness is {state.state}; next action: {state.next_action}.",
            payload=asdict(state),
            resource_refs=(invocation.matter_id,),
        )

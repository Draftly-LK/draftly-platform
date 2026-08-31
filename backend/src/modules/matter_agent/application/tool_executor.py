"""The tool executor — where a model proposal becomes a refusal or an effect.

Gemini emits *proposals*. This module decides. Every call passes
``authorize_tool`` before anything runs, and every call — executed or refused —
produces a ``ToolCallRecord`` and an audit event
(``matter-agent-service.md`` §Audit of tool calls).

The refusal path matters more than the success path: it is what a prompt
injection meets. A tool outside the allowlist fails here, not in the model's
judgement, so an instruction hidden inside OCR text cannot widen scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.matter_agent.domain.allowlist import get_tool
from src.modules.matter_agent.domain.models import ToolCallOutcome, ToolCallRecord
from src.modules.matter_agent.domain.permission import DenialReason, authorize_tool
from src.modules.matter_agent.ports import (
    AgentEventPort,
    AgentToolPort,
    ProposedToolCall,
    ToolCallRepository,
    ToolInvocation,
    ToolResult,
)
from src.platform import ids
from src.platform.errors import DraftlyError
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)

#: Arguments are never logged or audited. Only their keys are, so a malformed
#: call is diagnosable without putting matter content in the audit tier.
_SAFE_SUMMARY_KEYS = 12


@dataclass(frozen=True)
class ExecutionContext:
    """Everything the executor needs that is not the call itself."""

    ctx: RequestContext
    session_id: str
    matter_id: str
    job_id: str
    model_version: str
    prompt_version: str
    user_capabilities: frozenset[str]
    matter_owned: bool
    is_practising_notary: bool = False


@dataclass(frozen=True)
class ExecutedTool:
    """The outcome of one proposal, always recorded."""

    tool: str
    outcome: ToolCallOutcome
    reason_code: str | None = None
    result: ToolResult | None = None


def safe_input_summary(arguments: Mapping[str, object]) -> str:
    """Argument *keys* only. Values may be matter content and never appear."""
    keys = sorted(str(key) for key in arguments)[:_SAFE_SUMMARY_KEYS]
    return ",".join(keys)


class ToolExecutor:
    """Validates and runs one proposed tool call."""

    def __init__(
        self,
        *,
        tools: Mapping[str, AgentToolPort],
        tool_calls: ToolCallRepository,
        audit: AuditPort,
        events: AgentEventPort | None = None,
    ) -> None:
        self._tools = tools
        self._tool_calls = tool_calls
        self._audit = audit
        self._events = events

    async def execute(
        self,
        proposal: ProposedToolCall,
        execution: ExecutionContext,
    ) -> ExecutedTool:
        started_at = datetime.now(tz=UTC)
        decision = authorize_tool(
            tool_name=proposal.name,
            user_capabilities=execution.user_capabilities,
            matter_owned=execution.matter_owned,
            is_practising_notary=execution.is_practising_notary,
        )

        tool_spec = get_tool(proposal.name)
        capability = ",".join(sorted(tool_spec.capabilities)) if tool_spec else None

        if not decision.granted:
            reason = decision.reason or DenialReason.DOMAIN_REFUSED
            return await self._record(
                execution,
                proposal,
                started_at,
                capability=capability,
                outcome=ToolCallOutcome.DENIED,
                reason_code=reason.value,
            )

        implementation = self._tools.get(proposal.name)
        if implementation is None:
            # Allowlisted and authorised, but not wired. Refused explicitly and
            # with its own reason code, so a missing feature never reads as a
            # security refusal and never looks like a completed action.
            return await self._record(
                execution,
                proposal,
                started_at,
                capability=capability,
                outcome=ToolCallOutcome.DENIED,
                reason_code=DenialReason.TOOL_NOT_IMPLEMENTED.value,
            )

        try:
            result = await implementation.execute(
                ToolInvocation(
                    tool_name=proposal.name,
                    arguments=dict(proposal.arguments),
                    matter_id=execution.matter_id,
                    actor_id=execution.ctx.actor_id,
                )
            )
        except DraftlyError as exc:
            return await self._record(
                execution,
                proposal,
                started_at,
                capability=capability,
                outcome=ToolCallOutcome.FAILED,
                reason_code=exc.code,
            )

        return await self._record(
            execution,
            proposal,
            started_at,
            capability=capability,
            outcome=ToolCallOutcome.EXECUTED,
            reason_code=None,
            result=result,
        )

    async def _record(
        self,
        execution: ExecutionContext,
        proposal: ProposedToolCall,
        started_at: datetime,
        *,
        capability: str | None,
        outcome: ToolCallOutcome,
        reason_code: str | None,
        result: ToolResult | None = None,
    ) -> ExecutedTool:
        record = ToolCallRecord(
            id=ids.new_id(ids.AGENT_TOOL_CALL),
            session_id=execution.session_id,
            matter_id=execution.matter_id,
            user_id=execution.ctx.actor_id,
            actor_id=execution.ctx.actor_id,
            job_id=execution.job_id,
            tool=proposal.name,
            capability=capability,
            outcome=outcome,
            reason_code=reason_code,
            model_version=execution.model_version,
            prompt_version=execution.prompt_version,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            result_refs=result.resource_refs if result else (),
            input_summary=safe_input_summary(proposal.arguments),
        )
        await self._tool_calls.record(record)
        await self._audit.record(
            AuditEventInput(
                user_id=execution.ctx.actor_id,
                matter_id=execution.matter_id,
                actor=execution.ctx.actor_id,
                action=f"agent.tool-{outcome.value}",
                target_type="agent_tool_call",
                target_id=record.id,
                reason=reason_code,
                correlation_id=execution.ctx.correlation_id,
            )
        )
        if self._events is not None:
            await self._events.publish(
                "agent.tool-denied" if outcome is ToolCallOutcome.DENIED else "agent.tool-executed",
                user_id=execution.ctx.actor_id,
                matter_id=execution.matter_id,
                actor_id=execution.ctx.actor_id,
                correlation_id=execution.ctx.correlation_id,
                idempotency_key=f"agent.tool:{record.id}",
                data={
                    "toolCallId": record.id,
                    "tool": proposal.name,
                    "capability": capability,
                    **({"reasonCode": reason_code} if outcome is ToolCallOutcome.DENIED else {}),
                },
            )
        if outcome is ToolCallOutcome.DENIED:
            # Identifiers and reason codes only — no arguments, no content.
            log.info(
                "agent.tool_denied",
                tool=proposal.name,
                capability=capability,
                reason=reason_code,
                session_id=execution.session_id,
            )
        return ExecutedTool(
            tool=proposal.name,
            outcome=outcome,
            reason_code=reason_code,
            result=result,
        )

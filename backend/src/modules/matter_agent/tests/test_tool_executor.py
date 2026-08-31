"""The executor decides; the model only proposes.

The refusal path is the interesting one: it is what a prompt injection meets,
and it must leave a record.
"""

from __future__ import annotations

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import CAPABILITY_MAP
from src.modules.matter_agent.application.tool_executor import (
    ExecutionContext,
    ToolExecutor,
    safe_input_summary,
)
from src.modules.matter_agent.domain.models import ToolCallOutcome
from src.modules.matter_agent.domain.permission import DenialReason
from src.modules.matter_agent.ports import ProposedToolCall, ToolResult
from src.modules.matter_agent.tests.fakes import FakeAudit, FakeToolCallRepo, RecordingTool
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

APPROVER = CAPABILITY_MAP[Role.APPROVER]


def make_execution(
    *,
    capabilities: frozenset[str] = APPROVER,
    matter_owned: bool = True,
    practising: bool = True,
) -> ExecutionContext:
    return ExecutionContext(
        ctx=RequestContext(actor_id="usr-1", account_role=Role.APPROVER, correlation_id="corr-1"),
        session_id="asess-1",
        matter_id="mat-1",
        job_id="ajob-1",
        model_version="fake-1",
        prompt_version="v1",
        user_capabilities=capabilities,
        matter_owned=matter_owned,
        is_practising_notary=practising,
    )


def build(tools: dict[str, RecordingTool] | None = None):
    calls = FakeToolCallRepo()
    audit = FakeAudit()
    executor = ToolExecutor(tools=tools or {}, tool_calls=calls, audit=audit)
    return executor, calls, audit


class TestRefusals:
    async def test_a_tool_outside_the_allowlist_never_runs(self) -> None:
        tool = RecordingTool("delete_everything")
        executor, calls, audit = build({"delete_everything": tool})

        outcome = await executor.execute(
            ProposedToolCall(name="delete_everything", arguments={}), make_execution()
        )

        assert outcome.outcome is ToolCallOutcome.DENIED
        assert outcome.reason_code == DenialReason.TOOL_NOT_ALLOWLISTED.value
        assert tool.invocations == [], "an unallowlisted tool must not be invoked"
        assert calls.records[0].outcome is ToolCallOutcome.DENIED
        assert "agent.tool-denied" in audit.actions()

    async def test_a_denial_is_audited_as_deliberately_as_a_success(self) -> None:
        executor, calls, audit = build()
        await executor.execute(
            ProposedToolCall(name="run_checks", arguments={}),
            make_execution(capabilities=frozenset()),
        )
        record = calls.records[0]
        assert record.reason_code == DenialReason.CAPABILITY_NOT_HELD.value
        assert record.tool == "run_checks"
        assert record.actor_id == "usr-1"
        assert record.model_version == "fake-1"
        assert len(audit.events) == 1

    async def test_an_allowlisted_but_unimplemented_tool_is_refused_not_ignored(self) -> None:
        """An unimplemented tool must never look like a completed action."""
        executor, calls, _ = build()
        outcome = await executor.execute(
            ProposedToolCall(name="run_checks", arguments={}), make_execution()
        )
        assert outcome.outcome is ToolCallOutcome.DENIED
        assert calls.records[0].outcome is ToolCallOutcome.DENIED

    async def test_a_foreign_matter_refuses_before_the_capability_is_considered(self) -> None:
        executor, calls, _ = build()
        await executor.execute(
            ProposedToolCall(name="run_checks", arguments={}),
            make_execution(capabilities=frozenset(), matter_owned=False),
        )
        assert calls.records[0].reason_code == DenialReason.MATTER_NOT_OWNED.value


class TestExecution:
    async def test_an_authorised_call_runs_and_is_recorded(self) -> None:
        tool = RecordingTool(
            "save_working_note", result=ToolResult(summary="Saved.", resource_refs=("note-1",))
        )
        executor, calls, audit = build({"save_working_note": tool})

        outcome = await executor.execute(
            ProposedToolCall(name="save_working_note", arguments={"body": "hello"}),
            make_execution(),
        )

        assert outcome.outcome is ToolCallOutcome.EXECUTED
        assert tool.invocations[0].arguments == {"body": "hello"}
        assert tool.invocations[0].actor_id == "usr-1"
        assert calls.records[0].result_refs == ("note-1",)
        assert "agent.tool-executed" in audit.actions()

    async def test_a_tool_that_refuses_is_recorded_as_failed_with_its_code(self) -> None:
        class Refusing(RecordingTool):
            async def execute(self, invocation):  # type: ignore[no-untyped-def]
                raise DomainRuleError("no", code="nope")

        executor, calls, _ = build({"save_working_note": Refusing("save_working_note")})
        outcome = await executor.execute(
            ProposedToolCall(name="save_working_note", arguments={}), make_execution()
        )
        assert outcome.outcome is ToolCallOutcome.FAILED


class TestPrivacy:
    def test_the_input_summary_records_keys_and_never_values(self) -> None:
        summary = safe_input_summary(
            {"body": "The NIC on the deed is 199012345678", "matterId": "mat-1"}
        )
        assert summary == "body,matterId"
        assert "199012345678" not in summary

    async def test_no_argument_value_reaches_the_tool_call_record(self) -> None:
        executor, calls, _ = build()
        secret = "Perera, NIC 199012345678"
        await executor.execute(
            ProposedToolCall(name="run_checks", arguments={"note": secret}),
            make_execution(capabilities=frozenset()),
        )
        assert secret not in calls.records[0].input_summary

"""The turn loop: bounded, degradable, and honest about what it cannot answer."""

from __future__ import annotations

import asyncio

from src.modules.auth.domain.models import Role
from src.modules.auth.domain.policies import CAPABILITY_MAP
from src.modules.matter_agent.application.tool_executor import ExecutionContext, ToolExecutor
from src.modules.matter_agent.application.turn_runner import TurnRequest, TurnRunner
from src.modules.matter_agent.domain.allowlist import ALLOWLISTED_CAPABILITIES
from src.modules.matter_agent.domain.errors import ModelProviderError
from src.modules.matter_agent.domain.models import JobState, MessageRole, TurnBudget
from src.modules.matter_agent.infrastructure.fake_model import FakeAgentModelAdapter
from src.modules.matter_agent.ports import ModelTurn, ProposedToolCall, ToolResult
from src.modules.matter_agent.tests.fakes import (
    FakeConversation,
    FakeMemory,
    FakeToolCallRepo,
    RecordingTool,
    make_session,
)
from src.platform.request_context import RequestContext
from tests.factories.audit import FakeAudit

APPROVER = CAPABILITY_MAP[Role.APPROVER]
REVIEWER = CAPABILITY_MAP[Role.REVIEWER]


class FailingModel:
    """A provider that is down."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls = 0
        self.offered_tools: list[tuple[str, ...]] = []
        self.seen_history_lengths: list[int] = []
        self.seen_memory: list[tuple[str, ...]] = []

    async def run_turn(self, **kwargs: object) -> ModelTurn:
        self.calls += 1
        raise self._error


class SlowModel:
    """A provider that answers, but not before the turn budget expires."""

    def __init__(self, *, delay_seconds: float) -> None:
        self._delay = delay_seconds
        self.calls = 0
        self.offered_tools: list[tuple[str, ...]] = []
        self.seen_history_lengths: list[int] = []
        self.seen_memory: list[tuple[str, ...]] = []

    async def run_turn(self, **kwargs: object) -> ModelTurn:
        self.calls += 1
        await asyncio.sleep(self._delay)
        return ModelTurn(text="too late")


def make_runner(
    *,
    turns: list[ModelTurn] | None = None,
    memory: FakeMemory | None = None,
    tools: dict[str, RecordingTool] | None = None,
    model: object | None = None,
):
    conversation = FakeConversation()
    calls = FakeToolCallRepo()
    model = model or FakeAgentModelAdapter(turns or [])
    runner = TurnRunner(
        model=model,
        conversation=conversation,
        memory=memory or FakeMemory(),
        executor=ToolExecutor(tools=tools or {}, tool_calls=calls, audit=FakeAudit()),
    )
    return runner, conversation, model, calls


def make_request(
    *,
    message: str = "What documents are outstanding?",
    capabilities: frozenset[str] = APPROVER,
    budget: TurnBudget | None = None,
) -> TurnRequest:
    session = make_session()
    return TurnRequest(
        session=session,
        job_id="ajob-1",
        user_message=message,
        budget=budget or TurnBudget(),
        execution=ExecutionContext(
            ctx=RequestContext(actor_id="usr-1", account_role=Role.APPROVER),
            session_id=session.id,
            matter_id=session.matter_id,
            job_id="ajob-1",
            model_version="fake-1",
            prompt_version="v1",
            user_capabilities=capabilities,
            matter_owned=True,
            is_practising_notary=True,
        ),
    )


class TestTheHappyPath:
    async def test_a_plain_turn_appends_exactly_one_assistant_message(self) -> None:
        runner, conversation, _, _ = make_runner(turns=[ModelTurn(text="Two are outstanding.")])
        result = await runner.run(make_request())

        assert result.outcome is JobState.SUCCEEDED
        assert len(conversation.messages) == 1
        assert conversation.messages[0].role is MessageRole.ASSISTANT
        assert conversation.messages[0].content == "Two are outstanding."

    async def test_a_tool_result_summary_feeds_the_next_model_call(self) -> None:
        tool = RecordingTool("save_working_note", result=ToolResult(summary="Saved a note."))
        runner, _, model, _ = make_runner(
            turns=[
                ModelTurn(tool_calls=(ProposedToolCall(name="save_working_note", arguments={}),)),
                ModelTurn(text="Done."),
            ],
            tools={"save_working_note": tool},
        )
        await runner.run(make_request())
        assert "Saved a note." in model.seen_memory[-1]


class TestBudget:
    async def test_the_loop_stops_at_the_tool_call_ceiling(self) -> None:
        """A model that only ever proposes tools cannot spin forever."""
        looping = ModelTurn(tool_calls=(ProposedToolCall(name="run_checks", arguments={}),))
        runner, _, _, calls = make_runner(turns=[looping] * 50)

        result = await runner.run(make_request(budget=TurnBudget(max_tool_calls=3)))

        assert result.tool_call_count == 3
        assert len(calls.records) == 3

    async def test_history_is_capped_at_the_budget(self) -> None:
        runner, conversation, model, _ = make_runner(turns=[ModelTurn(text="ok")])
        session = make_session()
        for index in range(30):
            await conversation.append(session=session, role=MessageRole.USER, content=f"m{index}")
        await runner.run(make_request(budget=TurnBudget(history_messages=5)))
        assert model.seen_history_lengths[0] == 5


class TestDegradation:
    async def test_a_dead_memory_provider_does_not_fail_the_turn(self) -> None:
        """Invariant 10: Supermemory failure degrades recall and nothing else."""
        runner, conversation, model, _ = make_runner(
            turns=[ModelTurn(text="Answered without recall.")],
            memory=FakeMemory(fail=True),
        )
        result = await runner.run(make_request())

        assert result.outcome is JobState.SUCCEEDED
        assert len(conversation.messages) == 1
        assert model.seen_memory[0] == ()

    async def test_a_scope_that_is_not_ready_is_not_an_error(self) -> None:
        memory = FakeMemory(hits=("remembered",), ready=False)
        runner, _, model, _ = make_runner(turns=[ModelTurn(text="ok")], memory=memory)
        result = await runner.run(make_request())

        assert result.outcome is JobState.SUCCEEDED
        assert memory.retrieve_calls == 0
        assert model.seen_memory[0] == ()

    async def test_memory_is_used_when_the_scope_is_ready(self) -> None:
        runner, _, model, _ = make_runner(
            turns=[ModelTurn(text="ok")], memory=FakeMemory(hits=("prior context",))
        )
        await runner.run(make_request())
        assert model.seen_memory[0] == ("prior context",)


class TestAbstention:
    async def test_a_legal_question_abstains_instead_of_answering(self) -> None:
        """Until retrieval exists, model knowledge is never a legal answer."""
        runner, conversation, model, _ = make_runner(
            turns=[ModelTurn(text="Section 12 says you may.")]
        )
        result = await runner.run(
            make_request(message="Am I required under the Notaries Ordinance to attest this?")
        )

        assert model.calls == 0, "the model must not be consulted at all"
        assert result.failure_class == "legal_research_unavailable"
        assert "not available yet" in conversation.messages[0].content

    async def test_an_operational_question_is_not_treated_as_legal(self) -> None:
        runner, _, model, _ = make_runner(turns=[ModelTurn(text="Three outstanding.")])
        await runner.run(make_request(message="Which documents are still outstanding?"))
        assert model.calls == 1


class TestToolExposure:
    async def test_only_tools_the_caller_can_execute_are_offered(self) -> None:
        runner, _, model, _ = make_runner(turns=[ModelTurn(text="ok")])
        await runner.run(make_request(capabilities=frozenset()))

        offered = set(model.offered_tools[0])
        assert "run_checks" not in offered
        assert "read_matter_summary" in offered, "reads need only matter ownership"

    async def test_a_reviewer_never_exceeds_an_approver(self) -> None:
        """Equality here is the correct outcome, and it is the point.

        The allowlist exposes no approver-only capability, so a practising
        reviewer and a practising approver reach exactly the same tools. The
        agent adds no authority to either; everything an approver can do that a
        reviewer cannot — approve, export, attest — is outside the allowlist.
        """
        runner, _, model, _ = make_runner(turns=[ModelTurn(text="ok")])
        await runner.run(make_request(capabilities=REVIEWER))
        reviewer_tools = set(model.offered_tools[0])

        runner2, _, model2, _ = make_runner(turns=[ModelTurn(text="ok")])
        await runner2.run(make_request(capabilities=APPROVER))
        approver_tools = set(model2.offered_tools[0])

        assert reviewer_tools <= approver_tools
        approver_only = APPROVER - REVIEWER
        assert not (approver_only & ALLOWLISTED_CAPABILITIES), (
            "the allowlist must expose no approver-only capability"
        )

    async def test_no_prohibited_capability_is_ever_offered(self) -> None:
        runner, _, model, _ = make_runner(turns=[ModelTurn(text="ok")])
        await runner.run(make_request(capabilities=APPROVER))
        offered = set(model.offered_tools[0])
        for forbidden in ("approve_draft", "create_export", "attest_instrument", "place_hold"):
            assert forbidden not in offered


class TestFailure:
    async def test_an_unavailable_model_appends_no_assistant_message(self) -> None:
        """The user's message stays; the job reports the failure."""
        runner, conversation, _, _ = make_runner(model=FailingModel(ModelProviderError()))
        result = await runner.run(make_request())

        assert result.outcome is JobState.FAILED
        assert result.failure_class == "model_unavailable"
        assert conversation.messages == [], "a failed turn never fabricates a reply"

    async def test_a_turn_that_overruns_its_budget_fails_without_a_reply(self) -> None:
        runner, conversation, _, _ = make_runner(model=SlowModel(delay_seconds=5))
        result = await runner.run(make_request(budget=TurnBudget(timeout_seconds=1)))

        assert result.outcome is JobState.FAILED
        assert result.failure_class == "turn_timeout"
        assert conversation.messages == []

"""Task 6 regression contracts, synthetic data only."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from src.modules.matter_agent.application.read_tools import ReadDocumentExtractionTool
from src.modules.matter_agent.domain.models import PendingActionState
from src.modules.matter_agent.tests.fakes import FakePendingActions, make_pending_action
from src.modules.matter_agent.tests.test_agent_service import CTX, build
from src.modules.matter_agent.tests.test_turn_runner import make_request, make_runner
from src.platform.errors import CapabilityDeniedError


def test_model_receives_only_installed_tool_and_real_required_arguments():
    tool = ReadDocumentExtractionTool(AsyncMock())
    runner, *_ = make_runner(tools={tool.name: tool})
    declarations = runner._declarations(make_request().execution)
    assert [item.name for item in declarations] == [tool.name]
    assert declarations[0].parameters["required"] == ["detectedDocumentId"]
    assert declarations[0].parameters["additionalProperties"] is False


async def test_confirmed_replay_reauthorizes_before_returning_card():
    action = replace(make_pending_action(), state=PendingActionState.CONFIRMED)
    service, *_ = build(actions=FakePendingActions(seed=[action]))
    service._authorizer = AsyncMock()
    service._authorizer.authorize.side_effect = CapabilityDeniedError()
    with pytest.raises(CapabilityDeniedError):
        await service.confirm_action(CTX, "mat-1", action_id=action.id)


async def test_installed_genai_http_transport_preserves_closed_json_schema():
    """Exercise the installed SDK's request conversion, without network/provider use."""
    import json

    import httpx
    from google import genai
    from google.genai import types

    from src.modules.matter_agent.infrastructure.gemini_adapter import _build_config

    requests = []

    async def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"role": "model", "parts": [{"text": "synthetic"}]}}]},
        )

    declaration = ReadDocumentExtractionTool(AsyncMock()).declaration()
    async with genai.Client(
        api_key="synthetic-no-network",
        http_options=types.HttpOptions(
            async_client_args={"transport": httpx.MockTransport(handle)}
        ),
    ).aio as client:
        await client.models.generate_content(
            model="synthetic-model",
            contents="synthetic",
            config=_build_config("synthetic", [declaration]),
        )
    sent = requests[0]["tools"][0]["functionDeclarations"][0]
    assert sent["parameters_json_schema"] == declaration.parameters
    assert sent["parameters_json_schema"]["additionalProperties"] is False
    assert sent["parameters_json_schema"]["required"] == ["detectedDocumentId"]


@pytest.mark.parametrize(
    "arguments", [{}, {"detectedDocumentId": 2}, {"detectedDocumentId": "d", "matterId": "foreign"}]
)
async def test_invalid_typed_arguments_cannot_reach_owner(arguments):
    from src.modules.matter_agent.domain.models import ToolCallOutcome
    from src.modules.matter_agent.ports import ProposedToolCall
    from src.modules.matter_agent.tests.test_tool_executor import build as executor
    from src.modules.matter_agent.tests.test_tool_executor import make_execution

    documents = AsyncMock()
    tool = ReadDocumentExtractionTool(documents)
    runner, _, _ = executor({tool.name: tool})
    result = await runner.execute(ProposedToolCall(tool.name, arguments), make_execution())
    assert result.outcome is ToolCallOutcome.DENIED
    documents.extraction_for_agent.assert_not_called()


async def test_pinned_proposal_executes_once_and_preserves_result_and_audit():
    service, _, _, audit, _, _ = build()
    owner = AsyncMock()
    owner.current.return_value = (3, {"support": [["link-synthetic", "document-synthetic", 1, 2]]})
    owner.execute.return_value = {"itemId": "cli-1", "version": 4}
    service._action_executor = owner
    card = await service.propose_action(
        CTX,
        "mat-1",
        session_id="asess-1",
        kind="checklist-decision",
        arguments={"itemId": "cli-1", "digitalReview": "REVIEWED_OK"},
        target_ref="checklist-item:cli-1",
        target_version=3,
    )
    first = await service.confirm_action(CTX, "mat-1", action_id=card.id)
    again = await service.confirm_action(CTX, "mat-1", action_id=card.id)
    assert first == again and first.state is PendingActionState.EXECUTED
    assert first.result == {"itemId": "cli-1", "version": 4}
    owner.execute.assert_awaited_once()
    assert owner.authorize.await_count == 3
    assert audit.actions().count("agent.action-confirmed") == 1


async def test_changed_support_generation_invalidates_same_target_version():
    from src.modules.matter_agent.domain.errors import PendingActionStaleError

    service, _, _, audit, _, actions = build()
    owner = AsyncMock()
    owner.current.return_value = (3, {"support": [["link", "doc", 1, 2]]})
    service._action_executor = owner
    card = await service.propose_action(
        CTX,
        "mat-1",
        session_id="asess-1",
        kind="checklist-decision",
        arguments={"itemId": "cli-1"},
        target_ref="checklist-item:cli-1",
        target_version=3,
    )
    owner.current.return_value = (3, {"support": [["link", "doc", 1, 3]]})
    with pytest.raises(PendingActionStaleError):
        await service.confirm_action(CTX, "mat-1", action_id=card.id)
    assert actions.rows[card.id].state is PendingActionState.STALE
    owner.execute.assert_not_called()
    assert "agent.action-stale" in audit.actions()


async def test_other_actor_cannot_read_or_confirm_owning_actor_proposal():
    from src.modules.matter_agent.domain.errors import PendingActionNotFoundError
    from src.modules.matter_agent.tests.test_agent_service import OTHER

    service, *_ = build(
        actions=FakePendingActions(seed=[make_pending_action()]), owned={("usr-2", "mat-1")}
    )
    with pytest.raises(PendingActionNotFoundError):
        await service.read_action(OTHER, "mat-1", "apa-1")
    with pytest.raises(PendingActionNotFoundError):
        await service.confirm_action(OTHER, "mat-1", action_id="apa-1")


@pytest.mark.parametrize(
    "enabled,key,approved",
    [(False, "synthetic", True), (True, "", True), (True, "synthetic", False)],
)
async def test_model_factory_never_transports_when_any_existing_gate_is_closed(
    monkeypatch, enabled, key, approved
):
    from types import SimpleNamespace

    from src import bootstrap
    from src.modules.matter_agent.domain.errors import ModelProviderError

    factory = AsyncMock()
    monkeypatch.setattr(
        "src.modules.matter_agent.infrastructure.gemini_adapter.GeminiAgentAdapter", factory
    )
    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: SimpleNamespace(
            matter_agent_enabled=enabled, gemini_api_key=key, provider_data_approval=approved
        ),
    )
    model = bootstrap.build_agent_model()
    with pytest.raises(ModelProviderError):
        await model.run_turn()
    factory.assert_not_called()


async def test_proposal_ends_turn_so_later_model_failure_cannot_orphan_card():
    from src.modules.matter_agent.domain.errors import ModelProviderError
    from src.modules.matter_agent.ports import ModelTurn, ProposedToolCall, ToolResult
    from src.modules.matter_agent.tests.fakes import RecordingTool

    class ProposeThenFail:
        calls = 0

        async def run_turn(self, **kwargs):
            self.calls += 1
            if self.calls > 1:
                raise ModelProviderError()
            return ModelTurn(tool_calls=(ProposedToolCall("propose_checklist_decision", {}),))

    model = ProposeThenFail()
    tool = RecordingTool(
        "propose_checklist_decision",
        result=ToolResult(
            summary="Synthetic proposal awaiting decision", pending_action_id="synthetic-card"
        ),
    )
    runner, conversation, _, _ = make_runner(model=model, tools={tool.name: tool})
    result = await runner.run(make_request())
    assert model.calls == 1
    assert result.pending_action_ids == ("synthetic-card",)
    assert conversation.messages[0].pending_action_id == "synthetic-card"


@pytest.mark.parametrize("kind", ["extraction", "ocr"])
async def test_document_derivatives_cannot_cross_matter_even_for_same_actor(kind):
    from types import SimpleNamespace

    from src.modules.document.domain.errors import DocumentReviewNotFoundError
    from src.modules.matter_agent.application.read_adapters import DocumentReadAdapter

    review = AsyncMock()
    review.get_review.return_value = SimpleNamespace(matter_id="foreign-matter")
    adapter = DocumentReadAdapter(ingestion=AsyncMock(), review=review)
    with pytest.raises(DocumentReviewNotFoundError):
        if kind == "extraction":
            await adapter.extraction_for_agent(
                user_id="actor", matter_id="current", detected_document_id="foreign-document"
            )
        else:
            await adapter.ocr_pages_for_agent(
                user_id="actor",
                matter_id="current",
                detected_document_id="foreign-document",
                page_no=None,
            )
    review.get_artifact.assert_not_called()


async def test_processing_summary_keeps_latest_failed_run_separate_from_source_state_and_cursor():
    from types import SimpleNamespace

    from src.modules.matter_agent.application.read_adapters import DocumentReadAdapter

    owner = AsyncMock()
    owner.list_source_files.return_value = (
        [
            SimpleNamespace(
                source_file=SimpleNamespace(
                    id="src-synthetic", filename="synthetic.pdf", state="PROCESSED", version=4
                ),
                detected_document_ids=["doc-synthetic"],
                contains_multiple_documents=False,
                duplicate_of_source_file_id=None,
            )
        ],
        "next-page",
    )
    owner.get_processing_status.return_value = SimpleNamespace(
        latest_run=SimpleNamespace(
            id="run-retry", outcome="FAILED", failure_reason="PROVIDER_UNAVAILABLE", succeeded=False
        )
    )
    result = await DocumentReadAdapter(ingestion=owner, review=AsyncMock()).documents_for_agent(
        user_id="actor", matter_id="current", cursor="previous"
    )
    assert result["sourceFiles"][0]["state"] == "PROCESSED"
    assert result["sourceFiles"][0]["latestRun"]["succeeded"] is False
    assert result["nextCursor"] == "next-page"
    owner.list_source_files.assert_awaited_once_with(
        user_id="actor", matter_id="current", limit=50, cursor="previous"
    )


async def test_queued_turn_context_is_bounded_before_its_source_not_after_latest_page():
    from src.modules.matter_agent.domain.models import MessageRole
    from src.modules.matter_agent.ports import ModelTurn

    model = AsyncMock()
    model.run_turn.return_value = ModelTurn(text="Synthetic response")
    runner, conversation, _, _ = make_runner(model=model)
    request = make_request()
    source = await conversation.append(
        session=request.session, role=MessageRole.USER, content="Synthetic queued original"
    )
    for number in range(25):
        await conversation.append(
            session=request.session, role=MessageRole.USER, content=f"Synthetic later {number}"
        )
    await runner.run(replace(request, source_sequence=source.sequence))
    assert [message.id for message in model.run_turn.call_args.kwargs["history"]] == [source.id]


async def test_withheld_model_legal_claim_keeps_actual_prior_tool_count():
    from src.modules.matter_agent.ports import ModelTurn, ProposedToolCall
    from src.modules.matter_agent.tests.fakes import RecordingTool

    tool = RecordingTool("read_matter_summary")
    runner, _, _, _ = make_runner(
        turns=[
            ModelTurn(tool_calls=(ProposedToolCall(tool.name, {}),)),
            ModelTurn(text="Synthetic statute claim without authority"),
        ],
        tools={tool.name: tool},
    )
    result = await runner.run(make_request())
    assert result.failure_class == "legal_research_unavailable"
    assert result.tool_call_count == 1

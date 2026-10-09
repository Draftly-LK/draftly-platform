"""Synthetic corpus/provider seams; no production text or provider requests."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.matter_agent.application.legal_tool import ResearchLegalQuestionTool
from src.modules.matter_agent.tests.test_agent_service import CTX
from src.modules.matter_agent.tests.test_turn_runner import make_request, make_runner
from src.modules.research.application.matter_research import MatterResearchService
from src.modules.research.domain.models import (
    AuthorityKind,
    ComposedClaim,
    RetrievalPassage,
    Scope,
    ScopeType,
    SearchResult,
    SourceScope,
)
from src.platform.errors import NotFoundError
from tests.factories.audit import FakeAudit

PASSAGE = RetrievalPassage(
    "synthetic-corpus",
    "SYN-1",
    "Synthetic source",
    "Synthetic reference",
    "Synthetic supporting passage, not legal guidance.",
    2,
    "synthetic-v1",
)


def setup(*, passages=(PASSAGE,), claims=None, configured=True):
    composer = AsyncMock() if configured else None
    if composer is not None:
        composer.compose.return_value = (
            claims
            if claims is not None
            else (ComposedClaim("Synthetic supported answer.", ("SYN-1",)),)
        )
    research = SimpleNamespace(
        resolve_scope=AsyncMock(return_value=Scope(ScopeType.MATTER, "mat-1", "mat-1")),
        retrieve=AsyncMock(return_value=(SearchResult(list(passages)), ["synthetic-v1"], False)),
        composer=composer,
    )
    billing = AsyncMock()
    billing.reserve_usage.return_value = SimpleNamespace(id="synthetic-reservation")
    audit = FakeAudit()
    return MatterResearchService(research, billing, audit), research, billing, audit


async def test_grounded_turn_persists_exact_supported_text_and_provenance_without_agent_model():
    service, research, billing, audit = setup()
    tool = ResearchLegalQuestionTool(service)
    runner, conversation, model, calls = make_runner(tools={tool.name: tool})
    result = await runner.run(make_request(message="What does the statute require?"))
    assert result.tool_call_count == 1
    assert model.calls == 0
    assert conversation.messages[0].content == "Synthetic supported answer. [1]"
    citation = conversation.messages[0].citations[0]
    assert (
        citation.passage,
        citation.page,
        citation.corpus_version,
        citation.verification_status,
    ) == (PASSAGE.text, 2, "synthetic-v1", "unverified")
    research.resolve_scope.assert_awaited_once_with(
        CTX.__class__(actor_id="usr-1", account_role=CTX.account_role), "matter", "mat-1"
    )
    billing.require_feature_or_raise.assert_awaited_once()
    billing.reserve_usage.assert_awaited_once()
    billing.consume_usage.assert_awaited_once()
    assert "Synthetic supported" not in str(audit.events)
    assert calls.records[0].input_summary == "question,sources"


async def test_foreign_scope_fails_before_metering_and_retrieval():
    service, research, billing, _ = setup()
    research.resolve_scope.side_effect = NotFoundError()
    with pytest.raises(NotFoundError):
        await service.answer(
            CTX, "foreign", question="synthetic", sources=SourceScope.ALL, operation_id="job"
        )
    billing.require_feature_or_raise.assert_not_called()
    research.retrieve.assert_not_called()


async def test_entitlement_refusal_precedes_retrieval():
    service, research, billing, _ = setup()
    billing.require_feature_or_raise.side_effect = NotFoundError()
    with pytest.raises(NotFoundError):
        await service.answer(
            CTX, "mat-1", question="synthetic", sources=SourceScope.ALL, operation_id="job"
        )
    research.retrieve.assert_not_called()
    billing.reserve_usage.assert_not_called()


@pytest.mark.parametrize(
    "claims", [(ComposedClaim("Unsupported synthetic answer", ("MISSING",)),), ()]
)
async def test_uncited_claims_are_not_returned(claims):
    service, _, billing, _ = setup(claims=claims)
    answer = await service.answer(
        CTX, "mat-1", question="synthetic", sources=SourceScope.ALL, operation_id="job"
    )
    assert not answer.claims and not answer.passages
    assert answer.unavailable_reason == "insufficient_authority"
    billing.consume_usage.assert_awaited_once()


async def test_missing_approved_composer_does_not_call_any_provider():
    service, research, billing, _ = setup(configured=False)
    answer = await service.answer(
        CTX, "mat-1", question="synthetic", sources=SourceScope.ALL, operation_id="job"
    )
    assert answer.unavailable_reason == "legal_research_unavailable"
    research.retrieve.assert_not_called()
    billing.reserve_usage.assert_not_called()


async def test_provider_failure_releases_reservation_and_audits_only_identifiers():
    service, research, billing, audit = setup()
    research.composer.compose.side_effect = TimeoutError("synthetic secret")
    answer = await service.answer(
        CTX,
        "mat-1",
        question="synthetic private question",
        sources=SourceScope.ALL,
        operation_id="job",
    )
    assert answer.unavailable_reason == "legal_research_unavailable"
    billing.release_usage.assert_awaited_once()
    billing.consume_usage.assert_not_called()
    assert "synthetic private" not in str(audit.events)
    assert "synthetic secret" not in str(audit.events)


async def test_case_excerpt_remains_unverified_and_is_not_relabelled_statute():
    service, *_ = setup(passages=(replace(PASSAGE, kind=AuthorityKind.CASE, verified=True),))
    tool = ResearchLegalQuestionTool(service)
    runner, conversation, _, _ = make_runner(tools={tool.name: tool})
    await runner.run(make_request(message="What does the statute require?"))
    citation = conversation.messages[0].citations[0]
    assert citation.source_type == "case" and citation.verification_status == "unverified"


async def test_cancelled_research_releases_reserved_usage_and_propagates_cancellation():
    import asyncio

    service, research, billing, _ = setup()
    research.composer.compose.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await service.answer(
            CTX, "mat-1", question="synthetic", sources=SourceScope.ALL, operation_id="job"
        )
    billing.release_usage.assert_awaited_once()
    billing.consume_usage.assert_not_called()

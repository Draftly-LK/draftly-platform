"""End-to-end flow against a real PostgreSQL (Neon), not SQLite.

The path exercised is the whole product loop minus the browser:

    POST message → outbox job → worker runs the turn → tool proposes a card
    → user confirms → the checklist item actually changes in Postgres

SQLite is not sufficient for this: the outbox, the JSON columns, the unique
constraints and the transaction semantics are the things most likely to differ,
and this is the test that would catch it.

Everything is created inside a throwaway schema and dropped afterwards, so the
shared development database is never touched. The test skips rather than fails
when no database is reachable, because a missing Neon branch is an environment
gap, not a defect in the code under test.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_request_context
from src.main import create_app
from src.modules.audit.infrastructure.orm import AuditEventRow
from src.modules.auth.domain.models import Role
from src.modules.auth.infrastructure.orm import UserRow
from src.modules.content_governance.contracts import (
    ApplicabilityStatus,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
)
from src.modules.matter.domain.models import (
    AutomationScope,
    DispositionScope,
    DisputeStage,
    MatterLifecycleStatus,
    MatterState,
    ParcelKind,
    SubtypeDecisionStatus,
    TitleStatus,
)
from src.modules.matter.infrastructure.orm import MatterRow
from src.modules.matter_agent.infrastructure.orm import (
    AgentConversationRow,
    AgentJobRow,
    AgentMessageRow,
    AgentPendingActionRow,
    AgentSessionRow,
    AgentStreamEventRow,
    AgentToolCallRow,
    MatterNoteRow,
)
from src.modules.matter_agent.ports import ModelTurn, ProposedToolCall
from src.modules.task.infrastructure.orm import (
    ChecklistItemRow,
    ChecklistSnapshotRow,
    SatisfactionLinkRow,
)
from src.platform.db.idempotency import IdempotencyKeyRow
from src.platform.db.session import get_db
from src.platform.messaging.orm import OutboxRow
from src.platform.request_context import RequestContext
from tests.db.fixtures import _upgrade_head
from tests.db.postgres import database_url, skip_or_fail

OWNER = "usr-e2e-owner"
MATTER = "mat-e2e-1"
SNAPSHOT = "cls-e2e-1"
ITEM = "cli-e2e-1"
REQUIREMENT = "R_C00_MATTER_AND_CLIENT_REFERENCE"
MODULE = "C00_MATTER_ADMIN"

_TABLES = [
    UserRow.__table__,
    MatterRow.__table__,
    ChecklistSnapshotRow.__table__,
    ChecklistItemRow.__table__,
    # Read when a decision recomputes resolution (live link count).
    SatisfactionLinkRow.__table__,
    AgentSessionRow.__table__,
    AgentMessageRow.__table__,
    AgentJobRow.__table__,
    AgentToolCallRow.__table__,
    AgentPendingActionRow.__table__,
    AgentStreamEventRow.__table__,
    MatterNoteRow.__table__,
    IdempotencyKeyRow.__table__,
    OutboxRow.__table__,
    AuditEventRow.__table__,
]

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _selector_loop() -> None:
    """psycopg's async mode cannot run on the Windows proactor loop."""
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
async def pg_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = database_url()

    schema = f"agent_e2e_{uuid.uuid4().hex[:10]}"
    admin = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except Exception as exc:  # noqa: BLE001 - an unreachable database is a skip
        await admin.dispose()
        skip_or_fail(f"postgres unavailable: {type(exc).__name__}")

    engine = create_async_engine(
        url, connect_args={"options": f"-csearch_path={schema}"}, pool_pre_ping=True
    )
    # Exercise the real migration chain, including conversation segments.
    _upgrade_head(url, schema)

    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        # Neon drops idle connections under load, so teardown retries once.
        # A leaked schema is worth a warning, never a failed test run.
        for attempt in (1, 2):
            try:
                async with admin.connect() as connection:
                    await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                break
            except Exception as exc:  # noqa: BLE001 - cleanup must not fail the run
                if attempt == 2:
                    print(f"WARNING: could not drop schema {schema}: {exc!r}")
        await admin.dispose()


@pytest.fixture
async def seeded(pg_sessions: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(tz=UTC)
    async with pg_sessions() as session:
        session.add(
            UserRow(
                id=OWNER,
                display_name="Synthetic E2E Owner",
                role=Role.APPROVER.value,
                account_status="active",
            )
        )
        session.add(
            MatterRow(
                id=MATTER,
                user_id=OWNER,
                reference="RTA/E2E/001",
                responsible_lawyer_id=OWNER,
                regime_id="rta",
                subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL.value,
                lifecycle_status=MatterLifecycleStatus.ACTIVE.value,
                rta_state=MatterState.INTAKE_DRAFT.value,
                automation_scope=AutomationScope.ASSESSING.value,
                title_status=TitleStatus.UNKNOWN.value,
                parcel_kind=ParcelKind.UNKNOWN.value,
                disposition_scope=DispositionScope.UNKNOWN.value,
                dispute_stage=DisputeStage.NO_INDICIA_FOUND.value,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            ChecklistSnapshotRow(
                id=SNAPSHOT,
                user_id=OWNER,
                matter_id=MATTER,
                compiler_version="test",
                taxonomy_version="test",
                checklist_version="test",
                rule_pack_version="test",
                fingerprint=f"fp-{uuid.uuid4().hex[:8]}",
                created_by=OWNER,
                created_at=now,
            )
        )
        # Postgres enforces the snapshot foreign key, so the parent is flushed
        # before the item. SQLite let this pass; the real database does not.
        await session.flush()
        session.add(
            ChecklistItemRow(
                id=ITEM,
                user_id=OWNER,
                matter_id=MATTER,
                snapshot_id=SNAPSHOT,
                requirement_definition_id=REQUIREMENT,
                module_definition_id=MODULE,
                inclusion_reason="OFFICE_ADDED",
                applicability=ApplicabilityStatus.REQUIRED.value,
                collection=CollectionStatus.RECEIVED.value,
                digital_review=DigitalReviewStatus.UNREVIEWED.value,
                physical_original=PhysicalOriginalStatus.NOT_REQUIRED.value,
                currency=CurrencyStatus.CURRENT.value,
                consistency=ConsistencyStatus.MATCHED.value,
                resolution=ResolutionStatus.OPEN.value,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


def _client(sessions: async_sessionmaker[AsyncSession]) -> AsyncClient:
    app = create_app()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_request_context] = lambda: RequestContext(
        actor_id=OWNER, account_role=Role.APPROVER, correlation_id="corr-e2e"
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _agent_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATTER_AGENT_ENABLED", "true")
    import src.platform.config as config

    config._settings = None


@pytest.fixture
def scripted_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model that proposes the card, then answers.

    Deterministic on purpose: the test is about the pipeline, not the model.
    """
    from src.modules.matter_agent.infrastructure.fake_model import FakeAgentModelAdapter

    turns = [
        ModelTurn(
            tool_calls=(
                ProposedToolCall(
                    name="propose_checklist_decision",
                    arguments={
                        "itemId": ITEM,
                        "expectedVersion": 1,
                        "digitalReview": "LAWYER_CONFIRMED",
                    },
                ),
            )
        ),
        ModelTurn(text="I have suggested marking that item reviewed. Please confirm."),
    ]
    monkeypatch.setattr("src.bootstrap.build_agent_model", lambda: FakeAgentModelAdapter(turns))


async def _drain_turn(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Run the queued turn the way the worker would."""
    from src.modules.matter_agent.jobs import RUN_TURN_JOB_TYPE, run_turn_job

    async with sessions() as session:
        rows = (await session.execute(OutboxRow.__table__.select())).mappings().all()
        payloads = [row["payload"] for row in rows if row["name"] == RUN_TURN_JOB_TYPE]
    for payload in payloads:
        async with sessions() as session:
            await run_turn_job(session, payload)
            await session.commit()


class TestTheCompleteFlow:
    async def test_message_to_worker_to_proposal_to_confirm_updates_postgres(
        self, pg_sessions, seeded, scripted_model
    ) -> None:
        async with _client(pg_sessions) as client:
            sent = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "Has the client reference requirement been reviewed?"},
                headers={"Idempotency-Key": "e2e-1"},
            )
            assert sent.status_code == 202
            job_id = sent.json()["jobId"]

            await _drain_turn(pg_sessions)

            job = await client.get(f"/api/v1/agent-jobs/{job_id}")
            assert job.json()["state"] == "succeeded"
            assert job.json()["toolCallCount"] == 1

            history = await client.get(f"/api/v1/matters/{MATTER}/agent/messages")
            roles = [item["role"] for item in history.json()["items"]]
            assert roles == ["assistant", "user"], "both turns are in Neon"

        # The tool proposed a card and changed nothing yet.
        async with pg_sessions() as session:
            actions = (
                (await session.execute(AgentPendingActionRow.__table__.select())).mappings().all()
            )
            item_before = (
                (
                    await session.execute(
                        ChecklistItemRow.__table__.select().where(ChecklistItemRow.id == ITEM)
                    )
                )
                .mappings()
                .one()
            )
        assert len(actions) == 1
        assert actions[0]["state"] == "proposed"
        assert item_before["digital_review"] == DigitalReviewStatus.UNREVIEWED.value

        action_id = actions[0]["id"]

        async with _client(pg_sessions) as client:
            confirmed = await client.post(
                f"/api/v1/matters/{MATTER}/agent/actions/{action_id}/confirm"
            )
        assert confirmed.status_code == 200
        assert confirmed.json()["state"] == "executed"

        # Only now does the matter change, and it changed in Postgres.
        async with pg_sessions() as session:
            item_after = (
                (
                    await session.execute(
                        ChecklistItemRow.__table__.select().where(ChecklistItemRow.id == ITEM)
                    )
                )
                .mappings()
                .one()
            )
            events = (await session.execute(OutboxRow.__table__.select())).mappings().all()
            audits = (await session.execute(AuditEventRow.__table__.select())).mappings().all()
        assert item_after["digital_review"] == DigitalReviewStatus.LAWYER_CONFIRMED.value
        assert item_after["version"] > item_before["version"]

        names = {row["name"] for row in events}
        assert "agent.message-appended" in names
        assert "agent.tool-executed" in names
        assert "agent.turn-completed" in names
        assert "agent.action-confirmed" in names

        actions_audited = {row["action"] for row in audits}
        assert "agent.tool-executed" in actions_audited
        assert "agent.action-confirmed" in actions_audited

    async def test_no_event_payload_carries_message_content(
        self, pg_sessions, seeded, scripted_model
    ) -> None:
        secret = "Perera holds NIC 199012345678"
        async with _client(pg_sessions) as client:
            await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": secret},
                headers={"Idempotency-Key": "e2e-privacy"},
            )
        await _drain_turn(pg_sessions)

        async with pg_sessions() as session:
            events = (await session.execute(OutboxRow.__table__.select())).mappings().all()
            audits = (await session.execute(AuditEventRow.__table__.select())).mappings().all()
        for row in events:
            assert secret not in str(row["payload"]), row["name"]
        for row in audits:
            assert secret not in str(dict(row)), row["action"]

    async def test_a_stale_card_is_412_and_the_item_is_untouched(
        self, pg_sessions, seeded, scripted_model
    ) -> None:
        async with _client(pg_sessions) as client:
            await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "Review it."},
                headers={"Idempotency-Key": "e2e-stale"},
            )
        await _drain_turn(pg_sessions)

        # Somebody else moves the item after the card was proposed.
        async with pg_sessions() as session:
            await session.execute(
                ChecklistItemRow.__table__.update()
                .where(ChecklistItemRow.id == ITEM)
                .values(version=99)
            )
            actions = (
                (await session.execute(AgentPendingActionRow.__table__.select())).mappings().all()
            )
            await session.commit()

        async with _client(pg_sessions) as client:
            response = await client.post(
                f"/api/v1/matters/{MATTER}/agent/actions/{actions[0]['id']}/confirm"
            )
        assert response.status_code == 412
        assert response.json()["error"]["code"] == "pending_action_stale"

        async with pg_sessions() as session:
            item = (
                (
                    await session.execute(
                        ChecklistItemRow.__table__.select().where(ChecklistItemRow.id == ITEM)
                    )
                )
                .mappings()
                .one()
            )
        assert item["digital_review"] == DigitalReviewStatus.UNREVIEWED.value


async def test_concurrent_first_confirmations_mutate_and_audit_once(
    pg_sessions, seeded, scripted_model
):
    async with _client(pg_sessions) as client:
        await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic review request"},
            headers={"Idempotency-Key": "concurrent-confirm"},
        )
    await _drain_turn(pg_sessions)
    async with _client(pg_sessions) as client:
        page = (await client.get(f"/api/v1/matters/{MATTER}/agent/messages")).json()
        action_id = next(row["pendingActionId"] for row in page["items"] if row["pendingActionId"])
        responses = await asyncio.gather(
            *(
                client.post(f"/api/v1/matters/{MATTER}/agent/actions/{action_id}/confirm")
                for _ in range(2)
            )
        )
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
        card = (await client.get(f"/api/v1/matters/{MATTER}/agent/actions/{action_id}")).json()
        assert card["state"] == "executed" and card["result"]["version"] == 2
    async with pg_sessions() as session:
        assert (
            await session.execute(
                text("SELECT version FROM checklist_items WHERE id=:id"), {"id": ITEM}
            )
        ).scalar_one() == 2
        assert (
            await session.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='agent.action-confirmed' AND target_id=:id"
                ),
                {"id": action_id},
            )
        ).scalar_one() == 1


async def test_simultaneous_identical_send_and_replayed_worker_do_not_duplicate(
    pg_sessions, seeded, scripted_model
):
    async with _client(pg_sessions) as client:
        responses = await asyncio.gather(
            *(
                client.post(
                    f"/api/v1/matters/{MATTER}/agent/messages",
                    json={"content": "Synthetic shared conversation request"},
                    headers={"Idempotency-Key": "same-logical-send"},
                )
                for _ in range(2)
            )
        )
        assert all(r.status_code == 202 for r in responses)
        assert responses[0].json()["jobId"] == responses[1].json()["jobId"]
        latest = await client.get(f"/api/v1/matters/{MATTER}/agent/latest-job")
        assert latest.json()["jobId"] == responses[0].json()["jobId"]
    await _drain_turn(pg_sessions)
    await _drain_turn(pg_sessions)
    async with _client(pg_sessions) as client:
        page = (await client.get(f"/api/v1/matters/{MATTER}/agent/messages")).json()
        assert [m["role"] for m in page["items"]].count("user") == 1
        assert [m["role"] for m in page["items"]].count("assistant") == 1
        await client.post(f"/api/v1/matters/{MATTER}/agent/conversations")
        assert (await client.get(f"/api/v1/matters/{MATTER}/agent/latest-job")).json() is None
        assert (await client.get(f"/api/v1/matters/{MATTER}/agent/messages")).json()["items"] == []


async def test_grounded_research_roundtrip_uses_owner_scope_and_real_metering(
    pg_sessions, seeded, monkeypatch
):
    from unittest.mock import AsyncMock

    from src.api.deps import build_billing_service
    from src.modules.research.application.service import ResearchService
    from src.modules.research.domain.models import ComposedClaim, RetrievalPassage, SearchResult

    retrieval, composer = AsyncMock(), AsyncMock()
    retrieval.search.return_value = SearchResult(
        [
            RetrievalPassage(
                "synthetic",
                "SYNTHETIC-STATUTE",
                "Synthetic corpus fixture",
                "Synthetic reference",
                "Synthetic supporting source passage.",
                1,
                "synthetic-v1",
            )
        ]
    )
    composer.compose.return_value = (
        ComposedClaim("Synthetic supported research claim.", ("SYNTHETIC-STATUTE",)),
    )
    monkeypatch.setattr(
        "src.bootstrap.build_research_service",
        lambda session: ResearchService(session, retrieval, composer),
    )
    async with pg_sessions() as session:
        assert await build_billing_service(session).ensure_trial(OWNER) is not None
        await session.commit()
    async with _client(pg_sessions) as client:
        sent = await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic question: what does the statute require?"},
            headers={"Idempotency-Key": "grounded-synthetic"},
        )
        assert sent.status_code == 202
    await _drain_turn(pg_sessions)
    await _drain_turn(pg_sessions)
    async with _client(pg_sessions) as client:
        page = (await client.get(f"/api/v1/matters/{MATTER}/agent/messages")).json()
        answer = next(m for m in page["items"] if m["role"] == "assistant")
        assert "Synthetic supported research claim. [1]" in answer["content"]
        assert answer["citations"][0]["passage"] == "Synthetic supporting source passage."
        assert answer["citations"][0]["corpusVersion"] == "synthetic-v1"
        assert answer["citations"][0]["verificationStatus"] == "unverified"
    composer.compose.assert_awaited_once()
    assert retrieval.search.await_args.args[1].matter_id == MATTER
    async with pg_sessions() as session:
        usage = (
            await session.execute(
                text(
                    "SELECT state, quantity FROM usage_ledger_entries WHERE user_id=:id AND metric='research_queries.monthly'"
                ),
                {"id": OWNER},
            )
        ).all()
        assert usage == [("consumed", 1)]


async def test_queued_turn_rechecks_suspended_actor_before_any_provider(
    pg_sessions, seeded, monkeypatch
):
    from unittest.mock import Mock

    model_factory = Mock()
    monkeypatch.setattr("src.bootstrap.build_agent_model", model_factory)
    async with _client(pg_sessions) as client:
        await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic queued request"},
            headers={"Idempotency-Key": "suspended-synthetic"},
        )
    async with pg_sessions() as session:
        await session.execute(
            text("UPDATE users SET account_status='suspended' WHERE id=:id"), {"id": OWNER}
        )
        await session.commit()
    await _drain_turn(pg_sessions)
    model_factory.assert_not_called()
    async with pg_sessions() as session:
        assert (
            await session.execute(
                text("SELECT failure_class FROM agent_jobs WHERE matter_id=:id"), {"id": MATTER}
            )
        ).scalar_one() == "access_unavailable"


async def test_read_then_provider_failure_keeps_recovery_refs_on_reload_and_blocks_duplicate_retry(
    pg_sessions, seeded, monkeypatch
):
    from src.modules.matter_agent.domain.errors import ModelProviderError

    class ReadThenFail:
        calls = 0

        async def run_turn(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(tool_calls=(ProposedToolCall("read_matter_summary", {}),))
            raise ModelProviderError()

    model = ReadThenFail()
    monkeypatch.setattr("src.bootstrap.build_agent_model", lambda: model)
    async with _client(pg_sessions) as client:
        sent = await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic matter summary request"},
            headers={"Idempotency-Key": "read-then-fail"},
        )
        job_id = sent.json()["jobId"]
    await _drain_turn(pg_sessions)
    await _drain_turn(pg_sessions)
    async with _client(pg_sessions) as client:
        latest = (await client.get(f"/api/v1/matters/{MATTER}/agent/latest-job")).json()
        assert latest["state"] == "failed" and latest["toolCallCount"] == 1
        page = (await client.get(f"/api/v1/matters/{MATTER}/agent/messages")).json()
        recovery = next(m for m in page["items"] if m["role"] == "assistant")
        assert "Recorded work before it stopped" in recovery["content"]
        assert recovery["citations"][0]["sourceId"] == MATTER
        refused = await client.post(
            f"/api/v1/matters/{MATTER}/agent/jobs/{job_id}/retry",
            headers={"Idempotency-Key": "unsafe-duplicate"},
        )
        assert refused.status_code == 409
    assert model.calls == 2
    async with pg_sessions() as session:
        assert (
            await session.execute(
                text("SELECT count(*) FROM agent_tool_calls WHERE job_id=:id"), {"id": job_id}
            )
        ).scalar_one() == 1


async def test_queued_source_cutoff_is_applied_before_sql_history_limit(pg_sessions, seeded):
    from src.modules.matter_agent.domain.models import MessageRole
    from src.modules.matter_agent.infrastructure.repository import (
        NeonConversationAdapter,
        SqlAgentSessionRepository,
    )

    async with _client(pg_sessions) as client:
        await client.get(f"/api/v1/matters/{MATTER}/agent")
    async with pg_sessions() as session:
        owner_id = (await session.execute(select(AgentSessionRow.user_id))).scalar_one()
        chat = await SqlAgentSessionRepository(session).find(user_id=owner_id, matter_id=MATTER)
        conversation = NeonConversationAdapter(session)
        source = await conversation.append(
            session=chat, role=MessageRole.USER, content="SYNTHETIC queued source"
        )
        for number in range(25):
            await conversation.append(
                session=chat, role=MessageRole.USER, content=f"SYNTHETIC later {number}"
            )
        history = await conversation.recent(
            session_id=chat.id,
            conversation_id=chat.active_conversation_id,
            limit=20,
            through_sequence=source.sequence,
        )
        assert [row.id for row in history] == [source.id]
        await session.commit()


@pytest.mark.parametrize(
    "status,sources,versioned,case_success,consumed",
    [
        (503, "statutes", True, False, False),
        (200, "cases", True, False, False),
        (200, "statutes", True, False, True),
        (503, "all", True, True, True),
        (200, "statutes", False, False, False),
    ],
)
async def test_actual_retrieval_outcomes_meter_once_and_worker_replay_is_inert(
    pg_sessions, seeded, monkeypatch, status, sources, versioned, case_success, consumed
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import httpx

    from src.api.deps import build_billing_service
    from src.modules.matter_agent.infrastructure.fake_model import FakeAgentModelAdapter
    from src.modules.research.application.service import ResearchService
    from src.modules.research.domain.cases import SimilarCase
    from src.modules.research.domain.models import ComposedClaim
    from src.modules.research.infrastructure.retrieval.case_http import HttpCaseSearchAdapter
    from src.modules.research.infrastructure.retrieval.http_adapter import (
        HttpStatuteRetrievalAdapter,
    )

    calls = []

    def transport(request):
        calls.append(request.url.path)
        return httpx.Response(
            status,
            json=[],
            headers={"X-Draftly-Corpus-Version": "statutes-index-v1:" + "a" * 64}
            if versioned
            else {},
        )

    retrieval = HttpStatuteRetrievalAdapter(
        base_url="http://synthetic.invalid", transport=httpx.MockTransport(transport)
    )
    cases = HttpCaseSearchAdapter(
        base_url="http://synthetic.invalid",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )
    if case_success:
        cases = AsyncMock()
        cases.search_cases.return_value = SimpleNamespace(
            corpus_version="synthetic-case-v1",
            items=[
                SimilarCase(
                    None,
                    "commonlii-synthetic",
                    "Synthetic case",
                    "Synthetic reference",
                    "",
                    1,
                    ["lexical"],
                    False,
                    "Synthetic case supporting passage",
                )
            ],
        )
    composer = AsyncMock()
    composer.compose.return_value = (
        ComposedClaim("Synthetic partial supported answer.", ("COMMONLII-SYNTHETIC",)),
    )
    monkeypatch.setattr(
        "src.bootstrap.build_research_service",
        lambda session: ResearchService(session, retrieval, composer, cases),
    )
    model = FakeAgentModelAdapter(
        turns=[
            ModelTurn(
                tool_calls=(
                    ProposedToolCall(
                        name="research_legal_question",
                        arguments={"question": "Synthetic research inquiry", "sources": sources},
                    ),
                )
            )
        ]
    )
    monkeypatch.setattr("src.bootstrap.build_agent_model", lambda: model)
    async with pg_sessions() as session:
        await build_billing_service(session).ensure_trial(OWNER)
        await session.commit()
    async with _client(pg_sessions) as client:
        sent = await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic research inquiry"},
            headers={"Idempotency-Key": "outcome-synthetic"},
        )
        assert sent.status_code == 202
    await _drain_turn(pg_sessions)
    await _drain_turn(pg_sessions)
    async with _client(pg_sessions) as client:
        replay = await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic research inquiry"},
            headers={"Idempotency-Key": "outcome-synthetic"},
        )
        assert replay.json()["jobId"] == sent.json()["jobId"]
        answer = next(
            m
            for m in (await client.get(f"/api/v1/matters/{MATTER}/agent/messages")).json()["items"]
            if m["role"] == "assistant"
        )
        if case_success:
            assert answer["citations"][0]["corpusVersion"] == "synthetic-case-v1"
            assert answer["citations"][0]["passage"] == "Synthetic case supporting passage"
        else:
            assert answer["citations"] == []
    async with pg_sessions() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT state, quantity FROM usage_ledger_entries WHERE user_id=:id AND metric='research_queries.monthly'"
                ),
                {"id": OWNER},
            )
        ).all()
        assert rows == [("consumed" if consumed else "released", 1)]
    assert len(calls) == (0 if sources == "cases" else 1)
    assert composer.compose.await_count == int(case_success)


async def _receipt_state(sessions: async_sessionmaker[AsyncSession]) -> dict:
    """Capture persisted state, including updates as well as inserted effects."""
    async with sessions() as session:
        return {
            row.__tablename__: (await session.execute(row.__table__.select())).mappings().all()
            for row in (
                AgentSessionRow,
                AgentConversationRow,
                AgentJobRow,
                AgentMessageRow,
                AuditEventRow,
                OutboxRow,
                IdempotencyKeyRow,
            )
        }


@pytest.mark.parametrize("session_exists", [False, True], ids=["no-session", "no-active-segment"])
@pytest.mark.parametrize("conversation_id", [None, "mismatched-conversation"])
async def test_send_receipt_without_current_segment_does_not_write(
    pg_sessions, seeded, monkeypatch, session_exists, conversation_id
):
    from unittest.mock import AsyncMock

    from src.platform.db.idempotency import SqlIdempotencyStore

    if session_exists:
        async with pg_sessions() as session:
            session.add(AgentSessionRow(id="asess-inactive", user_id=OWNER, matter_id=MATTER))
            await session.commit()
    before = await _receipt_state(pg_sessions)
    receipt = AsyncMock(return_value=None)
    monkeypatch.setattr(SqlIdempotencyStore, "receipt", receipt)

    async with _client(pg_sessions) as client:
        for _ in range(2):
            result = await client.get(
                f"/api/v1/matters/{MATTER}/agent/send-receipt",
                params={"conversationId": conversation_id} if conversation_id else {},
                headers={"Idempotency-Key": "synthetic-opaque-send-key"},
            )
            assert result.status_code == 200
            assert result.json() is None
    assert await _receipt_state(pg_sessions) == before
    receipt.assert_not_awaited()


@pytest.mark.parametrize("session_exists", [False, True], ids=["no-session", "no-active-segment"])
async def test_accepted_send_job_without_current_segment_does_not_write(
    pg_sessions, seeded, session_exists
):
    from src.bootstrap import build_agent_service
    from src.platform.db.unit_of_work import UnitOfWork

    if session_exists:
        async with pg_sessions() as session:
            session.add(AgentSessionRow(id="asess-inactive", user_id=OWNER, matter_id=MATTER))
            await session.commit()
    before = await _receipt_state(pg_sessions)
    ctx = RequestContext(actor_id=OWNER, account_role=Role.APPROVER)
    async with pg_sessions() as session, UnitOfWork(session):
        service = build_agent_service(session)
        await service.lock(ctx, MATTER)
        assert await service.accepted_send_job(ctx, MATTER, "ajob-unaccepted") is None
    assert await _receipt_state(pg_sessions) == before


async def test_send_receipt_is_exact_current_actor_matter_and_conversation(
    pg_sessions, seeded, monkeypatch
):
    from src.platform.db.idempotency import SqlIdempotencyStore

    lookups = []
    original = SqlIdempotencyStore.receipt

    async def receipt(self, **kwargs):
        lookups.append(kwargs)
        return await original(self, **kwargs)

    monkeypatch.setattr(SqlIdempotencyStore, "receipt", receipt)
    async with _client(pg_sessions) as client:
        sent = await client.post(
            f"/api/v1/matters/{MATTER}/agent/messages",
            json={"content": "Synthetic receipt question"},
            headers={"Idempotency-Key": "exact-send-key"},
        )
        conversation = (await client.get(f"/api/v1/matters/{MATTER}/agent")).json()[
            "activeConversationId"
        ]
        url = f"/api/v1/matters/{MATTER}/agent/send-receipt"
        headers = {"Idempotency-Key": "exact-send-key"}
        accepted = await client.get(url, params={"conversationId": conversation}, headers=headers)
        assert accepted.status_code == 200
        assert accepted.json() == {
            "sendKey": "exact-send-key",
            "matterId": MATTER,
            "conversationId": conversation,
            "jobId": sent.json()["jobId"],
        }
        from datetime import timedelta

        from sqlalchemy import update

        async with pg_sessions() as session:
            await session.execute(
                update(IdempotencyKeyRow)
                .where(IdempotencyKeyRow.idempotency_key == "exact-send-key")
                .values(created_at=datetime.now(UTC) - timedelta(hours=25))
            )
            await session.commit()
        assert (
            await client.get(url, params={"conversationId": conversation}, headers=headers)
        ).json() is None
        async with pg_sessions() as session:
            await session.execute(
                update(IdempotencyKeyRow)
                .where(IdempotencyKeyRow.idempotency_key == "exact-send-key")
                .values(created_at=datetime.now(UTC))
            )
            await session.commit()
        before = len(lookups)
        assert (await client.get(url)).status_code == 400
        assert (await client.get(url, headers=headers)).json() is None
        assert (
            await client.get(
                url, params={"conversationId": "foreign-conversation"}, headers=headers
            )
        ).json() is None
        assert (
            await client.get(
                url.replace(MATTER, "foreign-matter"),
                params={"conversationId": conversation},
                headers=headers,
            )
        ).status_code == 404
        assert len(lookups) == before
        assert (
            await client.get(
                url,
                params={"conversationId": conversation},
                headers={"Idempotency-Key": "unaccepted-key"},
            )
        ).json() is None
        new_conversation = (
            await client.post(f"/api/v1/matters/{MATTER}/agent/conversations")
        ).json()["id"]
        assert (
            await client.get(url, params={"conversationId": new_conversation}, headers=headers)
        ).json() is None
    async with pg_sessions() as session:
        session.add(
            IdempotencyKeyRow(
                id="idem-foreign-actor",
                user_id="foreign-actor",
                route="POST /matters/{matterId}/agent/messages",
                idempotency_key="foreign-actor-key",
                request_hash="synthetic",
                response=sent.json(),
            )
        )
        await session.commit()
    async with _client(pg_sessions) as client:
        assert (
            await client.get(
                url,
                params={"conversationId": new_conversation},
                headers={"Idempotency-Key": "foreign-actor-key"},
            )
        ).json() is None

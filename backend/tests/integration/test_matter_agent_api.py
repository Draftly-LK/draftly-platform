"""Database-backed API tests for the matter agent.

These run the real router, the real service graph and the real SQLAlchemy
repositories against a live SQLite database created from the ORM metadata. They
exercise what unit tests with fakes cannot: sequence allocation under the real
unique constraint, cursor pagination over real rows, transactional idempotency,
and the 404 a foreign matter actually returns through HTTP.

SQLite rather than Postgres because this repository has no Postgres harness.
The subset of tables used here is dialect-neutral — the JSON columns already
carry ``with_variant`` for SQLite — so the queries under test are the same ones
that run in production. Anything genuinely Postgres-specific (``FOR UPDATE SKIP
LOCKED`` in the outbox claim protocol) is out of scope here and covered by the
worker's own tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.deps import get_request_context
from src.main import create_app
from src.modules.audit.infrastructure.orm import AuditEventRow
from src.modules.auth.domain.models import Role
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
from src.platform.db.idempotency import IdempotencyKeyRow
from src.platform.db.session import Base, get_db
from src.platform.messaging.orm import OutboxRow
from src.platform.request_context import RequestContext

OWNER = "usr-owner"
INTRUDER = "usr-intruder"
MATTER = "mat-agent-1"
FOREIGN_MATTER = "mat-someone-else"

#: Only the tables these tests touch. Creating the whole metadata would pull in
#: party's JSONB columns, which SQLite cannot build.
_TABLES = [
    MatterRow.__table__,
    AgentSessionRow.__table__,
    AgentConversationRow.__table__,
    AgentMessageRow.__table__,
    AgentJobRow.__table__,
    AgentToolCallRow.__table__,
    AgentPendingActionRow.__table__,
    AgentStreamEventRow.__table__,
    MatterNoteRow.__table__,
    IdempotencyKeyRow.__table__,
    OutboxRow.__table__,
    # Every mutation writes an audit row in the same transaction, so the audit
    # table is part of the agent's write path rather than an optional extra.
    AuditEventRow.__table__,
]


@pytest.fixture
async def session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=_TABLES)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker
    finally:
        await engine.dispose()


def _matter(matter_id: str, owner: str, reference: str) -> MatterRow:
    """A minimal valid matter row. Enum columns take their initial values."""
    now = datetime.now(tz=UTC)
    return MatterRow(
        id=matter_id,
        user_id=owner,
        reference=reference,
        responsible_lawyer_id=owner,
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


@pytest.fixture
async def seeded(session_maker: async_sessionmaker[AsyncSession]) -> None:
    """Two matters: one owned by OWNER, one owned by somebody else."""
    async with session_maker() as session:
        session.add(_matter(MATTER, OWNER, "RTA/2026/001"))
        session.add(_matter(FOREIGN_MATTER, "usr-other", "RTA/2026/002"))
        await session.commit()


def _client(
    session_maker: async_sessionmaker[AsyncSession], *, actor_id: str = OWNER
) -> AsyncClient:
    """The real app, with the database and identity swapped for the test."""
    app = create_app()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    def override_ctx() -> RequestContext:
        return RequestContext(
            actor_id=actor_id, account_role=Role.APPROVER, correlation_id="corr-test"
        )

    # Only get_db is overridden: the real get_uow depends on it, so the route
    # and its unit of work share one session exactly as they do in production.
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_request_context] = override_ctx
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _enable_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agent is off by default; these tests are about it being on."""
    monkeypatch.setenv("MATTER_AGENT_ENABLED", "true")
    # conftest's autouse fixture clears the cached Settings around each test.
    import src.platform.config as config

    config._settings = None


class TestSessionProvisioning:
    async def test_first_read_creates_the_session_and_persists_it(
        self, session_maker, seeded
    ) -> None:
        async with _client(session_maker) as client:
            first = await client.get(f"/api/v1/matters/{MATTER}/agent")
            second = await client.get(f"/api/v1/matters/{MATTER}/agent")

        assert first.status_code == 200
        assert first.json()["id"] == second.json()["id"], "one session per matter"

        async with session_maker() as session:
            rows = (await session.execute(AgentSessionRow.__table__.select())).all()
        assert len(rows) == 1


class TestTenantIsolation:
    async def test_a_foreign_matter_is_404_not_403(self, session_maker, seeded) -> None:
        async with _client(session_maker) as client:
            response = await client.get(f"/api/v1/matters/{FOREIGN_MATTER}/agent")
        assert response.status_code == 404

    async def test_a_missing_matter_returns_the_same_body(self, session_maker, seeded) -> None:
        """Existence hiding: the two cases must be indistinguishable."""
        async with _client(session_maker) as client:
            foreign = await client.get(f"/api/v1/matters/{FOREIGN_MATTER}/agent")
            absent = await client.get("/api/v1/matters/mat-nope/agent")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json()["error"]["code"] == absent.json()["error"]["code"]

    async def test_another_user_cannot_read_the_owner_transcript(
        self, session_maker, seeded
    ) -> None:
        async with _client(session_maker) as client:
            await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "Confidential instruction."},
                headers={"Idempotency-Key": "k1"},
            )
        async with _client(session_maker, actor_id=INTRUDER) as intruder:
            response = await intruder.get(f"/api/v1/matters/{MATTER}/agent/messages")
        assert response.status_code == 404


class TestSendingMessages:
    async def test_a_message_is_persisted_with_its_job_and_outbox_row(
        self, session_maker, seeded
    ) -> None:
        async with _client(session_maker) as client:
            response = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "Which documents are outstanding?"},
                headers={"Idempotency-Key": "k-send-1"},
            )

        assert response.status_code == 202
        assert response.json()["state"] == "queued"

        async with session_maker() as session:
            messages = (await session.execute(AgentMessageRow.__table__.select())).all()
            jobs = (await session.execute(AgentJobRow.__table__.select())).all()
            outbox = (await session.execute(OutboxRow.__table__.select())).all()

        assert len(messages) == 1
        assert messages[0].content == "Which documents are outstanding?"
        assert messages[0].sequence == 1
        assert len(jobs) == 1
        # The turn job plus the agent.message-appended and session-created events.
        assert any(row.name == "agent.run-turn" for row in outbox)
        assert any(row.name == "agent.message-appended" for row in outbox)

    async def test_no_outbox_payload_carries_message_content(self, session_maker, seeded) -> None:
        secret = "The NIC on the deed is 199012345678"
        async with _client(session_maker) as client:
            await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": secret},
                headers={"Idempotency-Key": "k-privacy"},
            )
        async with session_maker() as session:
            rows = (await session.execute(OutboxRow.__table__.select())).all()
        for row in rows:
            assert secret not in str(row.payload), f"{row.name} leaked message content"

    async def test_the_sequence_is_monotonic_across_messages(self, session_maker, seeded) -> None:
        async with _client(session_maker) as client:
            for index in range(3):
                await client.post(
                    f"/api/v1/matters/{MATTER}/agent/messages",
                    json={"content": f"message {index}"},
                    headers={"Idempotency-Key": f"k-seq-{index}"},
                )
        async with session_maker() as session:
            rows = (
                await session.execute(
                    AgentMessageRow.__table__.select().order_by(AgentMessageRow.sequence)
                )
            ).all()
        assert [row.sequence for row in rows] == [1, 2, 3]

    async def test_a_missing_idempotency_key_is_refused(self, session_maker, seeded) -> None:
        async with _client(session_maker) as client:
            response = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages", json={"content": "hi"}
            )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "idempotency_key_required"

    async def test_a_replayed_key_returns_the_first_job_without_a_second_message(
        self, session_maker, seeded
    ) -> None:
        """Retry must not duplicate the message or start a second turn."""
        async with _client(session_maker) as client:
            first = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "same"},
                headers={"Idempotency-Key": "k-replay"},
            )
            second = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "same"},
                headers={"Idempotency-Key": "k-replay"},
            )

        assert first.json()["jobId"] == second.json()["jobId"]
        async with session_maker() as session:
            messages = (await session.execute(AgentMessageRow.__table__.select())).all()
        assert len(messages) == 1


class TestPagination:
    async def test_the_transcript_pages_newest_first_with_a_stable_cursor(
        self, session_maker, seeded
    ) -> None:
        async with _client(session_maker) as client:
            for index in range(5):
                await client.post(
                    f"/api/v1/matters/{MATTER}/agent/messages",
                    json={"content": f"m{index}"},
                    headers={"Idempotency-Key": f"k-page-{index}"},
                )
            first = await client.get(f"/api/v1/matters/{MATTER}/agent/messages?limit=2")
            body = first.json()
            second = await client.get(
                f"/api/v1/matters/{MATTER}/agent/messages?limit=2"
                f"&cursor={body['page']['nextCursor']}"
            )

        assert [item["sequence"] for item in body["items"]] == [5, 4]
        assert body["page"]["hasMore"] is True
        assert [item["sequence"] for item in second.json()["items"]] == [3, 2]

    async def test_a_limit_above_the_cap_is_refused(self, session_maker, seeded) -> None:
        async with _client(session_maker) as client:
            response = await client.get(f"/api/v1/matters/{MATTER}/agent/messages?limit=500")
        assert response.status_code == 422


class TestJobsAndStreaming:
    @pytest.mark.parametrize("reason", ["tools", "archived", "newer_message", "timeout"])
    async def test_retry_does_not_repeat_tools_or_answer_stale_messages(
        self, session_maker, seeded, reason
    ) -> None:
        async with _client(session_maker) as client:
            sent = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "hello"},
                headers={"Idempotency-Key": "original"},
            )
            job_id = sent.json()["jobId"]
            async with session_maker() as db:
                job = await db.get(AgentJobRow, job_id)
                job.state = "failed"
                job.failure_class = "model_unavailable"
                if reason == "timeout":
                    job.failure_class = "turn_timeout"
                if reason == "tools":
                    db.add(
                        AgentToolCallRow(
                            id="tool-record",
                            session_id=job.session_id,
                            job_id=job.id,
                            user_id=OWNER,
                            matter_id=MATTER,
                            actor_id=OWNER,
                            tool="create_working_note",
                            outcome="executed",
                        )
                    )
                await db.commit()
            if reason == "archived":
                await client.post(f"/api/v1/matters/{MATTER}/agent/conversations")
            elif reason == "newer_message":
                await client.post(
                    f"/api/v1/matters/{MATTER}/agent/messages",
                    json={"content": "new question"},
                    headers={"Idempotency-Key": "newer"},
                )
            response = await client.post(
                f"/api/v1/matters/{MATTER}/agent/jobs/{job_id}/retry",
                headers={"Idempotency-Key": "retry"},
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "agent_retry_unavailable"

    async def test_retry_queues_a_new_job_for_the_saved_message(
        self, session_maker, seeded
    ) -> None:
        async with _client(session_maker) as client:
            sent = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "hello"},
                headers={"Idempotency-Key": "original"},
            )
            original_id = sent.json()["jobId"]
            async with session_maker() as db:
                original = await db.get(AgentJobRow, original_id)
                original.state = "failed"
                original.failure_class = "model_unavailable"
                # Recovery of jobs created before the migration.
                original.source_message_id = None
                await db.commit()
            url = f"/api/v1/matters/{MATTER}/agent/jobs/{original_id}/retry"
            retried = await client.post(url, headers={"Idempotency-Key": "retry-1"})
            assert retried.status_code == 202
            assert retried.json()["jobId"] != original_id
            # Network retries and a double click with another key converge.
            replayed = await client.post(url, headers={"Idempotency-Key": "retry-1"})
            doubled = await client.post(url, headers={"Idempotency-Key": "retry-2"})
            assert replayed.json()["jobId"] == doubled.json()["jobId"] == retried.json()["jobId"]
        async with session_maker() as db:
            messages = (await db.execute(AgentMessageRow.__table__.select())).all()
            jobs = (await db.execute(AgentJobRow.__table__.select())).all()
            outbox = (await db.execute(OutboxRow.__table__.select())).all()
            audit = (await db.execute(AuditEventRow.__table__.select())).all()
        assert len(messages) == 1
        assert messages[0].content == "hello"
        assert len(jobs) == 2
        assert any(j.id == original_id and j.state == "failed" for j in jobs)
        turn_jobs = [r for r in outbox if r.name == "agent.run-turn"]
        assert len(turn_jobs) == 2
        assert {r.payload["messageId"] for r in turn_jobs} == {messages[0].id}
        assert sum(r.action == "agent.turn-retried" for r in audit) == 1

        async with session_maker() as db:
            retry = await db.get(AgentJobRow, retried.json()["jobId"])
            retry.state = "failed"
            retry.failure_class = "model_unavailable"
            await db.commit()
        async with _client(session_maker) as client:
            again = await client.post(
                f"/api/v1/matters/{MATTER}/agent/jobs/{retry.id}/retry",
                headers={"Idempotency-Key": "retry-child"},
            )
        assert again.status_code == 202
        async with session_maker() as db:
            assert len((await db.execute(AgentMessageRow.__table__.select())).all()) == 1

    @pytest.mark.parametrize("state", ["queued", "running", "succeeded"])
    async def test_retry_refuses_unfinished_or_successful_jobs(
        self, session_maker, seeded, state
    ) -> None:
        async with _client(session_maker) as client:
            sent = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "hello"},
                headers={"Idempotency-Key": "original"},
            )
            job_id = sent.json()["jobId"]
            async with session_maker() as db:
                job = await db.get(AgentJobRow, job_id)
                job.state = state
                await db.commit()
            result = await client.post(
                f"/api/v1/matters/{MATTER}/agent/jobs/{job_id}/retry",
                headers={"Idempotency-Key": "retry"},
            )
        assert result.status_code == 409

    async def test_foreign_retry_is_indistinguishable_from_absent(
        self, session_maker, seeded
    ) -> None:
        async with _client(session_maker) as client:
            sent = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "hello"},
                headers={"Idempotency-Key": "original"},
            )
        async with _client(session_maker, actor_id=INTRUDER) as client:
            foreign = await client.post(
                f"/api/v1/matters/{MATTER}/agent/jobs/{sent.json()['jobId']}/retry",
                headers={"Idempotency-Key": "retry"},
            )
            missing = await client.post(
                f"/api/v1/matters/{MATTER}/agent/jobs/absent/retry",
                headers={"Idempotency-Key": "retry"},
            )
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["error"]["code"] == missing.json()["error"]["code"]

    async def test_a_job_belonging_to_another_user_is_404(self, session_maker, seeded) -> None:
        async with _client(session_maker) as client:
            created = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "hello"},
                headers={"Idempotency-Key": "k-job"},
            )
            job_id = created.json()["jobId"]
        async with _client(session_maker, actor_id=INTRUDER) as intruder:
            response = await intruder.get(f"/api/v1/agent-jobs/{job_id}")
        assert response.status_code == 404

    async def test_the_event_stream_ends_with_the_job_state(self, session_maker, seeded) -> None:
        async with _client(session_maker) as client:
            created = await client.post(
                f"/api/v1/matters/{MATTER}/agent/messages",
                json={"content": "hello"},
                headers={"Idempotency-Key": "k-sse"},
            )
            job_id = created.json()["jobId"]
            response = await client.get(f"/api/v1/agent-jobs/{job_id}/events")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: job-state" in response.text
        assert job_id in response.text


class TestTheKillSwitch:
    async def test_every_route_refuses_while_the_agent_is_disabled(
        self, session_maker, seeded, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MATTER_AGENT_ENABLED", "false")
        import src.platform.config as config

        config._settings = None

        async with _client(session_maker) as client:
            response = await client.get(f"/api/v1/matters/{MATTER}/agent")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "matter_agent_disabled"

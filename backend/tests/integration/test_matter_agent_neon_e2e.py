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
from sqlalchemy import text
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
from src.platform.db.session import Base, get_db
from src.platform.messaging.orm import OutboxRow
from src.platform.request_context import RequestContext
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
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=_TABLES)

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
        session.add(UserRow(id=OWNER, display_name="E2E Owner", role=Role.APPROVER.value))
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
        assert confirmed.json()["state"] == "confirmed"

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

"""Session provisioning, existence hiding, and the confirmation gates."""

from __future__ import annotations

import pytest

from src.modules.auth.domain.models import Role
from src.modules.matter_agent.application.agent_service import AgentService, AgentSettings
from src.modules.matter_agent.domain.errors import (
    AgentDisabledError,
    AgentSessionNotFoundError,
    PendingActionExpiredError,
    PendingActionNotFoundError,
    PendingActionStaleError,
)
from src.modules.matter_agent.domain.models import MessageRole, PendingActionState
from src.modules.matter_agent.tests.fakes import (
    FakeConversation,
    FakeJobs,
    FakeMatterAccess,
    FakePendingActions,
    FakeSessionRepo,
    FakeTargets,
    make_pending_action,
)
from src.platform.request_context import RequestContext
from tests.factories.audit import FakeAudit

CTX = RequestContext(actor_id="usr-1", account_role=Role.APPROVER, correlation_id="corr-1")
OTHER = RequestContext(actor_id="usr-2", account_role=Role.APPROVER)


def build(
    *,
    enabled: bool = True,
    owned: set[tuple[str, str]] | None = None,
    actions: FakePendingActions | None = None,
    versions: dict[str, int] | None = None,
):
    sessions = FakeSessionRepo()
    conversation = FakeConversation()
    audit = FakeAudit()
    jobs = FakeJobs()
    pending = actions or FakePendingActions()
    service = AgentService(
        sessions=sessions,
        conversation=conversation,
        matters=FakeMatterAccess(owned=owned if owned is not None else {("usr-1", "mat-1")}),
        audit=audit,
        settings=AgentSettings(enabled=enabled),
        jobs=jobs,
        actions=pending,
        targets=FakeTargets(versions=versions or {"matter:mat-1": 3}),
    )
    return service, sessions, conversation, audit, jobs, pending


class TestSessionProvisioning:
    async def test_the_session_is_created_lazily_on_first_read(self) -> None:
        service, sessions, *_ = build()
        session = await service.get_or_create_session(CTX, "mat-1")

        assert session.matter_id == "mat-1"
        assert sessions.create_calls == 1

    async def test_repeated_reads_return_the_same_session(self) -> None:
        """One session per (user, matter). There is never a second."""
        service, sessions, *_ = build()
        first = await service.get_or_create_session(CTX, "mat-1")
        second = await service.get_or_create_session(CTX, "mat-1")

        assert first.id == second.id
        assert sessions.create_calls == 1

    async def test_creation_is_audited(self) -> None:
        service, _, _, audit, _, _ = build()
        await service.get_or_create_session(CTX, "mat-1")
        assert "agent.session-created" in audit.actions()


class TestExistenceHiding:
    async def test_a_matter_the_caller_does_not_own_is_absent_not_forbidden(self) -> None:
        service, *_ = build()
        with pytest.raises(AgentSessionNotFoundError) as excinfo:
            await service.get_or_create_session(OTHER, "mat-1")
        assert excinfo.value.http_status == 404

    async def test_a_matter_that_does_not_exist_raises_the_same_error(self) -> None:
        """The two cases must be indistinguishable to the caller."""
        service, *_ = build()
        with pytest.raises(AgentSessionNotFoundError) as absent:
            await service.get_or_create_session(CTX, "mat-does-not-exist")
        with pytest.raises(AgentSessionNotFoundError) as foreign:
            await service.get_or_create_session(OTHER, "mat-1")

        assert absent.value.code == foreign.value.code
        assert str(absent.value) == str(foreign.value)

    async def test_no_session_is_created_for_a_foreign_matter(self) -> None:
        service, sessions, *_ = build()
        with pytest.raises(AgentSessionNotFoundError):
            await service.get_or_create_session(OTHER, "mat-1")
        assert sessions.create_calls == 0

    async def test_a_job_owned_by_another_user_is_a_404(self) -> None:
        service, *_ = build()
        with pytest.raises(AgentSessionNotFoundError):
            await service.read_job(CTX, "ajob-nope")


class TestTheKillSwitch:
    async def test_every_route_refuses_while_the_agent_is_disabled(self) -> None:
        """A partial rollout cannot be reached by guessing a URL."""
        service, *_ = build(enabled=False)
        with pytest.raises(AgentDisabledError):
            await service.get_or_create_session(CTX, "mat-1")


class TestStartingATurn:
    async def test_the_message_is_appended_and_the_turn_is_queued(self) -> None:
        service, _, conversation, _, jobs, _ = build()
        job = await service.start_turn(CTX, "mat-1", content="Hello")

        assert conversation.messages[0].role is MessageRole.USER
        assert conversation.messages[0].content == "Hello"
        assert jobs.enqueued[0]["jobId"] == job.job_id

    async def test_the_queued_payload_carries_identifiers_and_no_content(self) -> None:
        """A job payload may never contain matter content (events.md §2)."""
        service, _, _, _, jobs, _ = build()
        secret = "The NIC is 199012345678"
        await service.start_turn(CTX, "mat-1", content=secret)

        payload = jobs.enqueued[0]
        assert secret not in str(payload)
        assert set(payload) == {"jobId", "sessionId", "messageId", "userId"}


class TestConfirmation:
    async def test_a_stale_target_is_412_and_must_be_regenerated(self) -> None:
        actions = FakePendingActions(seed=[make_pending_action(target_version=2)])
        service, *_ = build(actions=actions, versions={"checklist-item:cli-1": 7})

        with pytest.raises(PendingActionStaleError) as excinfo:
            await service.confirm_action(CTX, "mat-1", action_id="apa-1")
        assert excinfo.value.http_status == 412

    async def test_a_matching_version_confirms(self) -> None:
        actions = FakePendingActions(seed=[make_pending_action(target_version=3)])
        service, *_ = build(actions=actions, versions={"checklist-item:cli-1": 3})

        confirmed = await service.confirm_action(CTX, "mat-1", action_id="apa-1")
        assert confirmed.state is PendingActionState.CONFIRMED
        assert confirmed.confirmed_by == "usr-1"

    async def test_confirming_twice_is_safe(self) -> None:
        actions = FakePendingActions(seed=[make_pending_action(target_version=3)])
        service, *_ = build(actions=actions, versions={"checklist-item:cli-1": 3})

        first = await service.confirm_action(CTX, "mat-1", action_id="apa-1")
        second = await service.confirm_action(CTX, "mat-1", action_id="apa-1")
        assert first.confirmed_at == second.confirmed_at

    async def test_an_expired_card_cannot_be_confirmed(self) -> None:
        actions = FakePendingActions(seed=[make_pending_action(expired=True)])
        service, *_ = build(actions=actions)

        with pytest.raises(PendingActionExpiredError):
            await service.confirm_action(CTX, "mat-1", action_id="apa-1")

    async def test_an_unresolvable_target_fails_closed_as_stale(self) -> None:
        """An unrecognised target never confirms against nothing."""
        actions = FakePendingActions(seed=[make_pending_action(target_ref="mystery:x")])
        service, *_ = build(actions=actions, versions={})

        with pytest.raises(PendingActionStaleError):
            await service.confirm_action(CTX, "mat-1", action_id="apa-1")

    async def test_a_card_on_another_matter_is_not_found(self) -> None:
        actions = FakePendingActions(seed=[make_pending_action(matter_id="mat-9")])
        service, *_ = build(actions=actions, owned={("usr-1", "mat-1"), ("usr-1", "mat-9")})

        with pytest.raises(PendingActionNotFoundError):
            await service.confirm_action(CTX, "mat-1", action_id="apa-1")


class TestRejection:
    async def test_a_rejected_proposal_is_preserved_and_audited(self) -> None:
        actions = FakePendingActions(seed=[make_pending_action()])
        service, _, _, audit, _, pending = build(actions=actions)

        rejected = await service.reject_action(CTX, "mat-1", action_id="apa-1", reason="wrong")

        assert rejected.state is PendingActionState.REJECTED
        assert pending.rows["apa-1"].state is PendingActionState.REJECTED
        assert "agent.action-rejected" in audit.actions()

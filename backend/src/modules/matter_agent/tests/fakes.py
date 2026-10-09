"""In-memory doubles for the agent's ports.

Deliberately faithful on the two things the tests are about: sequence
allocation is monotonic and unique, and every recorded tool call is kept.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from src.modules.matter_agent.application.actions import CHECKLIST_DECISION
from src.modules.matter_agent.application.agent_service import AgentJob
from src.modules.matter_agent.domain.models import (
    AgentCitation,
    AgentConversation,
    AgentMessage,
    AgentSession,
    JobState,
    MessageRole,
    PendingAction,
    SessionState,
    ToolCallRecord,
)
from src.modules.matter_agent.ports import (
    MemoryHit,
    MessagePage,
    ToolDeclaration,
    ToolInvocation,
    ToolResult,
)
from src.platform import ids
from src.platform.pagination import Cursor


class FakeSessionRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], AgentSession] = {}
        self.conversations: dict[str, list[AgentConversation]] = {}
        self.create_calls = 0

    async def find(self, *, user_id: str, matter_id: str) -> AgentSession | None:
        return self.rows.get((user_id, matter_id))

    async def create(self, session: AgentSession) -> AgentSession:
        self.create_calls += 1
        key = (session.user_id, session.matter_id)
        if key in self.rows:
            # Mirrors the unique constraint: the first writer wins.
            return self.rows[key]
        self.rows[key] = session
        return await self.start_conversation(session)

    async def start_conversation(self, session: AgentSession) -> AgentSession:
        now = datetime.now(tz=UTC)
        rows = self.conversations.setdefault(session.id, [])
        if rows:
            rows[-1] = replace(rows[-1], state=SessionState.CLOSED, updated_at=now)
        conversation = AgentConversation(
            id=ids.new_id(ids.AGENT_CONVERSATION),
            session_id=session.id,
            user_id=session.user_id,
            matter_id=session.matter_id,
            state=SessionState.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        rows.append(conversation)
        updated = replace(
            session,
            active_conversation_id=conversation.id,
            updated_at=now,
        )
        self.rows[(session.user_id, session.matter_id)] = updated
        return updated

    async def list_conversations(self, session: AgentSession) -> tuple[AgentConversation, ...]:
        return tuple(reversed(self.conversations.get(session.id, [])))


class FakeConversation:
    def __init__(self) -> None:
        self.messages: list[AgentMessage] = []

    async def append(
        self,
        *,
        session: AgentSession,
        role: MessageRole,
        content: str,
        job_id: str | None = None,
        tool_call_id: str | None = None,
        pending_action_id: str | None = None,
        citations: tuple[AgentCitation, ...] = (),
    ) -> AgentMessage:
        message = AgentMessage(
            id=ids.new_id(ids.AGENT_MESSAGE),
            session_id=session.id,
            matter_id=session.matter_id,
            user_id=session.user_id,
            sequence=len(self.messages) + 1,
            role=role,
            content=content,
            created_at=datetime.now(tz=UTC),
            job_id=job_id,
            tool_call_id=tool_call_id,
            pending_action_id=pending_action_id,
            conversation_id=session.active_conversation_id,
            citations=citations,
        )
        self.messages.append(message)
        return message

    async def page(
        self,
        *,
        session_id: str,
        limit: int,
        cursor: Cursor | None = None,
        conversation_id: str | None = None,
    ) -> MessagePage:
        rows = [m for m in reversed(self.messages) if m.session_id == session_id]
        if conversation_id is not None:
            rows = [m for m in rows if m.conversation_id == conversation_id]
        if cursor is not None:
            rows = [m for m in rows if m.sequence < int(cursor.id)]
        page = rows[:limit]
        has_more = len(rows) > limit
        return MessagePage(
            items=tuple(page),
            next_cursor=(
                Cursor(created_at=page[-1].created_at, id=str(page[-1].sequence))
                if has_more and page
                else None
            ),
            has_more=has_more,
        )

    async def recent(
        self,
        *,
        session_id: str,
        limit: int,
        conversation_id: str | None = None,
        through_sequence: int | None = None,
    ) -> tuple[AgentMessage, ...]:
        rows = [m for m in self.messages if m.session_id == session_id]
        if conversation_id is not None:
            rows = [m for m in rows if m.conversation_id == conversation_id]
        if through_sequence is not None:
            rows = [m for m in rows if m.sequence <= through_sequence]
        return tuple(rows[-limit:])


class FakeMatterAccess:
    def __init__(self, *, owned: set[tuple[str, str]] | None = None) -> None:
        self.owned = owned or set()

    async def owns_matter(self, *, user_id: str, matter_id: str) -> bool:
        return (user_id, matter_id) in self.owned


class FakeToolCallRepo:
    def __init__(self) -> None:
        self.records: list[ToolCallRecord] = []

    async def record(self, call: ToolCallRecord) -> None:
        self.records.append(call)


class FakeMemory:
    """Optional memory. ``fail`` makes every call raise, like a dead provider."""

    def __init__(self, *, hits: tuple[str, ...] = (), ready: bool = True, fail: bool = False):
        self._hits = hits
        self._ready = ready
        self._fail = fail
        self.retrieve_calls = 0

    async def retrieve(self, *, matter_id: str, probe: str, limit: int) -> tuple[MemoryHit, ...]:
        self.retrieve_calls += 1
        if self._fail:
            raise TimeoutError("provider unreachable")
        return tuple(
            MemoryHit(text=text, resource_id=f"res-{i}", resource_version=1)
            for i, text in enumerate(self._hits[:limit])
        )

    async def ingest(self, *, matter_id: str, resource_id: str, resource_version: int) -> None:
        if self._fail:
            raise TimeoutError("provider unreachable")

    async def is_ready(self, *, matter_id: str) -> bool:
        if self._fail:
            raise TimeoutError("provider unreachable")
        return self._ready


class FakeJobs:
    def __init__(self) -> None:
        self.jobs: dict[str, AgentJob] = {}
        self.enqueued: list[dict[str, str]] = []

    async def create(
        self, *, session_id: str, user_id: str, matter_id: str, correlation_id: str
    ) -> AgentJob:
        job = AgentJob(job_id=ids.new_id(ids.AGENT_JOB), state=JobState.QUEUED)
        self.jobs[job.job_id] = job
        return job

    async def enqueue(self, *, job_id: str, session_id: str, message_id: str, user_id: str) -> None:
        self.enqueued.append(
            {
                "jobId": job_id,
                "sessionId": session_id,
                "messageId": message_id,
                "userId": user_id,
            }
        )

    async def get(self, *, job_id: str, user_id: str) -> AgentJob | None:
        return self.jobs.get(job_id)


class FakePendingActions:
    @asynccontextmanager
    async def execution(self):
        yield

    def __init__(self, *, seed: list[PendingAction] | None = None) -> None:
        self.rows = {action.id: action for action in (seed or [])}

    async def get(self, *, action_id: str, matter_id: str) -> PendingAction | None:
        action = self.rows.get(action_id)
        return action if action and action.matter_id == matter_id else None

    async def create(self, action: PendingAction) -> PendingAction:
        self.rows[action.id] = action
        return action

    async def update(self, action: PendingAction) -> PendingAction:
        self.rows[action.id] = action
        return action


class FakeTargets:
    def __init__(self, *, versions: dict[str, int] | None = None) -> None:
        self.versions = versions or {}

    async def current_version(self, *, matter_id: str, target_ref: str) -> int:
        return self.versions.get(target_ref, -1)


class RecordingTool:
    """A tool that records what it was given and returns a fixed result."""

    def __init__(
        self, name: str, *, result: ToolResult | None = None, parameters: dict | None = None
    ) -> None:
        self.name = name
        self.invocations: list[ToolInvocation] = []
        self._result = result or ToolResult(summary="done")
        self._parameters = parameters or {}

    def declaration(self) -> ToolDeclaration:
        return ToolDeclaration(name=self.name, description="", parameters=self._parameters)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.invocations.append(invocation)
        return self._result


def make_session(*, user_id: str = "usr-1", matter_id: str = "mat-1") -> AgentSession:
    now = datetime.now(tz=UTC)
    return AgentSession(
        id="asess-1",
        user_id=user_id,
        matter_id=matter_id,
        model_version="fake-1",
        prompt_version="v1",
        state=SessionState.ACTIVE,
        created_at=now,
        updated_at=now,
    )


def make_pending_action(
    *,
    action_id: str = "apa-1",
    matter_id: str = "mat-1",
    target_ref: str = "checklist-item:cli-1",
    target_version: int = 3,
    expired: bool = False,
) -> PendingAction:
    now = datetime.now(tz=UTC)
    return PendingAction(
        id=action_id,
        session_id="asess-1",
        matter_id=matter_id,
        user_id="usr-1",
        action_kind=CHECKLIST_DECISION,
        arguments={"itemId": "cli-1", "digitalReview": "REVIEWED_OK"},
        target_ref=target_ref,
        target_version=target_version,
        expires_at=now - timedelta(minutes=1) if expired else now + timedelta(hours=1),
        created_at=now,
    )

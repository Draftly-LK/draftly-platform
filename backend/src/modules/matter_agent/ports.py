"""Ports for the matter master agent.

Dependency direction (`CLAUDE.md`): the application service uses these; only
infrastructure implements them. Nothing here imports SQLAlchemy, FastAPI, or a
provider SDK.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.modules.matter_agent.domain.models import (
    AgentMessage,
    AgentSession,
    MessageRole,
    PendingAction,
    ToolCallRecord,
)
from src.platform.pagination import Cursor

# ── Model provider ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolDeclaration:
    """One function declaration offered to the model for a single turn."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ProposedToolCall:
    """A model proposal. Draftly validates and executes it, never the model."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """One stateless tool-calling turn's output."""

    text: str = ""
    tool_calls: tuple[ProposedToolCall, ...] = ()
    model_version: str = ""


class AgentModelPort(Protocol):
    """Run one stateless tool-calling turn.

    Stateless on purpose: no provider-side conversation store. History is
    supplied from Neon on every call.
    """

    async def run_turn(
        self,
        *,
        system_prompt: str,
        history: Sequence[AgentMessage],
        memory_context: Sequence[str],
        tools: Sequence[ToolDeclaration],
    ) -> ModelTurn: ...


# ── Conversation ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MessagePage:
    items: tuple[AgentMessage, ...]
    next_cursor: Cursor | None
    has_more: bool


class ConversationPort(Protocol):
    """Append and retrieve ordered chat messages. Backed by Neon, always.

    There is exactly one implementation and it is Neon-backed. No provider ever
    serves visible chat history (`matter-agent-service.md` invariant 5).
    """

    async def append(
        self,
        *,
        session: AgentSession,
        role: MessageRole,
        content: str,
        job_id: str | None = None,
        tool_call_id: str | None = None,
        pending_action_id: str | None = None,
    ) -> AgentMessage:
        """Append at the next sequence. Commits with its outbox event."""
        ...

    async def page(
        self,
        *,
        session_id: str,
        limit: int,
        cursor: Cursor | None = None,
    ) -> MessagePage: ...

    async def recent(self, *, session_id: str, limit: int) -> tuple[AgentMessage, ...]:
        """The newest `limit` messages, oldest first, for the model turn."""
        ...


# ── Memory (optional) ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MemoryHit:
    """One remembered item with the pointer that makes it traceable."""

    text: str
    resource_id: str
    resource_version: int
    kind: str = ""


class MemoryPort(Protocol):
    """Semantic memory, owned and implemented by `memory_service`.

    Optional in every direction: a null implementation is a supported
    deployment, and every caller tolerates an empty result. Failure here
    degrades recall and never blocks chat, history, or tools.
    """

    async def retrieve(
        self, *, matter_id: str, probe: str, limit: int
    ) -> tuple[MemoryHit, ...]: ...

    async def ingest(self, *, matter_id: str, resource_id: str, resource_version: int) -> None: ...

    async def is_ready(self, *, matter_id: str) -> bool: ...


class NullMemoryPort:
    """The memory implementation used when Supermemory is disabled.

    Not a test double — this is the default deployment. `SUPERMEMORY_ENABLED`
    is off unless a signed DPA and provider approval say otherwise.
    """

    async def retrieve(self, *, matter_id: str, probe: str, limit: int) -> tuple[MemoryHit, ...]:
        return ()

    async def ingest(self, *, matter_id: str, resource_id: str, resource_version: int) -> None:
        return None

    async def is_ready(self, *, matter_id: str) -> bool:
        return False


# ── Tools ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolInvocation:
    """A validated call, after the allowlist and capability gates passed."""

    tool_name: str
    arguments: dict[str, Any]
    matter_id: str
    actor_id: str


@dataclass(frozen=True)
class ToolResult:
    """What a tool returns to the loop.

    `summary` is safe for memory and for the transcript. `payload` may contain
    matter content and is sent to the model transiently only.
    """

    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    resource_refs: tuple[str, ...] = ()
    pending_action_id: str | None = None


class AgentToolPort(Protocol):
    """Common typed contract for every allowlisted internal tool."""

    name: str

    def declaration(self) -> ToolDeclaration: ...

    async def execute(self, invocation: ToolInvocation) -> ToolResult: ...


class AgentEventPort(Protocol):
    """Publishes a registered ``agent.*`` event into the outbox.

    Transactional with the mutation it describes; never fire-and-forget.
    """

    async def publish(
        self,
        event_name: str,
        *,
        user_id: str,
        matter_id: str | None,
        actor_id: str | None,
        correlation_id: str,
        idempotency_key: str,
        data: dict[str, Any],
    ) -> bool: ...


# ── Persistence ──────────────────────────────────────────────────────────────


class AgentSessionRepository(Protocol):
    async def find(self, *, user_id: str, matter_id: str) -> AgentSession | None: ...

    async def create(self, session: AgentSession) -> AgentSession:
        """Provision lazily. Unique on (user_id, matter_id) under concurrency."""
        ...


class ToolCallRepository(Protocol):
    async def record(self, call: ToolCallRecord) -> None: ...


class PendingActionRepository(Protocol):
    async def get(self, *, action_id: str, matter_id: str) -> PendingAction | None: ...

    async def create(self, action: PendingAction) -> PendingAction: ...

    async def update(self, action: PendingAction) -> PendingAction: ...

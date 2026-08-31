"""Domain models for the matter master agent.

Neon is authoritative for the transcript (`matter-agent-service.md` §Summary),
so `AgentMessage` carries its content and is the record, not an index into a
provider. Nothing here imports SQLAlchemy, FastAPI, or a provider SDK.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class SessionState(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class JobState(StrEnum):
    """States from `api-conventions.md` §6, including dead_letter."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class ToolCallOutcome(StrEnum):
    EXECUTED = "executed"
    DENIED = "denied"
    FAILED = "failed"


class PendingActionState(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SuggestionOrigin(StrEnum):
    """Provenance label stored on every agent-created record.

    A stored column, not a rendering convention
    (`matter-agent-service.md` §Document processing follow-through).
    """

    HUMAN = "human"
    AI_SUGGESTED = "ai_suggested"


def content_hash(content: str) -> str:
    """Stable hash of message content, used to detect drift against a copy."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AgentSession:
    """One durable chat session per (user_id, matter_id)."""

    id: str
    user_id: str
    matter_id: str
    model_version: str
    prompt_version: str
    created_at: datetime
    updated_at: datetime
    state: SessionState = SessionState.ACTIVE


@dataclass(frozen=True)
class AgentMessage:
    """An authoritative transcript row. Unique on (session_id, sequence)."""

    id: str
    session_id: str
    matter_id: str
    user_id: str
    sequence: int
    role: MessageRole
    content: str
    created_at: datetime
    content_hash: str = ""
    job_id: str | None = None
    tool_call_id: str | None = None
    pending_action_id: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence starts at 1")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self.content))

    def hash_matches(self) -> bool:
        """True when the stored hash still describes the stored content."""
        return self.content_hash == content_hash(self.content)


@dataclass(frozen=True)
class ToolCallRecord:
    """One attempted tool call, executed or refused.

    A denial is recorded as deliberately as an execution: it is what a prompt
    injection looks like from the outside
    (`matter-agent-service.md` §Audit of tool calls).
    """

    id: str
    session_id: str
    matter_id: str
    user_id: str
    actor_id: str
    job_id: str
    tool: str
    capability: str | None
    outcome: ToolCallOutcome
    reason_code: str | None
    model_version: str
    prompt_version: str
    started_at: datetime
    finished_at: datetime | None = None
    result_refs: tuple[str, ...] = ()
    input_summary: str = ""


@dataclass(frozen=True)
class PendingAction:
    """A typed card awaiting human confirmation."""

    id: str
    session_id: str
    matter_id: str
    user_id: str
    action_kind: str
    arguments: dict[str, object]
    target_ref: str
    target_version: int
    expires_at: datetime
    created_at: datetime
    state: PendingActionState = PendingActionState.PROPOSED
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    reason_code: str | None = None

    def is_open(self, *, now: datetime) -> bool:
        return self.state is PendingActionState.PROPOSED and self.expires_at > now


@dataclass(frozen=True)
class TurnBudget:
    """Hard limits on one turn (`matter-agent-service.md` §Agent loop)."""

    max_tool_calls: int = 8
    timeout_seconds: int = 120
    history_messages: int = 20
    memory_results: int = 8


@dataclass(frozen=True)
class TurnResult:
    """What a completed turn produced, for the job row and the event."""

    job_id: str
    outcome: JobState
    tool_call_count: int
    assistant_message_id: str | None = None
    failure_class: str | None = None
    pending_action_ids: tuple[str, ...] = field(default_factory=tuple)

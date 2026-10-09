"""Domain models for the matter master agent.

Neon is authoritative for the transcript (`matter-agent-service.md` §Summary),
so `AgentMessage` carries its content and is the record, not an index into a
provider. Nothing here imports SQLAlchemy, FastAPI, or a provider SDK.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from src.modules.corpus_governance.contracts import AuthorityMetadata
from src.modules.matter_agent.domain.legal_context import (
    AgentLegalContext,
    authority_payload,
    legal_context_payload,
)


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
    EXECUTED = "executed"
    DECLINED = "declined"
    STALE = "stale"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SuggestionOrigin(StrEnum):
    """Provenance label stored on every agent-created record.

    A stored column, not a rendering convention
    (`matter-agent-service.md` §Document processing follow-through).
    """

    HUMAN = "human"
    AI_SUGGESTED = "ai_suggested"


@dataclass(frozen=True)
class AgentCitation:
    """An immutable pointer from an answer back to an authoritative record."""

    source_id: str
    source_type: str
    label: str
    verification_status: str
    locator: str | None = None
    source_file_id: str | None = None
    page: int | None = None
    version: int | None = None
    transaction_id: str | None = None
    subject_id: str | None = None
    passage: str | None = None
    corpus_version: str | None = None
    authority_metadata: AuthorityMetadata | None = None


def content_hash(
    content: str,
    citations: tuple[AgentCitation, ...] = (),
    legal_context: AgentLegalContext | None = None,
) -> str:
    """Hash visible answer text and its evidence pointers as one record."""
    # Preserve the hash of every pre-citation transcript row exactly.
    if not citations and legal_context is None:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    evidence = [
        {
            "sourceId": item.source_id,
            "sourceType": item.source_type,
            "label": item.label,
            "verificationStatus": item.verification_status,
            "locator": item.locator,
            **{
                k: v
                for k, v in {
                    "sourceFileId": item.source_file_id,
                    "page": item.page,
                    "version": item.version,
                    "transactionId": item.transaction_id,
                    "subjectId": item.subject_id,
                    "passage": item.passage,
                    "corpusVersion": item.corpus_version,
                    "authorityMetadata": authority_payload(item.authority_metadata)
                    if item.authority_metadata is not None
                    else None,
                }.items()
                if v is not None
            },
        }
        for item in citations
    ]
    canonical = json.dumps(
        {
            "content": content,
            "citations": evidence,
            **(
                {"legalContext": legal_context_payload(legal_context)}
                if legal_context is not None
                else {}
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    active_conversation_id: str | None = None


@dataclass(frozen=True)
class AgentConversation:
    """One visible segment inside the matter's durable assistant session."""

    id: str
    session_id: str
    matter_id: str
    user_id: str
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
    conversation_id: str | None = None
    citations: tuple[AgentCitation, ...] = ()
    legal_context: AgentLegalContext | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence starts at 1")
        if not self.content_hash:
            object.__setattr__(
                self, "content_hash", content_hash(self.content, self.citations, self.legal_context)
            )

    def hash_matches(self) -> bool:
        """True when the stored hash still describes the stored content."""
        return self.content_hash == content_hash(self.content, self.citations, self.legal_context)


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

    result: dict[str, object] = field(default_factory=dict)

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

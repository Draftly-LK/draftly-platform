"""Wire schemas for the matter agent API (camelCase, like every other module).

Nothing here serialises a domain object directly. Legal-state fields are closed
enums, never free strings (``api-conventions.md`` §9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _StrictCamel(_CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class SessionRead(_CamelModel):
    """The matter's single session. There is never a second one."""

    id: str
    matter_id: str
    state: Literal["active", "closed"]
    model_version: str
    prompt_version: str
    created_at: datetime
    updated_at: datetime
    active_conversation_id: str | None = None


class ConversationRead(_CamelModel):
    id: str
    state: Literal["active", "closed"]
    created_at: datetime
    updated_at: datetime


class CitationRead(_CamelModel):
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


class MessageRead(_CamelModel):
    """One transcript row, read from Neon."""

    id: str
    sequence: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    job_id: str | None = None
    pending_action_id: str | None = None
    conversation_id: str | None = None
    citations: list[CitationRead] = Field(default_factory=list)


class PageInfo(_CamelModel):
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class MessageListRead(_CamelModel):
    items: list[MessageRead]
    page: PageInfo


class SendMessageRequest(_StrictCamel):
    """Requires ``Idempotency-Key`` (``api-conventions.md`` §4)."""

    content: str = Field(min_length=1, max_length=10_000)


class JobRead(_CamelModel):
    """The job envelope from ``api-conventions.md`` §6.

    ``dead_letter`` is included: a turn that exhausts its attempts is a visible
    state, not a log line.
    """

    job_id: str
    state: Literal["queued", "running", "succeeded", "failed", "dead_letter"]
    poll_after_ms: int = 1500
    tool_call_count: int = 0
    failure_class: str | None = None


class PendingActionRead(_CamelModel):
    """An inline card. ``targetVersion`` is what a stale confirm trips on."""

    id: str
    action_kind: str
    target_ref: str
    target_version: int
    state: Literal[
        "proposed", "confirmed", "rejected", "expired", "executed", "declined", "stale", "failed"
    ]
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    reason_code: str | None = None
    expires_at: datetime
    created_at: datetime


class RejectActionRequest(_StrictCamel):
    reason: str | None = Field(default=None, max_length=500)


class MemoryStatusRead(_CamelModel):
    """Surfaced so the UI can show reduced recall without calling it a failure."""

    enabled: bool
    ready: bool

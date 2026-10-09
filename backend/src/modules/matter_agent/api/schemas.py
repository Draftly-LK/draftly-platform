"""Wire schemas for the matter agent API (camelCase, like every other module).

Nothing here serialises a domain object directly. Legal-state fields are closed
enums, never free strings (``api-conventions.md`` §9).
"""

from __future__ import annotations

from datetime import date, datetime
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


class LegalDateContextRead(_CamelModel):
    current_date: date
    transaction_id: str | None = None
    association_version: int | None = None
    transaction_date: date | None = None
    fact_id: str | None = None
    fact_version: int | None = None
    reason: Literal["reviewed-date", "date-missing", "date-conflict", "transaction-required"]


class AuthorityRelationshipRead(_CamelModel):
    relation: Literal["amends", "supersedes", "made-under", "commences"]
    target_source_id: str
    target_reference: str | None = None
    supporting_page: int | None = None
    review_state: Literal["unreviewed", "reviewed"]


class LegalAuthorityRead(_CamelModel):
    source_id: str
    title: str
    reference: str
    kind: Literal["statute", "amendment", "gazette"]
    source_url: str
    source_sha256: str
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    commencement_known: bool
    commencement_source_id: str | None = None
    commencement_page: int | None = None
    relationships: list[AuthorityRelationshipRead] = Field(default_factory=list)
    release_version: str
    review_state: Literal[
        "discovered",
        "provenance-recorded",
        "rights-reviewed",
        "content-reviewed",
        "approved",
        "quarantined",
        "retired",
        "unknown",
    ]
    currency_status: Literal["current", "superseded", "reverify", "unknown"]


class LegalContextRead(_CamelModel):
    kind: Literal["selection", "result"] = "result"
    transaction_id: str | None = None
    association_version: int | None = None
    date_context: LegalDateContextRead | None = None
    authorities: list[LegalAuthorityRead] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    source_release_version: str | None = None
    unavailable_reason: str | None = None
    visibility: Literal["available", "current-policy-unavailable"] = "available"


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
    authority_metadata: LegalAuthorityRead | None = None


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
    legal_context: LegalContextRead | None = None


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
    transaction_id: str | None = Field(default=None, min_length=1, max_length=128)
    association_version: int | None = Field(default=None, ge=1, strict=True)


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


class SendReceiptRead(_CamelModel):
    send_key: str
    matter_id: str
    conversation_id: str
    job_id: str


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

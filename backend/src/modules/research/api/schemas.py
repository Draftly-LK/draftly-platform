from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StrictCamel(CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ScopeInput(StrictCamel):
    type: Literal["library", "matter", "step", "document"]
    target_id: str | None = Field(default=None, max_length=64)


class ScopeRead(CamelModel):
    type: Literal["library", "matter", "step", "document"]
    target_id: str | None = None
    matter_id: str | None = None


class CreateConversationRequest(StrictCamel):
    scope: ScopeInput
    title: str | None = Field(default=None, max_length=256)


class RenameConversationRequest(StrictCamel):
    # A title of only whitespace is rejected rather than stored as blank.
    title: str = Field(min_length=1, max_length=256, pattern=r"\S")


class ConversationRead(CamelModel):
    id: str
    title: str
    scope: ScopeRead
    active_branch_id: str
    created_at: datetime
    updated_at: datetime


class ConversationListRead(CamelModel):
    items: list[ConversationRead]


class MessageCitationRead(CamelModel):
    id: str
    source_id: str
    authority_id: str
    passage: str
    page: int
    verified: bool
    # "case" citations are unverified research leads; earlier rows read as "statute".
    authority_kind: Literal["statute", "case"] = "statute"
    title: str | None = None
    reference: str | None = None
    source_url: str | None = None


class MessageClaimRead(CamelModel):
    """One answer claim and the authority ids it cites, in answer order."""

    text: str
    citation_ids: list[str]


class MessageRead(CamelModel):
    id: str
    conversation_id: str
    branch_id: str
    parent_message_id: str | None = None
    edited_from_id: str | None = None
    role: Literal["user", "assistant", "tool", "system"]
    content: str
    answer_id: str | None = None
    citations: list[MessageCitationRead] = Field(default_factory=list)
    claims: list[MessageClaimRead] = Field(default_factory=list)
    created_at: datetime


class MessageListRead(CamelModel):
    items: list[MessageRead]


class SendMessageRequest(StrictCamel):
    content: str = Field(min_length=1, max_length=10_000)
    parent_message_id: str | None = None
    # Legal sources to search. Defaults to the original statutes-only behaviour.
    sources: Literal["statutes", "cases", "all"] = "statutes"


class JobRead(CamelModel):
    job_id: str
    state: Literal["queued", "running", "succeeded", "failed"]
    poll_after_ms: int = 1500
    failure_class: str | None = None


class BranchRequest(StrictCamel):
    content: str | None = Field(default=None, max_length=10_000)


class BranchRead(CamelModel):
    id: str
    conversation_id: str
    root_message_id: str
    created_at: datetime


class SearchRequest(StrictCamel):
    query: str = Field(min_length=1, max_length=10_000)
    scope: ScopeInput


class SearchPassageRead(CamelModel):
    source_id: str
    authority_id: str
    title: str
    reference: str
    text: str
    page: int
    corpus_version: str
    verified: bool


class SearchRead(CamelModel):
    passages: list[SearchPassageRead]
    degraded_channels: list[str]


class ActionRequest(StrictCamel):
    answer_id: str
    action: Literal[
        "added-to-matter", "saved-to-library", "check-created", "authority-review-requested"
    ]
    matter_id: str | None = None


class ActionRead(CamelModel):
    id: str
    recorded: bool

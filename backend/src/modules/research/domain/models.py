from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ScopeType(str, Enum):
    LIBRARY = "library"
    MATTER = "matter"
    STEP = "step"
    DOCUMENT = "document"


class SourceScope(str, Enum):
    """Which legal sources a research question searches. Not the conversation scope."""

    STATUTES = "statutes"
    CASES = "cases"
    ALL = "all"


class AuthorityKind(str, Enum):
    """Where a cited passage came from. Case law is always an unverified research lead."""

    STATUTE = "statute"
    CASE = "case"


# Case ids in the judgment catalogue carry this prefix; it identifies case citations
# stored before the authority kind was recorded.
CASE_ID_PREFIX = "commonlii-"


def authority_kind_of(authority_id: str, recorded: str | None) -> AuthorityKind:
    if recorded:
        return AuthorityKind(recorded)
    if authority_id.lower().startswith(CASE_ID_PREFIX):
        return AuthorityKind.CASE
    return AuthorityKind.STATUTE


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Scope:
    type: ScopeType
    target_id: str | None = None
    matter_id: str | None = None


@dataclass(frozen=True)
class RetrievalPassage:
    source_id: str
    authority_id: str
    title: str
    reference: str
    text: str
    page: int
    corpus_version: str
    verified: bool = True
    kind: AuthorityKind = AuthorityKind.STATUTE
    source_url: str | None = None


@dataclass(frozen=True)
class ResearchConversation:
    id: str
    user_id: str
    title: str
    scope: Scope
    active_branch_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ResearchMessage:
    id: str
    conversation_id: str
    branch_id: str
    role: str
    content: str
    created_at: datetime
    parent_message_id: str | None = None
    edited_from_id: str | None = None
    answer_id: str | None = None


@dataclass(frozen=True)
class ResearchJob:
    id: str
    conversation_id: str
    user_message_id: str
    state: JobState
    corpus_version: str
    created_at: datetime
    finished_at: datetime | None = None
    failure_class: str | None = None


class RetrievalStatus(str, Enum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SearchResult:
    passages: list[RetrievalPassage] = field(default_factory=list)
    degraded_channels: list[str] = field(default_factory=list)
    status: RetrievalStatus = RetrievalStatus.COMPLETE
    corpus_version: str | None = None


@dataclass(frozen=True)
class ComposedClaim:
    text: str
    citation_ids: tuple[str, ...]

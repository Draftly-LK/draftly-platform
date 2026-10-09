"""The only surface other modules may import from task.

`draft` and `approval` need to know whether the checklist currently blocks
approval. They get a narrow read port, not the item aggregate, so neither can
decide an item's satisfaction on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.platform.request_context import RequestContext


class ChecklistBlockerPort(Protocol):
    """Requirements that currently block approval or registration-ready export."""

    async def blocking_requirement_ids(
        self, *, user_id: str, matter_id: str
    ) -> tuple[str, ...]: ...


class ChecklistLinkCommandPort(Protocol):
    """Lets `document` supersede links when a document is replaced (§5.4)."""

    async def supersede_document_links(
        self, *, user_id: str, detected_document_id: str, replacement_link_id: str | None = None
    ) -> int: ...


class DocumentLinkInvalidationPort(Protocol):
    async def invalidate_documents(
        self,
        *,
        user_id: str,
        matter_id: str,
        document_ids: tuple[str, ...],
        actor_id: str,
        correlation_id: str,
    ) -> None: ...


@dataclass(frozen=True)
class ReadinessReference:
    kind: str
    id: str
    version: int | None = None
    generation: int | None = None
    transaction_id: str | None = None
    subject_id: str | None = None
    association_version: int | None = None


@dataclass(frozen=True)
class ReadinessDependency:
    category: str
    state: str
    references: tuple[ReadinessReference, ...] = ()


class ReadinessSourcePort(Protocol):
    async def readiness_dependencies(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[ReadinessDependency, ...]: ...

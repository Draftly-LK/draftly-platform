"""The only surface other modules may import from task.

`draft` and `approval` need to know whether the checklist currently blocks
approval. They get a narrow read port, not the item aggregate, so neither can
decide an item's satisfaction on its own.
"""

from __future__ import annotations

from typing import Protocol


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

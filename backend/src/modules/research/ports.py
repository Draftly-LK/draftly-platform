from __future__ import annotations

from typing import Protocol

from src.modules.research.domain.models import ComposedClaim, RetrievalPassage, Scope, SearchResult


class LegalRetrievalPort(Protocol):
    async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult: ...


class GroundedAnswerComposerPort(Protocol):
    async def compose(
        self, question: str, passages: list[RetrievalPassage]
    ) -> tuple[ComposedClaim, ...]: ...


class SessionMemoryPort(Protocol):
    async def recall(self, *, user_id: str, conversation_id: str, scope: Scope) -> list[str]: ...
    async def ingest(self, *, user_id: str, conversation_id: str, answer_id: str) -> None: ...

from __future__ import annotations

from src.modules.research.domain.models import RetrievalStatus, Scope, SearchResult


class NullLegalRetrieval:
    """Fail-closed adapter used until an approved corpus release is installed."""

    async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult:
        return SearchResult(
            degraded_channels=["dense", "graph", "rewrite"], status=RetrievalStatus.UNAVAILABLE
        )

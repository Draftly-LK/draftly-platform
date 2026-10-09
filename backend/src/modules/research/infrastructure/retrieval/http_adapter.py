"""HTTP adapter over the deployed retrieval engine's read-only `/search`.

`StatuteRetrievalAdapter` (`statute_adapter.py`) reads a small SQLite corpus
baked into this image at build time — a "pinned 57-statute/18-amendment
release" that goes stale the moment the retrieval engine's own index is
rebuilt from a newer research-repo checkout. This adapter calls that engine
instead, over the internal network (`RETRIEVAL_BASE_URL`, never exposed
publicly — see deploy/PRODUCTION.md), so the two stop drifting apart.

`/search` never returns full section text (the engine's own API strips it,
even from `/answer` — a deliberate boundary on that side, not a bug on ours),
so passages are built from each hit's `excerpt`: real corpus text, just
shorter than a full section. `GroundedStatuteComposer` composes from that
exactly as it already does from the bundled corpus; nothing about the compose
step changes.

Fails closed like `NullLegalRetrieval`: any network error, timeout, or
malformed response degrades to no passages rather than raising, so a slow or
unreachable retrieval container turns into "insufficient authority," never a
500.
"""

from __future__ import annotations

import httpx
import structlog

from src.modules.research.domain.models import RetrievalPassage, Scope, SearchResult

log = structlog.get_logger(__name__)

_TIMEOUT_SECONDS = 10.0
_LIMIT = 12


class HttpStatuteRetrievalAdapter:
    """Read-only lexical retrieval over the deployed retrieval engine."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = _TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # None in every real deployment; a test passes httpx.MockTransport.
        self._transport = transport

    async def search(self, query: str, scope: Scope, corpus_version: str) -> SearchResult:
        del scope  # the engine has no matter- or scope-aware index yet
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(
                    f"{self._base_url}/search", params={"q": query, "limit": _LIMIT}
                )
                response.raise_for_status()
                hits = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("research.retrieval_engine_unreachable", error_class=type(exc).__name__)
            return SearchResult(degraded_channels=["retrieval-engine"])

        if not isinstance(hits, list):
            log.warning("research.retrieval_engine_bad_response", body_type=type(hits).__name__)
            return SearchResult(degraded_channels=["retrieval-engine"])

        passages: list[RetrievalPassage] = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            try:
                section_id = str(hit["section_id"])
                excerpt = str(hit.get("excerpt") or "").strip()
            except KeyError:
                continue
            if not excerpt:
                continue
            section = section_id.rsplit(":s", 1)[-1]
            passages.append(
                RetrievalPassage(
                    source_id=str(hit.get("source_id", "")),
                    authority_id=section_id,
                    title=str(hit.get("title", "")),
                    reference=f"Section {section}",
                    text=excerpt,
                    page=0,  # not carried by this API; only the bundled adapter has it
                    corpus_version=corpus_version,
                    verified=False,
                )
            )
        # Dense and graph expansion are not part of this engine's deployed
        # index (RETRIEVAL_WITH_EMBEDDINGS=0 — see deploy/README.md); say so
        # rather than implying coverage this response does not have.
        return SearchResult(passages=passages, degraded_channels=["dense", "graph"])

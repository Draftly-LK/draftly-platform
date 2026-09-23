"""HttpStatuteRetrievalAdapter: mapping and fail-closed degradation.

No real network call — every case injects an httpx.MockTransport standing in
for the retrieval engine.
"""

from __future__ import annotations

import httpx
import pytest

from src.modules.research.domain.models import Scope, ScopeType
from src.modules.research.infrastructure.retrieval.http_adapter import (
    HttpStatuteRetrievalAdapter,
)

CORPUS_VERSION = "statutes-bm25-v1:test"
SCOPE = Scope(ScopeType.LIBRARY)


def _adapter(handler) -> HttpStatuteRetrievalAdapter:
    return HttpStatuteRetrievalAdapter(
        base_url="http://retrieval.internal:8000",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_maps_hits_into_passages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["q"] == "prescription"
        return httpx.Response(
            200,
            json=[
                {
                    "source_id": "SRC071",
                    "section_id": "SRC071:s14",
                    "title": "Prescription Ordinance",
                    "excerpt": "Any person who has possessed land for ten years...",
                },
            ],
        )

    result = await _adapter(handler).search("prescription", SCOPE, CORPUS_VERSION)
    assert result.degraded_channels == ["dense", "graph"]
    assert len(result.passages) == 1
    passage = result.passages[0]
    assert passage.source_id == "SRC071"
    assert passage.authority_id == "SRC071:s14"
    assert passage.title == "Prescription Ordinance"
    assert passage.reference == "Section 14"
    assert passage.text == "Any person who has possessed land for ten years..."
    assert passage.corpus_version == CORPUS_VERSION
    assert passage.verified is False


@pytest.mark.asyncio
async def test_a_hit_with_no_excerpt_is_skipped_rather_than_grounding_on_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json=[
                {"source_id": "SRC071", "section_id": "SRC071:s14", "title": "x", "excerpt": ""},
                {
                    "source_id": "SRC071",
                    "section_id": "SRC071:s15",
                    "title": "x",
                    "excerpt": "real text",
                },
            ],
        )

    result = await _adapter(handler).search("q", SCOPE, CORPUS_VERSION)
    assert [p.authority_id for p in result.passages] == ["SRC071:s15"]


@pytest.mark.asyncio
async def test_connection_failure_degrades_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = await _adapter(handler).search("q", SCOPE, CORPUS_VERSION)
    assert result.passages == []
    assert result.degraded_channels == ["retrieval-engine"]


@pytest.mark.asyncio
async def test_timeout_degrades_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    result = await _adapter(handler).search("q", SCOPE, CORPUS_VERSION)
    assert result.degraded_channels == ["retrieval-engine"]


@pytest.mark.asyncio
async def test_a_server_error_status_degrades_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503, text="index rebuilding")

    result = await _adapter(handler).search("q", SCOPE, CORPUS_VERSION)
    assert result.degraded_channels == ["retrieval-engine"]


@pytest.mark.asyncio
async def test_a_non_list_body_degrades_instead_of_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"detail": "not what this adapter expects"})

    result = await _adapter(handler).search("q", SCOPE, CORPUS_VERSION)
    assert result.passages == []
    assert result.degraded_channels == ["retrieval-engine"]


@pytest.mark.asyncio
async def test_a_hit_missing_section_id_is_skipped_not_fatal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json=[
                {"source_id": "SRC071", "title": "no section_id", "excerpt": "text"},
                {
                    "source_id": "SRC071",
                    "section_id": "SRC071:s1",
                    "title": "ok",
                    "excerpt": "text",
                },
            ],
        )

    result = await _adapter(handler).search("q", SCOPE, CORPUS_VERSION)
    assert [p.authority_id for p in result.passages] == ["SRC071:s1"]

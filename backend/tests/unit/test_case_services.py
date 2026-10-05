from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.modules.auth.domain.models import Role
from src.modules.library.api.case_schemas import CaseRecordRead, InternalCaseListRead
from src.modules.library.application.cases import CaseLibraryService
from src.modules.library.domain.cases import CaseCorpusUnavailableError, CaseFilters
from src.modules.library.infrastructure.case_http import HttpCaseAdapter
from src.modules.research.api.case_schemas import CaseSearchRead
from src.modules.research.application.cases import CaseResearchService
from src.modules.research.infrastructure.case_operations import SqlCaseSearchOperations
from src.modules.research.infrastructure.retrieval.case_http import HttpCaseSearchAdapter
from src.platform.api.pagination import InvalidCursorError
from src.platform.db.idempotency import IdempotencyConflictError, IdempotencyKeyRow
from src.platform.request_context import RequestContext

CTX = RequestContext("synthetic-user", Role.REVIEWER, "synthetic-correlation")
COVERAGE = {
    "catalogueRecords": 2,
    "retrievalRecords": 1,
    "readerOverlapRecords": 1,
    "collections": {"LKCA": 2},
    "retrievalScope": "conveyancing-only",
    "minYear": 2000,
    "maxYear": 2000,
}
CASE = {
    "id": "commonlii-LKCA-2000-1",
    "title": "Synthetic case",
    "citation": "[2000] synthetic 1",
    "collection": "LKCA",
    "decidingCourt": "Supreme Court",
    "year": 2000,
    "decisionDate": "2000-01-01",
    "reportSeries": "NLR",
    "sourceUrl": "https://www.commonlii.org/lk/cases/LKCA/2000/1.html",
    "provenance": "commonlii-parsed",
    "verificationState": "parsed-unverified",
    "qualityWarnings": [],
    "displayPolicy": "metadata-only",
    "textSha256": "a" * 64,
    "text": None,
    "displayApprovalReference": None,
}
EMPTY = {
    "corpusVersion": "synthetic-v1",
    "coverage": COVERAGE,
    "items": [],
    "outcome": "no_similar_cases",
    "degradedChannels": [],
    "denseStatus": "disabled",
}


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={**EMPTY, "outcome": "similar_cases_found"}),
    ],
)
async def test_http_failure_or_malformed_response_never_becomes_empty(response):
    adapter = HttpCaseSearchAdapter(
        base_url="http://retrieval", transport=httpx.MockTransport(lambda request: response)
    )
    with pytest.raises(CaseCorpusUnavailableError):
        await adapter.search_cases("Synthetic facts", limit=8)


async def test_post_search_does_not_put_fact_pattern_in_url():
    def respond(request):
        assert request.method == "POST"
        assert str(request.url) == "http://retrieval/v1/cases/search"
        assert b"Synthetic facts" in request.content
        return httpx.Response(200, json=EMPTY)

    result = await HttpCaseSearchAdapter(
        base_url="http://retrieval", transport=httpx.MockTransport(respond)
    ).search_cases("Synthetic facts", limit=8)
    assert result.outcome == "no_similar_cases"


async def test_detail_404_and_actor_header():
    def respond(request):
        assert request.headers["X-Draftly-Actor"] == CTX.actor_id
        return httpx.Response(404)

    assert (
        await HttpCaseAdapter(
            base_url="http://retrieval", transport=httpx.MockTransport(respond)
        ).get_case(CASE["id"], actor_id=CTX.actor_id)
        is None
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"sourceUrl": "javascript:alert(1)"},
        {"text": "forbidden"},
        {"verificationState": "lawyer-verified"},
    ],
)
def test_case_schema_fails_closed(changed):
    with pytest.raises(ValueError):
        CaseRecordRead.model_validate({**CASE, **changed})


async def test_cursor_scope_version_and_tamper_validation():
    class Catalogue:
        version = "synthetic-v1"

        async def list_cases(self, filters, **kwargs):
            return InternalCaseListRead.model_validate(
                {
                    "corpusVersion": self.version,
                    "coverage": COVERAGE,
                    "items": [CASE],
                    "hasMore": True,
                }
            ).domain()

    catalogue = Catalogue()
    service = CaseLibraryService(catalogue)
    _, page = await service.browse(CTX, CaseFilters(), limit=1)
    assert page.next_cursor
    await service.browse(CTX, CaseFilters(), limit=1, cursor=page.next_cursor)
    for filters, ctx, cursor in [
        (CaseFilters(collection="LKSC"), CTX, page.next_cursor),
        (CaseFilters(), replace(CTX, actor_id="other-user"), page.next_cursor),
        (CaseFilters(), CTX, "tampered"),
    ]:
        with pytest.raises(InvalidCursorError):
            await service.browse(ctx, filters, limit=1, cursor=cursor)
    catalogue.version = "changed-v2"
    with pytest.raises(InvalidCursorError):
        await service.browse(CTX, CaseFilters(), limit=1, cursor=page.next_cursor)


class FakeBilling:
    reserves = 0
    consumes = 0
    enabled = True

    async def require_feature_or_raise(self, user_id, feature):
        assert feature == "research.enabled"
        if not self.enabled:
            raise ValueError("feature denied")

    async def reserve_usage(self, user_id, metric, quantity, operation_id):
        assert metric == "research_queries.monthly" and quantity == 1
        self.reserves += 1
        return SimpleNamespace(id="synthetic-reservation")

    async def consume_usage(self, user_id, reservation_id, quantity):
        self.consumes += quantity


class FakeAudit:
    def __init__(self):
        self.events = []

    async def record(self, event):
        self.events.append(event)


@pytest.fixture
async def operations_db(tmp_path):
    engine = create_async_engine(
        "sqlite+aiosqlite:///" + (tmp_path / "operations.sqlite").as_posix()
    )
    async with engine.begin() as conn:
        await conn.run_sync(IdempotencyKeyRow.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_concurrent_replay_conflict_empty_consumption_and_safe_audit(operations_db):
    billing, audit = FakeBilling(), FakeAudit()
    calls = 0

    class Retrieval:
        async def search_cases(self, query, *, limit):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return CaseSearchRead.model_validate(EMPTY).domain()

    async def search(query="Synthetic private facts"):
        async with operations_db() as session:
            service = CaseResearchService(
                Retrieval(), SqlCaseSearchOperations(session, billing, audit)
            )
            return await service.search(CTX, query, key="synthetic-attempt")

    first, second = await asyncio.gather(search(), search())
    assert first == second
    assert calls == billing.reserves == billing.consumes == 1
    assert len(audit.events) == 1
    from src.modules.audit.domain.models import AuditAction, AuditTargetType

    assert AuditAction(audit.events[0].action) is AuditAction.RESEARCH_CASES_SEARCHED
    assert AuditTargetType(audit.events[0].target_type) is AuditTargetType.CASE_SEARCH
    assert "private" not in repr(vars(audit.events[0]))
    with pytest.raises(IdempotencyConflictError):
        await search("Different synthetic facts")
    assert billing.reserves == 1


async def test_retrieval_failure_rolls_back_replay_and_never_consumes(operations_db):
    billing, audit = FakeBilling(), FakeAudit()

    class Retrieval:
        async def search_cases(self, query, *, limit):
            raise CaseCorpusUnavailableError()

    async with operations_db() as session:
        service = CaseResearchService(Retrieval(), SqlCaseSearchOperations(session, billing, audit))
        with pytest.raises(CaseCorpusUnavailableError):
            await service.search(CTX, "Synthetic private facts", key="synthetic-attempt")
        assert (await session.execute(select(IdempotencyKeyRow))).scalars().all() == []
    assert billing.consumes == 0 and audit.events == []


async def test_feature_denial_precedes_retrieval_and_reservation(operations_db):
    billing, audit = FakeBilling(), FakeAudit()
    billing.enabled = False
    async with operations_db() as session:
        service = CaseResearchService(None, SqlCaseSearchOperations(session, billing, audit))
        with pytest.raises(ValueError, match="feature denied"):
            await service.search(CTX, "Synthetic private facts", key="synthetic-attempt")
    assert billing.reserves == 0


async def test_quota_denial_never_runs_retrieval_or_consumes(operations_db):
    from src.modules.billing.domain.errors import QuotaExceededError

    class QuotaBilling(FakeBilling):
        async def reserve_usage(self, user_id, metric, quantity, operation_id):
            raise QuotaExceededError(metric=metric)

    billing, audit = QuotaBilling(), FakeAudit()
    async with operations_db() as session:
        service = CaseResearchService(None, SqlCaseSearchOperations(session, billing, audit))
        with pytest.raises(QuotaExceededError):
            await service.search(CTX, "Synthetic private facts", key="synthetic-attempt")
    assert billing.consumes == 0 and audit.events == []


async def test_real_app_case_route_precedes_statute_dynamic_route_and_requires_auth():
    from src.api.deps import get_request_context
    from src.main import create_app
    from src.modules.library.api.case_router import get_case_library_service
    from src.modules.research.api.case_router import get_case_research_service

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        for method, path in [
            ("GET", "/api/v1/library/cases"),
            ("GET", "/api/v1/library/cases/commonlii-LKCA-2000-1"),
            ("POST", "/api/v1/research/cases/search"),
        ]:
            response = await client.request(
                method, path, json={"query": "Synthetic facts"} if method == "POST" else None
            )
            assert response.status_code == 401

    class Catalogue:
        async def list_cases(self, filters, **kwargs):
            return InternalCaseListRead.model_validate(
                {
                    "corpusVersion": "synthetic-v1",
                    "coverage": COVERAGE,
                    "items": [CASE],
                    "hasMore": False,
                }
            ).domain()

        async def get_case(self, case_id, *, actor_id):
            from src.modules.library.api.case_schemas import CaseDetailRead

            assert actor_id == CTX.actor_id
            return CaseDetailRead.model_validate(
                {"corpusVersion": "synthetic-v1", "coverage": COVERAGE, "item": CASE}
            ).domain()

    class Research:
        async def search(self, ctx, query, *, limit, key):
            assert ctx.actor_id == CTX.actor_id
            assert key == "synthetic-attempt"
            return CaseSearchRead.model_validate(EMPTY).domain()

    app.dependency_overrides[get_request_context] = lambda: CTX
    app.dependency_overrides[get_case_library_service] = lambda: CaseLibraryService(Catalogue())
    app.dependency_overrides[get_case_research_service] = lambda: Research()
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        response = await client.get("/api/v1/library/cases")
        assert response.status_code == 200
        assert response.json()["items"][0]["id"] == CASE["id"]
        assert response.json()["page"]["limit"] == 25
        response = await client.get(
            "/api/v1/library/cases/" + CASE["id"], headers={"X-Draftly-Actor": "untrusted-user"}
        )
        assert response.status_code == 200
        response = await client.post(
            "/api/v1/research/cases/search",
            json={"query": "Synthetic facts"},
            headers={"Idempotency-Key": "synthetic-attempt"},
        )
        assert response.status_code == 200
        assert response.json()["outcome"] == "no_similar_cases"


async def test_required_key_contract_preserves_missing_key_error_envelope():
    from src.api.deps import get_request_context
    from src.main import create_app
    from src.modules.research.api.case_router import get_case_research_service

    app = create_app()
    post = app.openapi()["paths"]["/api/v1/research/cases/search"]["post"]
    headers = [
        parameter
        for parameter in post.get("parameters", [])
        if parameter["name"] == "Idempotency-Key"
    ]
    assert len(headers) == 1 and headers[0]["required"] is True
    app.dependency_overrides[get_request_context] = lambda: CTX
    app.dependency_overrides[get_case_research_service] = lambda: CaseResearchService(None, None)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://api"
    ) as client:
        response = await client.post(
            "/api/v1/research/cases/search", json={"query": "Synthetic facts"}
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_required"

"""Persistent recovery reads against a disposable in-memory database.

All uploads are synthetic; provider doubles never send bytes outside the test.
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.api.deps import get_request_context
from src.modules.auth.domain.models import Role
from src.modules.content_governance.contracts import ProcessingFailureReason, SourceFileState
from src.modules.document.api import ingestion_router
from src.modules.document.application.ingestion_service import SourceFileIngestionService
from src.modules.document.application.processing_job import SynchronousProcessingJob
from src.modules.document.domain.errors import SourceFileNotFoundError, SourceFileStaleError
from src.modules.document.domain.ingestion import ProcessingRun
from src.modules.document.domain.v1 import (
    OcrPage,
    PageClassification,
    PageQualityStatus,
    ProcessedPage,
    RotationDecision,
    RotationStatus,
    V1PipelineReport,
)
from src.modules.document.infrastructure.orm import (
    DetectedDocumentRow,
    DocumentFragmentRow,
    DocumentProcessingPageRow,
    SourceFileProcessingRunRow,
    SourceFileRow,
)
from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository
from src.modules.document.tests.test_ingestion_service import FakeAudit, FakeStorage, ScriptedJob
from src.platform.db.session import Base, get_db
from src.platform.request_context import RequestContext
from tests.factories.document import synthetic_pdf

USER = "usr_synthetic_processing"
MATTER = "mat_synthetic_processing"
NOW = datetime(2026, 10, 9, tzinfo=UTC)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync,
                tables=[
                    SourceFileRow.__table__,
                    DetectedDocumentRow.__table__,
                    DocumentFragmentRow.__table__,
                    SourceFileProcessingRunRow.__table__,
                    DocumentProcessingPageRow.__table__,
                ],
            )
        )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


def service_for(session: AsyncSession, *, unavailable: bool = True):
    storage = FakeStorage()
    jobs = (
        SynchronousProcessingJob(
            storage=storage,
            pipeline=None,
            provider_name="unavailable",
            data_protection_approved=False,
        )
        if unavailable
        else ScriptedJob(())
    )
    return SourceFileIngestionService(
        repository=SqlDocumentIngestionRepository(session),
        storage=storage,
        jobs=jobs,
        audit=FakeAudit(),
        max_upload_bytes=10_000,
        max_page_count=300,
    )


async def upload(service):
    return await service.upload_source_file(
        user_id=USER,
        matter_id=MATTER,
        actor_id=USER,
        correlation_id="corr_synthetic",
        filename="synthetic-processing.pdf",
        declared_media_type="application/pdf",
        data=synthetic_pdf(),
    )


async def process(service, source_id: str, version: int):
    return await service.process_source_file(
        user_id=USER,
        source_file_id=source_id,
        actor_id=USER,
        correlation_id="corr_synthetic",
        expected_version=version,
    )


async def test_failed_run_reason_survives_new_service_and_session(session):
    service = service_for(session)
    uploaded = await upload(service)
    result = await process(service, uploaded.source_file.id, 1)
    await session.commit()
    session.expunge_all()
    refreshed = await service_for(session).get_processing_status(
        user_id=USER, source_file_id=uploaded.source_file.id
    )
    assert refreshed.source.source_file.version == 3
    assert refreshed.latest_run.id == result.run.id
    assert refreshed.latest_run.outcome is SourceFileState.PROCESSING_FAILED
    assert refreshed.latest_run.failure_reason is ProcessingFailureReason.NOT_CONFIGURED
    assert refreshed.latest_run.failure_explanation_key == "rta.source_file.failure.not_configured"
    assert not refreshed.latest_run.succeeded


async def test_unprocessed_source_has_no_fabricated_run(session):
    service = service_for(session)
    uploaded = await upload(service)
    status = await service.get_processing_status(
        user_id=USER, source_file_id=uploaded.source_file.id
    )
    assert status.latest_run is None


async def test_retry_rejects_stale_version_then_preserves_both_attempts(session):
    service = service_for(session)
    uploaded = await upload(service)
    await process(service, uploaded.source_file.id, 1)
    with pytest.raises(SourceFileStaleError):
        await process(service, uploaded.source_file.id, 1)
    latest = await service.get_source_file(user_id=USER, source_file_id=uploaded.source_file.id)
    await process(service, uploaded.source_file.id, latest.source_file.version)
    runs = await SqlDocumentIngestionRepository(session).list_runs_for_source_file(
        USER, uploaded.source_file.id
    )
    assert len(runs) == 2
    assert all(run.failure_reason is ProcessingFailureReason.NOT_CONFIGURED for run in runs)


async def test_latest_run_has_deterministic_tie_breaker_and_excludes_other_accounts(session):
    service = service_for(session)
    uploaded = await upload(service)
    repo = SqlDocumentIngestionRepository(session)
    for run_id, owner in (("run_a", USER), ("run_z", USER), ("run_zz_other", "usr_other")):
        await repo.create_run(
            ProcessingRun(
                id=run_id,
                user_id=owner,
                matter_id=MATTER,
                source_file_id=uploaded.source_file.id,
                provider="synthetic",
                outcome=SourceFileState.PROCESSING_FAILED,
                started_at=NOW,
                finished_at=NOW,
                correlation_id="corr_synthetic",
                reasons=("PROVIDER_ERROR",),
                failure_reason=ProcessingFailureReason.PROVIDER_ERROR,
            )
        )
    latest = await repo.get_latest_run_for_source_file(USER, MATTER, uploaded.source_file.id)
    assert latest.id == "run_z"
    assert (
        await repo.get_latest_run_for_source_file(USER, "mat_other", uploaded.source_file.id)
        is None
    )
    with pytest.raises(SourceFileNotFoundError):
        await service.get_processing_status(
            user_id="usr_other", source_file_id=uploaded.source_file.id
        )


async def test_retained_page_failure_requires_manual_review_after_refresh(session):
    service = service_for(session, unavailable=False)
    uploaded = await upload(service)
    result = await process(service, uploaded.source_file.id, 1)
    repo = SqlDocumentIngestionRepository(session)
    page = ProcessedPage(
        page_no=2,
        original_width=100,
        original_height=200,
        corrected_width=100,
        corrected_height=200,
        quality_status=PageQualityStatus.OCR_FAILED,
        rotation=RotationDecision(None, 0, 0.0, 0, RotationStatus.UNCERTAIN),
        ocr=OcrPage("", (), ()),
        corrected_webp=b"synthetic",
        ocr_json=b"{}",
        plain_text=b"",
        classification=PageClassification(2, "other", None, False, 0.0),
        derivative_refs={
            "corrected_webp": ("synthetic-webp", "1"),
            "corrected_ocr_json": ("synthetic-ocr", "1"),
            "plain_ocr_text": ("synthetic-text", "1"),
        },
    )
    await repo.create_run(
        ProcessingRun(
            id="run_partial",
            user_id=USER,
            matter_id=MATTER,
            source_file_id=uploaded.source_file.id,
            provider="synthetic",
            outcome=SourceFileState.PROCESSED,
            started_at=datetime(2026, 10, 10, tzinfo=UTC),
            finished_at=NOW,
            correlation_id="corr_synthetic",
            pages_processed=2,
            v1_report=V1PipelineReport((page,), (), 1, 0),
        )
    )
    await session.commit()
    session.expunge_all()
    status = await service_for(session).get_processing_status(
        user_id=USER, source_file_id=uploaded.source_file.id
    )
    assert status.latest_run.id != result.run.id
    assert status.manual_review_required
    assert [
        (page.page_no, page.quality_status, page.rotation_status) for page in status.page_outcomes
    ] == [(2, "ocr_failed", "rotation_uncertain")]


async def test_status_api_returns_failure_etag_and_hides_foreign_source(session, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://synthetic:synthetic@localhost:1/synthetic"
    )
    monkeypatch.setenv(
        "DATABASE_URL_DIRECT", "postgresql+psycopg://synthetic:synthetic@localhost:1/synthetic"
    )
    from src.main import create_app

    service = service_for(session)
    uploaded = await upload(service)
    await process(service, uploaded.source_file.id, 1)
    calls = []

    async def authorize(ctx, matter_id, db, capability):
        calls.append((matter_id, capability))

    monkeypatch.setattr(ingestion_router, "_authorized_matter", authorize)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[ingestion_router.get_ingestion_service] = lambda: service
    app.dependency_overrides[get_request_context] = lambda: RequestContext(
        actor_id=USER, account_role=Role.APPROVER, correlation_id="corr_synthetic"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/source-files/{uploaded.source_file.id}/processing")
        assert response.status_code == 200
        assert response.headers["etag"] == '"3"'
        assert response.json()["latestRun"]["state"] == "failed"
        assert response.json()["latestRun"]["failureReason"] == "NOT_CONFIGURED"
        assert "storageObjectKey" not in response.text
        assert calls == [(MATTER, "rta.document.classify")]
        app.dependency_overrides[get_request_context] = lambda: RequestContext(
            actor_id="usr_other", account_role=Role.APPROVER, correlation_id="corr_synthetic"
        )
        response = await client.get(f"/api/v1/source-files/{uploaded.source_file.id}/processing")
        assert response.status_code == 404

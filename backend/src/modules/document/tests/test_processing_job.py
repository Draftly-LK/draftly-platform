"""Unit tests for the gates between stored bytes and the extraction pipeline.

Fakes only: no database, no network, no provider. Every byte string here is
synthetic test material, not client evidence.

The load-bearing test is
``test_bytes_that_do_not_match_the_recorded_hash_never_reach_the_provider``.
Its pipeline call-count assertion is the point: an integrity failure that still
sent the document would leak evidence the deployment could not vouch for.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from src.modules.content_governance.contracts import ProcessingFailureReason, SourceFileState
from src.modules.document.application.processing_job import SynchronousProcessingJob
from src.modules.document.domain.errors import SourceObjectIntegrityError
from src.modules.document.domain.ingestion import SourceFile
from src.modules.document.domain.models import ProcessingOutcome, ProcessingReport
from src.modules.document.domain.v1 import (
    ExtractedCandidate,
    LogicalDocument,
    OcrPage,
    PageClassification,
    PageQualityStatus,
    ProcessedLogicalDocument,
    ProcessedPage,
    RotationDecision,
    RotationStatus,
    V1PipelineReport,
)
from src.modules.document.ports import MatterDocumentTypes

KEY = "sources/usr_1/mat_1/src_1"
BYTES = b"%PDF-1.7\nsynthetic\n"
NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeStorage:
    """Hands back whatever bytes the test scripted, recording the pinned version."""

    def __init__(self, data: bytes = BYTES) -> None:
        self._data = data
        self.reads: list[tuple[str, str]] = []
        self.writes: list[tuple[str, bytes]] = []

    async def put(self, key: str, data: bytes) -> str:
        self.writes.append((key, data))
        return "generation-1"

    async def get(self, key: str, *, version: str) -> bytes:
        self.reads.append((key, version))
        return self._data

    async def exists(self, key: str) -> bool:
        return True


class CountingPipeline:
    """Counts calls, so a test can prove the provider was never reached."""

    def __init__(self) -> None:
        self.calls = 0

    async def process(
        self,
        data: bytes,
        media_type: str,
        *,
        synthetic: bool = False,
        correlation_id: str = "",
    ) -> ProcessingReport:
        self.calls += 1
        return ProcessingReport(
            outcome=ProcessingOutcome.MANUAL_REVIEW,
            kind="unknown",
            kind_model_confidence=0.0,
            page_count=1,
            provider="fake",
        )


def make_source_file(*, data: bytes = BYTES, version: str = "42") -> SourceFile:
    return SourceFile(
        id="src_1",
        user_id="usr_1",
        matter_id="mat_1",
        original_filename="synthetic.pdf",
        media_type="application/pdf",
        byte_length=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_object_key=KEY,
        storage_object_version=version,
        upload_actor_id="usr_1",
        state=SourceFileState.STORED,
        retention_class="matter_evidence",
        created_at=NOW,
        updated_at=NOW,
    )


def make_job(
    *,
    storage: FakeStorage,
    pipeline: CountingPipeline | None,
    approved: bool = True,
) -> SynchronousProcessingJob:
    return SynchronousProcessingJob(
        storage=storage,  # type: ignore[arg-type]
        pipeline=pipeline,  # type: ignore[arg-type]
        provider_name="fake",
        data_protection_approved=approved,
    )


# ── The integrity gate (§6.2 stage 2) ────────────────────────────────────────


async def test_bytes_that_do_not_match_the_recorded_hash_never_reach_the_provider() -> None:
    # The record says one thing; storage returned another. Something altered
    # evidence of record, so the run stops rather than extracting from it.
    pipeline = CountingPipeline()
    storage = FakeStorage(b"%PDF-1.7\ntampered\n")
    job = make_job(storage=storage, pipeline=pipeline)

    with pytest.raises(SourceObjectIntegrityError):
        await job.enqueue(source_file=make_source_file())

    assert pipeline.calls == 0


async def test_bytes_that_match_the_recorded_hash_proceed_to_extraction() -> None:
    pipeline = CountingPipeline()
    job = make_job(storage=FakeStorage(), pipeline=pipeline)

    run = await job.enqueue(source_file=make_source_file())

    assert pipeline.calls == 1
    assert run.outcome is not SourceFileState.PROCESSING_FAILED


async def test_the_read_is_pinned_to_the_version_recorded_at_upload() -> None:
    storage = FakeStorage()
    job = make_job(storage=storage, pipeline=CountingPipeline())

    await job.enqueue(source_file=make_source_file(version="9001"))

    assert storage.reads == [(KEY, "9001")]


# ── Ordering: the earlier gates still come first ─────────────────────────────


async def test_a_closed_data_protection_gate_is_refused_without_reading_the_bytes() -> None:
    storage = FakeStorage(b"%PDF-1.7\ntampered\n")
    job = make_job(storage=storage, pipeline=CountingPipeline(), approved=False)

    run = await job.enqueue(source_file=make_source_file())

    assert run.failure_reason is ProcessingFailureReason.DATA_PROTECTION_GATE
    # The gate is about evidence not leaving the deployment, so it must be
    # decided before anything is fetched — not after an integrity check.
    assert storage.reads == []


async def test_an_unconfigured_provider_is_refused_without_reading_the_bytes() -> None:
    storage = FakeStorage()
    job = make_job(storage=storage, pipeline=None)

    run = await job.enqueue(source_file=make_source_file())

    assert run.failure_reason is ProcessingFailureReason.NOT_CONFIGURED
    assert storage.reads == []


async def test_v1_writes_three_immutable_derivatives_and_keeps_candidates_unverified() -> None:
    classification = PageClassification(1, "rta.doc.title_certificate", None, True, 0.92)
    page = ProcessedPage(
        page_no=1,
        original_width=100,
        original_height=200,
        corrected_width=100,
        corrected_height=200,
        quality_status=PageQualityStatus.NORMAL,
        rotation=RotationDecision(0, 0, 1.0, 12, RotationStatus.NOT_REQUIRED),
        ocr=OcrPage("synthetic", (), ()),
        corrected_webp=b"webp",
        ocr_json=b"{}",
        plain_text=b"synthetic",
        classification=classification,
    )
    logical = LogicalDocument(1, classification.type_id, None, (1,), "synthetic")
    report = V1PipelineReport(
        pages=(page,),
        logical_documents=(
            ProcessedLogicalDocument(
                logical,
                (ExtractedCandidate("parcelNo", "0020", 1, 0.8),),
            ),
        ),
        classification_calls=1,
        extraction_calls=1,
    )

    class Pipeline:
        async def process(self, *_args: object, **_kwargs: object) -> V1PipelineReport:
            return report

    class Types:
        async def for_matter(self, **_kwargs: object) -> MatterDocumentTypes:
            return MatterDocumentTypes((classification.type_id,), {})

    storage = FakeStorage()
    job = SynchronousProcessingJob(
        storage=storage,  # type: ignore[arg-type]
        pipeline=None,
        provider_name="vision-gemini",
        data_protection_approved=True,
        v1_pipeline=Pipeline(),  # type: ignore[arg-type]
        matter_document_types=Types(),  # type: ignore[arg-type]
    )

    run = await job.enqueue(source_file=make_source_file())

    assert len(storage.writes) == 3
    assert {key.rsplit("/", 1)[-1] for key, _ in storage.writes} == {
        "page.webp",
        "ocr.json",
        "text.txt",
    }
    assert run.candidates[0].candidate_fields[0].value == "0020"
    assert page.derivative_refs["corrected_webp"][1] == "generation-1"

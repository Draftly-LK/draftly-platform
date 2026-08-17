"""Ingestion service — upload, processing honesty, versions, and corrections.

Fakes only: no database, no network, no provider. Every byte string here is
synthetic test material, not client evidence.

The test that matters most is
``test_a_file_nothing_processed_is_reported_as_unprocessed``: with no provider
wired the run must finish ``PROCESSING_FAILED`` / ``NOT_CONFIGURED`` and the
file must never reach ``PROCESSED``.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.modules.auth.ports import AuditEventInput
from src.modules.content_governance.contracts import (
    UNIDENTIFIED_DOCUMENT_CLASS_ID,
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    ProcessingFailureReason,
    SourceFileState,
)
from src.modules.document.application.ingestion_service import SourceFileIngestionService
from src.modules.document.application.processing_job import SynchronousProcessingJob
from src.modules.document.domain.errors import (
    SourceFileTooLargeError,
    UnknownDocumentClassError,
)
from src.modules.document.domain.ingestion import (
    DetectedDocument,
    DocumentCandidate,
    DocumentFragment,
    FragmentRange,
    ProcessingRun,
    SourceFile,
)

USER = "usr_1"
MATTER = "mat_1"
TITLE_CLASS = "rta.doc.title_certificate"


def synthetic_pdf(pages: int = 2) -> bytes:
    """A structurally minimal PDF. Synthetic — no client content whatsoever."""
    body = b"".join(b"/Type /Page \n" for _ in range(pages))
    return b"%PDF-1.7\n" + body + b"%%EOF\n"


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeRepository:
    """In-memory stand-in that keeps the tenant filter the real one enforces."""

    def __init__(self) -> None:
        self.sources: dict[str, SourceFile] = {}
        self.documents: dict[str, DetectedDocument] = {}
        self.fragments: dict[str, DocumentFragment] = {}
        self.runs: list[ProcessingRun] = []
        self._clock = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)

    def _tick(self) -> datetime:
        self._clock += timedelta(seconds=1)
        return self._clock

    async def create_source_file(self, source: SourceFile) -> SourceFile:
        stored = replace(source, created_at=self._tick())
        self.sources[stored.id] = stored
        return replace(stored)

    async def get_source_file(self, user_id: str, source_file_id: str) -> SourceFile | None:
        source = self.sources.get(source_file_id)
        return replace(source) if source and source.user_id == user_id else None

    async def list_source_files(
        self, user_id: str, matter_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[SourceFile], str | None]:
        rows = [
            replace(source)
            for source in self.sources.values()
            if source.user_id == user_id and source.matter_id == matter_id
        ]
        rows.sort(key=lambda source: source.created_at, reverse=True)
        return rows[:limit], None

    async def list_source_files_by_sha256(
        self, user_id: str, matter_id: str, sha256: str
    ) -> list[SourceFile]:
        return [
            replace(source)
            for source in self.sources.values()
            if source.user_id == user_id
            and source.matter_id == matter_id
            and source.sha256 == sha256
        ]

    async def source_file_hashes(self, user_id: str, matter_id: str) -> list[tuple[str, str]]:
        rows = sorted(
            (
                source
                for source in self.sources.values()
                if source.user_id == user_id
                and source.matter_id == matter_id
                and source.state is not SourceFileState.REJECTED
            ),
            key=lambda source: source.created_at,
        )
        return [(source.id, source.sha256) for source in rows]

    async def update_source_file(self, source: SourceFile, expected_version: int) -> SourceFile:
        current = self.sources[source.id]
        assert current.version == expected_version, "stale write reached the repository"
        saved = replace(source, version=expected_version + 1, updated_at=self._tick())
        self.sources[saved.id] = saved
        return replace(saved)

    async def create_document(self, document: DetectedDocument) -> DetectedDocument:
        self.documents[document.id] = replace(document)
        return replace(document)

    async def get_document(self, user_id: str, document_id: str) -> DetectedDocument | None:
        document = self.documents.get(document_id)
        return replace(document) if document and document.user_id == user_id else None

    async def list_documents(self, user_id: str, matter_id: str) -> list[DetectedDocument]:
        return [
            replace(document)
            for document in self.documents.values()
            if document.user_id == user_id and document.matter_id == matter_id
        ]

    async def update_document(
        self, document: DetectedDocument, expected_version: int
    ) -> DetectedDocument:
        current = self.documents[document.id]
        assert current.version == expected_version, "stale write reached the repository"
        saved = replace(document, version=expected_version + 1)
        self.documents[saved.id] = saved
        return replace(saved)

    async def create_fragments(self, fragments: list[DocumentFragment]) -> list[DocumentFragment]:
        for fragment in fragments:
            self.fragments[fragment.id] = fragment
        return list(fragments)

    async def list_fragments_for_matter(
        self, user_id: str, matter_id: str
    ) -> list[DocumentFragment]:
        return [
            fragment
            for fragment in self.fragments.values()
            if fragment.user_id == user_id and fragment.matter_id == matter_id
        ]

    async def list_fragments_for_document(
        self, user_id: str, document_id: str
    ) -> list[DocumentFragment]:
        return sorted(
            (
                fragment
                for fragment in self.fragments.values()
                if fragment.user_id == user_id and fragment.detected_document_id == document_id
            ),
            key=lambda fragment: fragment.order_in_document,
        )

    async def list_document_ids_for_source_file(
        self, user_id: str, source_file_id: str
    ) -> list[str]:
        return sorted(
            {
                fragment.detected_document_id
                for fragment in self.fragments.values()
                if fragment.user_id == user_id and fragment.source_file_id == source_file_id
            }
        )

    async def replace_fragments(
        self, user_id: str, document_id: str, fragments: list[DocumentFragment]
    ) -> list[DocumentFragment]:
        for fragment in list(self.fragments.values()):
            if fragment.user_id == user_id and fragment.detected_document_id == document_id:
                del self.fragments[fragment.id]
        return await self.create_fragments(fragments)

    async def create_run(self, run: ProcessingRun) -> ProcessingRun:
        self.runs.append(run)
        return run


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> str:
        self.objects[key] = data
        return f"sha256:{len(data)}"

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def exists(self, key: str) -> bool:
        return key in self.objects


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def record(self, event: AuditEventInput) -> None:
        self.events.append((event.action, event.target_id))

    @property
    def actions(self) -> list[str]:
        return [action for action, _ in self.events]


class ScriptedJob:
    """Returns a prepared run, so document materialisation can be tested alone."""

    def __init__(self, candidates: tuple[DocumentCandidate, ...], *, pages: int = 2) -> None:
        self._candidates = candidates
        self._pages = pages
        self.calls = 0

    async def enqueue(self, *, source_file: SourceFile, correlation_id: str = "") -> ProcessingRun:
        self.calls += 1
        now = datetime(2026, 8, 16, 10, 0, tzinfo=UTC)
        return ProcessingRun(
            id=f"run_{self.calls}",
            user_id=source_file.user_id,
            matter_id=source_file.matter_id,
            source_file_id=source_file.id,
            provider="fake",
            outcome=SourceFileState.PROCESSED,
            started_at=now,
            finished_at=now,
            correlation_id=correlation_id,
            pages_processed=self._pages,
            ai_extraction_calls=1,
            candidates=tuple(
                replace(candidate, source_file_id=source_file.id) for candidate in self._candidates
            ),
        )


class FakeChecklistLinks:
    def __init__(self) -> None:
        self.superseded: list[str] = []

    async def supersede_document_links(
        self, *, user_id: str, detected_document_id: str, replacement_link_id: str | None = None
    ) -> int:
        self.superseded.append(detected_document_id)
        return 1


def make_candidate(
    *, class_id: str | None = TITLE_CLASS, confidence: float = 0.9, pages: tuple[int, int] = (1, 2)
) -> DocumentCandidate:
    return DocumentCandidate(
        page_start=pages[0],
        page_end=pages[1],
        source_file_id="src_placeholder",
        boundary_confidence=None,
        continuity_anomaly=False,
        class_id=class_id,
        class_confidence=confidence,
    )


def build_service(
    *,
    repository: FakeRepository | None = None,
    storage: FakeStorage | None = None,
    audit: FakeAudit | None = None,
    jobs: object | None = None,
    max_upload_bytes: int = 10_000,
    max_page_count: int = 300,
    checklist_links: FakeChecklistLinks | None = None,
) -> SourceFileIngestionService:
    return SourceFileIngestionService(
        repository=repository or FakeRepository(),  # type: ignore[arg-type]
        storage=storage or FakeStorage(),
        jobs=jobs or ScriptedJob((make_candidate(),)),  # type: ignore[arg-type]
        audit=audit or FakeAudit(),  # type: ignore[arg-type]
        max_upload_bytes=max_upload_bytes,
        max_page_count=max_page_count,
        checklist_links=checklist_links,
    )


async def upload(
    service: SourceFileIngestionService,
    *,
    data: bytes | None = None,
    filename: str = "synthetic-title.pdf",
    declared_media_type: str | None = "application/pdf",
):  # type: ignore[no-untyped-def]
    return await service.upload_source_file(
        user_id=USER,
        matter_id=MATTER,
        actor_id=USER,
        correlation_id="corr_1",
        filename=filename,
        declared_media_type=declared_media_type,
        data=synthetic_pdf() if data is None else data,
    )


# ── Upload (§6.2 stages 1–2) ─────────────────────────────────────────────────


async def test_upload_hashes_and_stores_the_bytes_server_side() -> None:
    repo, storage, audit = FakeRepository(), FakeStorage(), FakeAudit()
    service = build_service(repository=repo, storage=storage, audit=audit)

    result = await upload(service)
    source = result.source_file

    assert source.state is SourceFileState.STORED
    assert len(source.sha256) == 64
    assert storage.objects[source.storage_object_key] == synthetic_pdf()
    assert source.storage_object_version
    assert audit.actions == ["rta.source-file.uploaded"]


async def test_media_type_is_read_from_the_bytes_not_the_filename() -> None:
    service = build_service()
    result = await upload(service, filename="notes.txt", declared_media_type="text/plain")
    assert result.source_file.media_type == "application/pdf"


async def test_an_unsupported_file_is_recorded_as_rejected_with_a_reason() -> None:
    repo, storage, audit = FakeRepository(), FakeStorage(), FakeAudit()
    service = build_service(repository=repo, storage=storage, audit=audit)

    result = await upload(service, data=b"this is not a document at all")
    source = result.source_file

    assert source.state is SourceFileState.REJECTED
    assert source.failure_reason is ProcessingFailureReason.UNSUPPORTED_MEDIA
    assert source.failure_explanation_key == "rta.source_file.failure.unsupported_media"
    # Refused bytes are never written to storage, but the refusal is a record.
    assert storage.objects == {}
    assert source.id in repo.sources
    assert audit.actions == ["rta.source-file.rejected"]


async def test_a_password_protected_pdf_is_rejected_recoverably() -> None:
    service = build_service()
    locked = b"%PDF-1.7\ntrailer<</Encrypt 9 0 R>>"
    result = await upload(service, data=locked)
    assert result.source_file.failure_reason is ProcessingFailureReason.PASSWORD_PROTECTED


async def test_the_page_limit_comes_from_settings_and_rejects_recoverably() -> None:
    service = build_service(max_page_count=2)
    result = await upload(service, data=synthetic_pdf(pages=5))
    assert result.source_file.state is SourceFileState.REJECTED
    assert result.source_file.failure_reason is ProcessingFailureReason.PAGE_LIMIT_EXCEEDED


async def test_an_oversized_upload_is_refused_before_it_becomes_a_record() -> None:
    repo = FakeRepository()
    service = build_service(repository=repo, max_upload_bytes=16)
    with pytest.raises(SourceFileTooLargeError):
        await upload(service, data=synthetic_pdf(pages=20))
    assert repo.sources == {}


async def test_a_duplicate_upload_is_detected_and_both_copies_are_kept() -> None:
    repo, storage = FakeRepository(), FakeStorage()
    service = build_service(repository=repo, storage=storage)

    first = await upload(service)
    second = await upload(service)

    assert second.view.version_relationship is DocumentVersionRelationship.EXACT_DUPLICATE
    assert second.view.duplicate_of_source_file_id == first.source_file.id
    # Nothing is deleted: two rows, two stored objects (§6.3).
    assert len(repo.sources) == 2
    assert len(storage.objects) == 2
    assert second.source_file.state is SourceFileState.STORED


# ── Processing honesty (§6.2 stage 10, §6.4) ─────────────────────────────────


async def test_a_file_nothing_processed_is_reported_as_unprocessed() -> None:
    """No provider wired: PROCESSING_FAILED / NOT_CONFIGURED, never PROCESSED."""
    repo, storage = FakeRepository(), FakeStorage()
    job = SynchronousProcessingJob(
        storage=storage, pipeline=None, provider_name="none", data_protection_approved=True
    )
    service = build_service(repository=repo, storage=storage, jobs=job)
    uploaded = await upload(service)

    view = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_2",
        expected_version=uploaded.source_file.version,
    )

    assert view.run.outcome is SourceFileState.PROCESSING_FAILED
    assert view.run.failure_reason is ProcessingFailureReason.NOT_CONFIGURED
    assert view.source_file.state is SourceFileState.PROCESSING_FAILED
    assert view.source_file.state is not SourceFileState.PROCESSED
    assert view.source_file.failure_explanation_key == "rta.source_file.failure.not_configured"
    assert view.documents == ()
    # The attempt is still recorded: the file is provably unprocessed, not lost.
    assert len(repo.runs) == 1


async def test_a_closed_data_protection_gate_stops_the_document_reaching_a_provider() -> None:
    class ExplodingPipeline:
        async def process(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("the document must not reach the provider")

    repo, storage = FakeRepository(), FakeStorage()
    job = SynchronousProcessingJob(
        storage=storage,
        pipeline=ExplodingPipeline(),  # type: ignore[arg-type]
        provider_name="gemini",
        data_protection_approved=False,
    )
    service = build_service(repository=repo, storage=storage, jobs=job)
    uploaded = await upload(service)

    view = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_3",
        expected_version=uploaded.source_file.version,
    )

    assert view.run.failure_reason is ProcessingFailureReason.DATA_PROTECTION_GATE
    assert view.source_file.state is SourceFileState.PROCESSING_FAILED


async def test_a_successful_run_creates_documents_in_the_band_it_earned() -> None:
    repo = FakeRepository()
    # A high score with no reported top-two margin cannot be auto-filed (§6.4).
    job = ScriptedJob((make_candidate(confidence=0.99),))
    service = build_service(repository=repo, jobs=job)
    uploaded = await upload(service)

    view = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_4",
        expected_version=uploaded.source_file.version,
    )

    assert view.source_file.state is SourceFileState.PROCESSED
    document = view.documents[0].document
    assert document.class_status is DocumentClassStatus.REVIEW_REQUIRED
    assert document.boundary_status is BoundaryStatus.CANDIDATE
    assert view.documents[0].fragments[0].boundary_confidence is None


async def test_an_unplaceable_document_lands_unidentified_without_a_guess() -> None:
    job = ScriptedJob((make_candidate(class_id=None, confidence=0.99),))
    service = build_service(jobs=job)
    uploaded = await upload(service)

    view = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_5",
        expected_version=uploaded.source_file.version,
    )
    document = view.documents[0].document
    assert document.class_status is DocumentClassStatus.UNIDENTIFIED
    assert document.class_id is None
    assert document.class_confidence is None


async def test_reprocessing_never_overwrites_documents_a_lawyer_may_have_decided() -> None:
    repo = FakeRepository()
    job = ScriptedJob((make_candidate(),))
    service = build_service(repository=repo, jobs=job)
    uploaded = await upload(service)

    first = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_6",
        expected_version=uploaded.source_file.version,
    )
    second = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_7",
        expected_version=first.source_file.version,
    )

    assert len(repo.documents) == 1
    assert second.candidates_withheld is True
    assert len(repo.runs) == 2


# ── The §6.3 shapes, end to end ──────────────────────────────────────────────


async def test_one_pdf_can_hold_several_documents() -> None:
    job = ScriptedJob(
        (
            make_candidate(pages=(1, 2)),
            make_candidate(pages=(3, 4), class_id="rta.doc.nic"),
        )
    )
    service = build_service(jobs=job)
    uploaded = await upload(service)
    await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_8",
        expected_version=uploaded.source_file.version,
    )

    inbox = await service.get_document_inbox(user_id=USER, matter_id=MATTER)
    assert len(inbox.documents) == 2
    assert inbox.source_files[0].contains_multiple_documents is True
    assert len(inbox.source_files[0].detected_document_ids) == 2


async def test_one_document_can_span_two_files_without_merging_bytes() -> None:
    repo, storage = FakeRepository(), FakeStorage()
    service = build_service(repository=repo, storage=storage)
    first = await upload(service)
    second = await upload(service, data=synthetic_pdf(pages=3))
    run = await service.process_source_file(
        user_id=USER,
        source_file_id=first.source_file.id,
        actor_id=USER,
        correlation_id="corr_9",
        expected_version=first.source_file.version,
    )
    document = run.documents[0].document

    joined = await service.decide_boundary(
        user_id=USER,
        document_id=document.id,
        ranges=[
            FragmentRange(
                source_file_id=first.source_file.id,
                page_start=1,
                page_end=2,
                order_in_document=0,
            ),
            FragmentRange(
                source_file_id=second.source_file.id,
                page_start=1,
                page_end=3,
                order_in_document=1,
            ),
        ],
        actor_id=USER,
        correlation_id="corr_10",
        expected_version=document.version,
    )

    assert joined.spans_multiple_sources is True
    assert joined.source_file_ids == (first.source_file.id, second.source_file.id)
    assert joined.document.boundary_status is BoundaryStatus.CONFIRMED
    # Both source objects are untouched by the correction.
    assert len(storage.objects) == 2
    assert all(source.state is not SourceFileState.REJECTED for source in repo.sources.values())


async def test_a_superseded_source_keeps_its_row_and_its_links_are_superseded() -> None:
    repo, links = FakeRepository(), FakeChecklistLinks()
    service = build_service(repository=repo, checklist_links=links)
    older = await upload(service)
    newer = await upload(service, data=synthetic_pdf(pages=3))
    processed = await service.process_source_file(
        user_id=USER,
        source_file_id=older.source_file.id,
        actor_id=USER,
        correlation_id="corr_11",
        expected_version=older.source_file.version,
    )

    view = await service.supersede_source_file(
        user_id=USER,
        source_file_id=older.source_file.id,
        replacement_source_file_id=newer.source_file.id,
        actor_id=USER,
        correlation_id="corr_12",
        expected_version=processed.source_file.version,
        reason="A later certified copy was issued.",
    )

    assert view.source_file.state is SourceFileState.SUPERSEDED
    assert view.source_file.superseded_by_source_file_id == newer.source_file.id
    # The row, its hash, and its stored object all survive.
    assert older.source_file.id in repo.sources
    assert repo.sources[older.source_file.id].sha256 == older.source_file.sha256
    document_id = processed.documents[0].document.id
    assert repo.documents[document_id].version_relationship is (
        DocumentVersionRelationship.SUPERSEDED
    )
    assert links.superseded == [document_id]


async def test_a_probable_newer_version_flags_the_pair_without_moving_state() -> None:
    repo = FakeRepository()
    service = build_service(repository=repo)
    older = await upload(service)
    newer = await upload(service, data=synthetic_pdf(pages=3))
    processed = await service.process_source_file(
        user_id=USER,
        source_file_id=older.source_file.id,
        actor_id=USER,
        correlation_id="corr_13",
        expected_version=older.source_file.version,
    )

    view = await service.supersede_source_file(
        user_id=USER,
        source_file_id=older.source_file.id,
        replacement_source_file_id=newer.source_file.id,
        actor_id=USER,
        correlation_id="corr_14",
        expected_version=processed.source_file.version,
        relationship=DocumentVersionRelationship.POSSIBLE_VERSION,
    )

    # §6.3 asks the lawyer which is current before anything is superseded.
    assert view.source_file.state is SourceFileState.PROCESSED
    assert view.source_file.superseded_by_source_file_id is None
    document_id = processed.documents[0].document.id
    assert repo.documents[document_id].version_relationship is (
        DocumentVersionRelationship.POSSIBLE_VERSION
    )


# ── Lawyer corrections (§6.5) ────────────────────────────────────────────────


async def test_confirming_a_class_drops_the_score_that_belonged_to_the_old_one() -> None:
    audit = FakeAudit()
    service = build_service(audit=audit, jobs=ScriptedJob((make_candidate(confidence=0.9),)))
    uploaded = await upload(service)
    run = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_15",
        expected_version=uploaded.source_file.version,
    )
    document = run.documents[0].document
    assert document.class_confidence == 0.9

    corrected = await service.decide_classification(
        user_id=USER,
        document_id=document.id,
        class_id="rta.doc.nic",
        actor_id=USER,
        correlation_id="corr_16",
        expected_version=document.version,
        note="Filed under the wrong class by the classifier.",
    )

    assert corrected.document.class_status is DocumentClassStatus.LAWYER_CONFIRMED
    assert corrected.document.class_id == "rta.doc.nic"
    assert corrected.document.class_confidence is None
    assert "rta.document.classified" in audit.actions


async def test_a_lawyer_may_answer_unidentified() -> None:
    """§6.3: an unplaceable document is never resolved to the nearest class."""
    service = build_service(jobs=ScriptedJob((make_candidate(),)))
    uploaded = await upload(service)
    run = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_17",
        expected_version=uploaded.source_file.version,
    )
    document = run.documents[0].document

    answered = await service.decide_classification(
        user_id=USER,
        document_id=document.id,
        class_id=UNIDENTIFIED_DOCUMENT_CLASS_ID,
        actor_id=USER,
        correlation_id="corr_18",
        expected_version=document.version,
    )
    assert answered.document.class_status is DocumentClassStatus.UNIDENTIFIED


async def test_a_class_outside_the_rule_pack_is_refused() -> None:
    service = build_service(jobs=ScriptedJob((make_candidate(),)))
    uploaded = await upload(service)
    run = await service.process_source_file(
        user_id=USER,
        source_file_id=uploaded.source_file.id,
        actor_id=USER,
        correlation_id="corr_19",
        expected_version=uploaded.source_file.version,
    )
    document = run.documents[0].document

    with pytest.raises(UnknownDocumentClassError):
        await service.decide_classification(
            user_id=USER,
            document_id=document.id,
            class_id="something.the.lawyer.typed",
            actor_id=USER,
            correlation_id="corr_20",
            expected_version=document.version,
        )


# ── Storage adapter (§6.2 stage 2) ───────────────────────────────────────────


async def test_stored_bytes_are_written_once_and_read_back_identically(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.modules.document.infrastructure.storage_filesystem import (
        FilesystemSourceFileStorage,
    )

    storage = FilesystemSourceFileStorage(tmp_path)
    key = "sources/usr_1/mat_1/src_1"
    version = await storage.put(key, synthetic_pdf())

    assert await storage.exists(key) is True
    assert await storage.get(key) == synthetic_pdf()
    # A retried upload of identical bytes is idempotent, not a conflict.
    assert await storage.put(key, synthetic_pdf()) == version


async def test_different_bytes_never_replace_stored_evidence(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.modules.document.domain.errors import SourceObjectImmutableError
    from src.modules.document.infrastructure.storage_filesystem import (
        FilesystemSourceFileStorage,
    )

    storage = FilesystemSourceFileStorage(tmp_path)
    key = "sources/usr_1/mat_1/src_1"
    await storage.put(key, synthetic_pdf())
    with pytest.raises(SourceObjectImmutableError):
        await storage.put(key, synthetic_pdf(pages=9))
    assert await storage.get(key) == synthetic_pdf()


async def test_a_key_cannot_escape_the_storage_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.modules.document.infrastructure.storage_filesystem import (
        FilesystemSourceFileStorage,
    )

    storage = FilesystemSourceFileStorage(tmp_path)
    with pytest.raises(ValueError):
        await storage.put("../outside/src_1", b"%PDF-1.7\n")

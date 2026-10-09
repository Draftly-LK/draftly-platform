"""Ingestion application service — upload, process, organise, correct.

The rules this service exists to keep:

- **Uploaded bytes are written once and never rewritten** (§6.2 stage 2). There
  is no update path that touches the filename, the hash, or the stored object.
- **A duplicate is reported, not refused** (§6.3). The upload succeeds, the
  relationship comes back with it, and both copies stay.
- **Nothing claims to have been processed unless something processed it.** The
  terminal state comes from the run the job actually performed, through the
  §10.2 table, so ``PROCESSED`` is unreachable except from ``PROCESSING``.
- **A lawyer's correction never edits the model's output in place** (§6.5). A
  boundary decision replaces the fragment set and records both ends in the
  audit event; a classification decision drops the confidence that belonged to
  the class it scored.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

import structlog

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import (
    UNIDENTIFIED_DOCUMENT_CLASS_ID,
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    MatterState,
    ProcessingFailureReason,
    SourceFileState,
    get_document_class,
)
from src.modules.document.domain.errors import (
    DetectedDocumentNotFoundError,
    DetectedDocumentStaleError,
    ExtractionProviderError,
    SourceFileNotFoundError,
    SourceFileStaleError,
    SourceFileSupersedeTargetError,
    SourceFileTooLargeError,
    SourceObjectIntegrityError,
    UnknownDocumentClassError,
)
from src.modules.document.domain.grouping import PageAccounting, PageDisposition, account_pages
from src.modules.document.domain.ingestion import (
    DEFAULT_RETENTION_CLASS,
    DetectedDocument,
    DocumentFragment,
    FragmentRange,
    ProcessingPageOutcome,
    ProcessingRun,
    SourceFile,
)
from src.modules.document.domain.ingestion_policies import (
    SourceFileEvent,
    boundary_status_for,
    bundle_spans_multiple_sources,
    class_status_for,
    classify_duplicate,
    estimate_pdf_page_count,
    failure_explanation_key,
    find_exact_duplicate,
    is_password_protected_pdf,
    next_state,
    sniff_media_type,
    source_contains_multiple_documents,
    validate_boundary_decision,
)
from src.modules.document.domain.interpretation import InterpretationHistory, InterpretationPage
from src.modules.document.domain.v1 import ExtractedCandidate
from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository
from src.modules.document.ports import (
    MatterDocumentTypesPort,
    MatterWorkflowCommandPort,
    ProcessingJobPort,
    SourceFileStoragePort,
    StructuredDocumentExtractorPort,
)
from src.modules.matter.contracts import MatterMutationLockPort
from src.modules.task.contracts import ChecklistLinkCommandPort
from src.modules.verification.contracts import (
    FactEvidenceInvalidation,
    FactEvidenceInvalidationPort,
)
from src.platform import ids
from src.platform.errors import DomainRuleError, DraftlyError, PreconditionFailedError

log = structlog.get_logger(__name__)

_ResultT = TypeVar("_ResultT")
PROCESSING_TIMEOUT_SECONDS = 900.0
PROCESSING_RECOVERY_GRACE_SECONDS = 30.0


@dataclass(frozen=True)
class DocumentView:
    """One detected document with the pages it is made of."""

    document: DetectedDocument
    fragments: tuple[DocumentFragment, ...]

    @property
    def source_file_ids(self) -> tuple[str, ...]:
        seen: list[str] = []
        for fragment in self.fragments:
            if fragment.source_file_id not in seen:
                seen.append(fragment.source_file_id)
        return tuple(seen)

    @property
    def spans_multiple_sources(self) -> bool:
        """The §6.3 cross-file bundle, visible without merging any bytes."""
        return bundle_spans_multiple_sources(self.fragments)


@dataclass(frozen=True)
class SourceFileView:
    """One uploaded file with what was found in it and what it duplicates."""

    source_file: SourceFile
    detected_document_ids: tuple[str, ...]
    contains_multiple_documents: bool
    duplicate_of_source_file_id: str | None = None
    version_relationship: DocumentVersionRelationship | None = None


@dataclass(frozen=True)
class UploadResult:
    view: SourceFileView

    @property
    def source_file(self) -> SourceFile:
        return self.view.source_file


@dataclass(frozen=True)
class ProcessingRunView:
    """One run, the file it ran over, and what it proposed."""

    run: ProcessingRun
    source_file: SourceFile
    documents: tuple[DocumentView, ...]
    #: True when the run's candidates were not written because the file already
    #: has documents a lawyer may have decided on (§6.5).
    candidates_withheld: bool = False


@dataclass(frozen=True)
class ProcessingStatusView:
    source: SourceFileView
    latest_run: ProcessingRun | None
    page_outcomes: tuple[ProcessingPageOutcome, ...] = ()
    manual_review_required: bool = False


@dataclass(frozen=True)
class DocumentInboxView:
    """The grouped review queue for one matter (§11.1 Document Inbox)."""

    matter_id: str
    source_files: tuple[SourceFileView, ...]
    documents: tuple[DocumentView, ...]
    next_cursor: str | None = None
    page_accounting: tuple[PageAccounting, ...] = ()

    @property
    def boundary_review_document_ids(self) -> tuple[str, ...]:
        return tuple(
            view.document.id
            for view in self.documents
            if view.document.boundary_status is not BoundaryStatus.CONFIRMED
        )

    @property
    def classification_review_document_ids(self) -> tuple[str, ...]:
        return tuple(
            view.document.id
            for view in self.documents
            if view.document.class_status
            in {DocumentClassStatus.REVIEW_REQUIRED, DocumentClassStatus.AI_ORGANIZED}
        )

    @property
    def unidentified_document_ids(self) -> tuple[str, ...]:
        """§6.3: these stay in the inbox asking to be classified."""
        return tuple(
            view.document.id
            for view in self.documents
            if view.document.class_status is DocumentClassStatus.UNIDENTIFIED
        )

    @property
    def unprocessed_source_file_ids(self) -> tuple[str, ...]:
        """Stored but never processed, or processed and failed — reported as such."""
        return tuple(
            view.source_file.id
            for view in self.source_files
            if view.source_file.state
            in {
                SourceFileState.STORED,
                SourceFileState.PROCESSING,
                SourceFileState.PROCESSING_FAILED,
            }
        )


class SourceFileIngestionService:
    """Owns source files, detected documents, fragments, and processing runs."""

    def __init__(
        self,
        *,
        repository: SqlDocumentIngestionRepository,
        storage: SourceFileStoragePort,
        jobs: ProcessingJobPort,
        audit: AuditPort,
        max_upload_bytes: int,
        max_page_count: int,
        checklist_links: ChecklistLinkCommandPort | None = None,
        matter_workflow: MatterWorkflowCommandPort | None = None,
        matter_lock: MatterMutationLockPort | None = None,
        fact_invalidation: FactEvidenceInvalidationPort | None = None,
        refresh_extractor: StructuredDocumentExtractorPort | None = None,
        matter_document_types: MatterDocumentTypesPort | None = None,
        refresh_provider: str = "none",
        refresh_data_approved: bool = False,
    ) -> None:
        self._repo = repository
        self._matter_workflow = matter_workflow
        self._storage = storage
        self._jobs = jobs
        self._audit = audit
        self._max_upload_bytes = max_upload_bytes
        self._max_page_count = max_page_count
        self._checklist_links = checklist_links
        self._matter_lock = matter_lock
        self._fact_invalidation = fact_invalidation
        self._refresh_extractor = refresh_extractor
        self._matter_document_types = matter_document_types
        self._refresh_provider = refresh_provider
        self._refresh_data_approved = refresh_data_approved

    @property
    def max_upload_bytes(self) -> int:
        """Exposed so the transport can refuse oversized bytes before buffering."""
        return self._max_upload_bytes

    # ── Upload (§6.2 stages 1–2) ─────────────────────────────────────────────

    async def upload_source_file(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        filename: str,
        declared_media_type: str | None,
        data: bytes,
        derived_from_source_file_id: str | None = None,
    ) -> UploadResult:
        """Quarantine, store, and record one uploaded file.

        The media type is taken from the bytes, never from the filename or the
        client's ``Content-Type`` — both are claims by the uploader, and a
        mislabelled file that reached the rasterizer would fail much later and
        much less clearly.
        """
        if len(data) > self._max_upload_bytes:
            raise SourceFileTooLargeError(
                byteLength=len(data), maxByteLength=self._max_upload_bytes
            )

        if self._matter_lock:
            await self._matter_lock.lock(user_id, matter_id)

        now = datetime.now(tz=UTC)
        sha256 = hashlib.sha256(data).hexdigest()
        source_file_id = ids.new_id(ids.SOURCE_FILE)
        state = next_state(SourceFileState.UPLOAD_INITIATED, SourceFileEvent.BYTES_RECEIVED)

        sniffed = sniff_media_type(data)
        page_count = estimate_pdf_page_count(data)
        rejection = self._quarantine_failure(data, sniffed, page_count)

        # Both copies stay whatever the answer is; this only reports the pair.
        same_hash = await self._repo.list_source_files_by_sha256(user_id, matter_id, sha256)
        duplicate = find_exact_duplicate(sha256, same_hash)
        relationship = classify_duplicate(sha256, same_hash)

        if rejection is not None:
            source = SourceFile(
                id=source_file_id,
                user_id=user_id,
                matter_id=matter_id,
                original_filename=filename,
                # On a rejected row this is the uploader's claim about the file,
                # which is precisely what was disbelieved.
                media_type=declared_media_type or "application/octet-stream",
                byte_length=len(data),
                sha256=sha256,
                storage_object_key="",
                storage_object_version="",
                upload_actor_id=actor_id,
                state=next_state(state, SourceFileEvent.CHECK_FAILED),
                retention_class=DEFAULT_RETENTION_CLASS,
                created_at=now,
                updated_at=now,
                page_count=page_count,
                failure_reason=rejection,
                failure_explanation_key=failure_explanation_key(rejection),
                derived_from_source_file_id=derived_from_source_file_id,
            )
            saved = await self._repo.create_source_file(source)
            await self._record(
                user_id=user_id,
                matter_id=matter_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                action=AuditAction.RTA_SOURCE_FILE_REJECTED,
                target_type=AuditTargetType.SOURCE_FILE,
                target_id=saved.id,
                after_ref=f"{saved.state.value}/{rejection.value}",
            )
            return UploadResult(
                view=SourceFileView(
                    source_file=saved,
                    detected_document_ids=(),
                    contains_multiple_documents=False,
                    duplicate_of_source_file_id=duplicate.id if duplicate else None,
                    version_relationship=relationship,
                )
            )

        state = next_state(state, SourceFileEvent.CHECKS_PASSED)
        # Bytes go to storage before the row is committed, so a failed request
        # can leave an object with no row. That is the safe direction: the
        # reverse — a row promising bytes that were never written — would be a
        # source file the lawyer could open and find empty. The key is derived
        # from the id, so an orphan object is never reused or overwritten.
        storage_key = f"sources/{user_id}/{matter_id}/{source_file_id}"
        storage_version = await self._storage.put(storage_key, data)
        state = next_state(state, SourceFileEvent.IMMUTABLE_WRITE_CONFIRMED)

        saved = await self._repo.create_source_file(
            SourceFile(
                id=source_file_id,
                user_id=user_id,
                matter_id=matter_id,
                original_filename=filename,
                media_type=sniffed or "application/octet-stream",
                byte_length=len(data),
                sha256=sha256,
                storage_object_key=storage_key,
                storage_object_version=storage_version,
                upload_actor_id=actor_id,
                state=state,
                retention_class=DEFAULT_RETENTION_CLASS,
                created_at=now,
                updated_at=now,
                page_count=page_count,
                derived_from_source_file_id=derived_from_source_file_id,
            )
        )
        await self._record(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_SOURCE_FILE_UPLOADED,
            target_type=AuditTargetType.SOURCE_FILE,
            target_id=saved.id,
            # ``before_ref`` names the copy this upload duplicates, so the audit
            # trail shows the pair even after the inbox has been worked through.
            before_ref=duplicate.id if duplicate else None,
            after_ref=f"sha256:{sha256}",
        )
        return UploadResult(
            view=SourceFileView(
                source_file=saved,
                detected_document_ids=(),
                contains_multiple_documents=False,
                duplicate_of_source_file_id=duplicate.id if duplicate else None,
                version_relationship=relationship,
            )
        )

    def _quarantine_failure(
        self, data: bytes, sniffed: str | None, page_count: int | None
    ) -> ProcessingFailureReason | None:
        """§6.2 stage 1. Every refusal names a reason the lawyer can act on."""
        if sniffed is None:
            return ProcessingFailureReason.UNSUPPORTED_MEDIA
        if is_password_protected_pdf(data):
            return ProcessingFailureReason.PASSWORD_PROTECTED
        if page_count is not None and page_count > self._max_page_count:
            return ProcessingFailureReason.PAGE_LIMIT_EXCEEDED
        return None

    # ── Reads ────────────────────────────────────────────────────────────────

    async def list_source_files(
        self, *, user_id: str, matter_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[tuple[SourceFileView, ...], str | None]:
        sources, next_cursor = await self._repo.list_source_files(
            user_id, matter_id, limit=limit, cursor=cursor
        )
        fragments = await self._repo.list_fragments_for_matter(user_id, matter_id)
        duplicates = self._duplicate_map(await self._repo.source_file_hashes(user_id, matter_id))
        return (
            tuple(self._source_view(source, fragments, duplicates) for source in sources),
            next_cursor,
        )

    async def get_source_file(self, *, user_id: str, source_file_id: str) -> SourceFileView:
        source = await self._require_source(user_id, source_file_id)
        fragments = await self._repo.list_fragments_for_matter(user_id, source.matter_id)
        duplicates = self._duplicate_map(
            await self._repo.source_file_hashes(user_id, source.matter_id)
        )
        return self._source_view(source, fragments, duplicates)

    async def read_original(
        self, *, user_id: str, source_file_id: str, actor_id: str, correlation_id: str
    ) -> tuple[SourceFile, bytes]:
        """The uploaded bytes, for the lawyer to see what they are classifying.

        Scoped to the actor's matters like every read here. The bytes are checked
        against the hash taken at upload before they leave, so a viewer never shows
        anything but the recorded original, and the view is audited.
        """
        source = await self._require_source(user_id, source_file_id)
        if not source.has_stored_bytes:
            raise SourceFileNotFoundError(sourceFileId=source_file_id)
        data = await self._storage.get(
            source.storage_object_key, version=source.storage_object_version
        )
        if hashlib.sha256(data).hexdigest() != source.sha256:
            raise SourceObjectIntegrityError(
                sourceFileId=source.id,
                storageObjectKey=source.storage_object_key,
                storageObjectVersion=source.storage_object_version,
            )
        await self._record(
            user_id=user_id,
            matter_id=source.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_SOURCE_FILE_VIEWED,
            target_type=AuditTargetType.SOURCE_FILE,
            target_id=source.id,
        )
        return source, data

    async def get_processing_status(
        self, *, user_id: str, source_file_id: str
    ) -> ProcessingStatusView:
        """Read the latest recorded attempt, never infer success from source presence."""
        source = await self.get_source_file(user_id=user_id, source_file_id=source_file_id)
        run = await self._repo.get_latest_run_for_source_file(
            user_id, source.source_file.matter_id, source_file_id
        )
        if run is None:
            return ProcessingStatusView(source=source, latest_run=None)
        pages = await self._repo.list_run_page_outcomes(
            user_id, source.source_file.matter_id, source_file_id, run.id
        )
        documents = [
            await self._require_document(user_id, document_id)
            for document_id in source.detected_document_ids
        ]
        requires_review = (
            bool(run.reasons)
            or any(
                page.quality_status != "normal" or page.rotation_status == "rotation_uncertain"
                for page in pages
            )
            or any(
                document.class_status is not DocumentClassStatus.LAWYER_CONFIRMED
                or document.boundary_status is not BoundaryStatus.CONFIRMED
                for document in documents
            )
        )
        return ProcessingStatusView(
            source=source,
            latest_run=run,
            page_outcomes=pages,
            manual_review_required=run.succeeded and requires_review,
        )

    async def get_detected_document(self, *, user_id: str, document_id: str) -> DocumentView:
        document = await self._require_document(user_id, document_id)
        return await self._document_view(user_id, document)

    async def get_document_inbox(
        self, *, user_id: str, matter_id: str, limit: int = 50, cursor: str | None = None
    ) -> DocumentInboxView:
        """The grouped queue: files, the documents inside them, and the pairs.

        Paginated over source files. A document whose fragments reach a file on
        another page is still returned whole, so a cross-file bundle is never
        shown as half a document.
        """
        sources, next_cursor = await self._repo.list_source_files(
            user_id, matter_id, limit=limit, cursor=cursor
        )
        fragments = await self._repo.list_fragments_for_matter(user_id, matter_id)
        documents = await self._repo.list_documents(user_id, matter_id)
        documents = [
            document
            for document in documents
            if document.version_relationship is not DocumentVersionRelationship.SUPERSEDED
        ]
        active_ids = {document.id for document in documents}
        fragments = [
            fragment for fragment in fragments if fragment.detected_document_id in active_ids
        ]
        duplicates = self._duplicate_map(await self._repo.source_file_hashes(user_id, matter_id))

        page_source_ids = {source.id for source in sources}
        visible = {
            fragment.detected_document_id
            for fragment in fragments
            if fragment.source_file_id in page_source_ids
        }
        by_document: dict[str, list[DocumentFragment]] = {}
        for fragment in fragments:
            by_document.setdefault(fragment.detected_document_id, []).append(fragment)

        return DocumentInboxView(
            matter_id=matter_id,
            source_files=tuple(
                self._source_view(source, fragments, duplicates) for source in sources
            ),
            documents=tuple(
                DocumentView(
                    document=document,
                    fragments=tuple(
                        sorted(
                            by_document.get(document.id, ()),
                            key=lambda fragment: (fragment.order_in_document, fragment.id),
                        )
                    ),
                )
                for document in documents
                if document.id in visible
            ),
            next_cursor=next_cursor,
            page_accounting=account_pages(
                sources, fragments, await self._repo.list_page_dispositions(user_id, matter_id)
            ),
        )

    # ── Processing (§6.2 stages 3–8) ─────────────────────────────────────────

    async def process_source_file(
        self,
        *,
        user_id: str,
        source_file_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        checkpoint: Callable[[], Awaitable[None]] | None = None,
        rollback: Callable[[], Awaitable[None]] | None = None,
        on_complete: Callable[[ProcessingRunView], Awaitable[None]] | None = None,
    ) -> ProcessingRunView:
        """Run the pipeline once and record what it actually did.

        The two state writes are deliberate: the file is ``PROCESSING`` while the
        run happens and lands on the outcome the run reports. Nothing else can
        set ``PROCESSED``, because §10.2 admits it only from ``PROCESSING``.
        """
        source = await self._source_for_update(user_id, source_file_id)
        if source.version != expected_version:
            raise PreconditionFailedError(currentVersion=source.version)
        before_state = source.state.value
        if source.state is SourceFileState.PROCESSING:
            prior = await self._repo.get_latest_run_for_source_file(
                user_id, source.matter_id, source.id
            )
            started = (prior.started_at if prior else source.updated_at).replace(tzinfo=UTC)
            if (datetime.now(tz=UTC) - started).total_seconds() > (
                PROCESSING_TIMEOUT_SECONDS + PROCESSING_RECOVERY_GRACE_SECONDS
            ):
                if prior is None or prior.outcome is not SourceFileState.PROCESSING:
                    raise DomainRuleError(
                        "The interrupted processing attempt needs operator review."
                    )
                self._fail_attempt(prior, "interrupted_attempt")
                return await self._settle_processing(
                    self._complete_processing(
                        source, prior, actor_id, correlation_id, before_state, on_complete
                    )
                )
        source.state = next_state(source.state, SourceFileEvent.PROCESSING_STARTED)
        source.failure_reason = None
        source.failure_explanation_key = None
        running = await self._repo.update_source_file(source, expected_version)

        # A new source run cannot leave an earlier interpretation authoritative,
        # including when this run fails or withholds replacement organized rows.
        existing = await self._repo.list_document_ids_for_source_file(user_id, source.id)
        for document_id in existing:
            document = await self._require_document(user_id, document_id)
            if document.version_relationship is not DocumentVersionRelationship.SUPERSEDED:
                fragments = await self._repo.list_fragments_for_document(user_id, document.id)
                await self._invalidate(document, fragments, actor_id, correlation_id)
                await self._repo.update_document(document, document.version)
                await self._repo.snapshot_interpretation(document, fragments, actor_id)

        attempt = ProcessingRun(
            id=ids.new_id(ids.PROCESSING_RUN),
            user_id=user_id,
            matter_id=running.matter_id,
            source_file_id=running.id,
            provider=self._refresh_provider,
            outcome=SourceFileState.PROCESSING,
            started_at=datetime.now(tz=UTC),
            correlation_id=correlation_id,
        )
        await self._repo.create_run(attempt)
        await self._record(
            user_id=user_id,
            matter_id=running.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_SOURCE_FILE_STATE_CHANGED,
            target_type=AuditTargetType.SOURCE_FILE,
            target_id=running.id,
            before_ref=before_state,
            after_ref=f"PROCESSING@{attempt.id}",
        )
        error: Exception | None = None
        try:
            if checkpoint:
                await self._settle_processing(checkpoint(), propagate_cancellation=True)
            async with asyncio.timeout(PROCESSING_TIMEOUT_SECONDS):
                run = await self._jobs.enqueue(source_file=running, correlation_id=correlation_id)
            run.id = attempt.id
            run.started_at = attempt.started_at
        except (TimeoutError, asyncio.CancelledError):
            if rollback:
                await self._settle_processing(rollback())
            run = attempt
            self._fail_attempt(run, "processing_deadline_or_cancellation")
        except Exception as exc:
            if rollback:
                await self._settle_processing(rollback())
            run = attempt
            self._fail_attempt(run, "processing_failed", ProcessingFailureReason.PROVIDER_ERROR)
            error = exc
        result = await self._settle_processing(
            self._complete_processing(
                running, run, actor_id, correlation_id, before_state, on_complete
            )
        )
        if error is not None:
            raise error
        return result

    @staticmethod
    async def _settle_processing(
        operation: Awaitable[_ResultT], *, propagate_cancellation: bool = False
    ) -> _ResultT:
        # Keep the request/session alive until its checkpoint finishes. Provider
        # threads only return SDK responses and never write the database.
        task = asyncio.ensure_future(operation)
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                cancelled = True
                if task.done():
                    result = task.result()
                    break
        if cancelled and propagate_cancellation:
            raise asyncio.CancelledError
        return result

    @staticmethod
    def _fail_attempt(
        run: ProcessingRun,
        detail: str,
        reason: ProcessingFailureReason = ProcessingFailureReason.TIMEOUT,
    ) -> None:
        run.outcome = SourceFileState.PROCESSING_FAILED
        run.finished_at = datetime.now(tz=UTC)
        run.failure_reason = reason
        run.failure_explanation_key = failure_explanation_key(reason)
        run.reasons = (reason.value, detail)

    async def _complete_processing(
        self,
        running: SourceFile,
        run: ProcessingRun,
        actor_id: str,
        correlation_id: str,
        before_state: str,
        on_complete: Callable[[ProcessingRunView], Awaitable[None]] | None,
    ) -> ProcessingRunView:
        user_id = running.user_id
        current = await self._source_for_update(user_id, running.id)
        latest = await self._repo.get_latest_run_for_source_file(
            user_id, running.matter_id, running.id
        )
        if (
            current.version != running.version
            or current.state is not SourceFileState.PROCESSING
            or latest is None
            or latest.id != run.id
            or latest.outcome is not SourceFileState.PROCESSING
        ):
            raise SourceFileStaleError(expectedVersion=running.version)
        running = current
        event = (
            SourceFileEvent.PROCESSING_COMPLETED
            if run.succeeded
            else SourceFileEvent.PROCESSING_FAILED
        )
        running.state = next_state(running.state, event)
        running.failure_reason = run.failure_reason
        running.failure_explanation_key = run.failure_explanation_key
        if run.succeeded and run.pages_processed:
            running.page_count = run.pages_processed
        final = await self._repo.update_source_file(running, running.version)
        await self._repo.finish_run(run)

        existing = await self._repo.list_document_ids_for_source_file(user_id, final.id)
        # A re-run never overwrites documents a lawyer may already have decided
        # on (§6.5). The run is recorded and its candidates are returned for
        # comparison, but the organised inbox is left alone.
        documents = () if existing else await self._materialise(run, final)
        if run.v1_report is not None and documents:
            await self._repo.link_v1_logical_documents(
                user_id, run.id, tuple(view.document.id for view in documents)
            )

        await self._record(
            user_id=user_id,
            matter_id=final.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_SOURCE_FILE_STATE_CHANGED,
            target_type=AuditTargetType.SOURCE_FILE,
            target_id=final.id,
            before_ref=before_state,
            after_ref=f"{final.state.value}@{run.id}",
            reason=final.failure_reason.value if final.failure_reason else None,
        )
        if run.succeeded:
            # §10.1: ingestion completing puts the evidence in front of the lawyer.
            await self._advance(
                user_id,
                final.matter_id,
                (MatterState.REVIEW_REQUIRED,),
                AuditAction.RTA_SOURCE_FILE_STATE_CHANGED,
            )
        result = ProcessingRunView(
            run=run,
            source_file=final,
            documents=documents,
            candidates_withheld=bool(existing) and bool(run.candidates),
        )
        if on_complete:
            await on_complete(result)
        return result

    async def _materialise(
        self, run: ProcessingRun, source: SourceFile
    ) -> tuple[DocumentView, ...]:
        """Turn a run's candidates into documents and fragments (§6.4 bands)."""
        now = datetime.now(tz=UTC)
        views: list[DocumentView] = []
        for index, candidate in enumerate(run.candidates):
            class_status = class_status_for(
                candidate.class_id,
                candidate.class_confidence,
                top_two_margin=candidate.class_top_two_margin,
            )
            # Below the review floor the class is not recorded at all. Keeping
            # the guess beside an UNIDENTIFIED status would let a later reader
            # treat it as a filing (§6.3).
            keeps_class = class_status is not DocumentClassStatus.UNIDENTIFIED
            document = await self._repo.create_document(
                DetectedDocument(
                    id=ids.new_id(ids.DETECTED_DOCUMENT),
                    user_id=source.user_id,
                    matter_id=source.matter_id,
                    class_status=class_status,
                    boundary_status=boundary_status_for(
                        candidate.boundary_confidence,
                        continuity_anomaly=candidate.continuity_anomaly,
                    ),
                    created_at=now,
                    updated_at=now,
                    class_id=candidate.class_id if keeps_class else None,
                    class_confidence=candidate.class_confidence if keeps_class else None,
                    language_codes=candidate.language_codes,
                    issuer=candidate.issuer,
                    extraction_state=(
                        run.v1_report.logical_documents[index].extraction_state
                        if run.v1_report and index < len(run.v1_report.logical_documents)
                        else "unavailable"
                    ),
                )
            )
            fragments = await self._repo.create_fragments(
                [
                    DocumentFragment(
                        id=ids.new_id(ids.DOCUMENT_FRAGMENT),
                        user_id=source.user_id,
                        matter_id=source.matter_id,
                        detected_document_id=document.id,
                        source_file_id=candidate.source_file_id,
                        page_start=candidate.page_start,
                        page_end=candidate.page_end,
                        order_in_document=0,
                        boundary_confidence=candidate.boundary_confidence,
                        boundary_status=boundary_status_for(
                            candidate.boundary_confidence,
                            continuity_anomaly=candidate.continuity_anomaly,
                        ),
                        created_at=now,
                    )
                ]
            )
            views.append(DocumentView(document=document, fragments=tuple(fragments)))
        return tuple(views)

    # ── Versions (§6.3) ──────────────────────────────────────────────────────

    async def supersede_source_file(
        self,
        *,
        user_id: str,
        source_file_id: str,
        replacement_source_file_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        relationship: DocumentVersionRelationship = DocumentVersionRelationship.SUPERSEDED,
        reason: str | None = None,
    ) -> SourceFileView:
        """Record that a newer file replaces this one, or may replace it.

        ``SUPERSEDED`` is the lawyer's decision: the older file moves state,
        keeps its row and its bytes, and its documents and checklist links are
        marked superseded rather than deleted. ``POSSIBLE_VERSION`` is the
        weaker claim §6.3 asks first — it flags the pair for a decision and
        changes no state at all.
        """
        source = await self._source_for_update(user_id, source_file_id)
        replacement = await self._require_source(user_id, replacement_source_file_id)
        if replacement.id == source.id or replacement.matter_id != source.matter_id:
            raise SourceFileSupersedeTargetError(
                sourceFileId=source.id, replacementSourceFileId=replacement_source_file_id
            )
        if relationship not in {
            DocumentVersionRelationship.SUPERSEDED,
            DocumentVersionRelationship.POSSIBLE_VERSION,
        }:
            raise SourceFileSupersedeTargetError(
                "A supersede decision records SUPERSEDED or POSSIBLE_VERSION.",
                relationship=relationship.value,
            )

        document_ids = await self._repo.list_document_ids_for_source_file(user_id, source.id)
        replacement_document_ids = await self._repo.list_document_ids_for_source_file(
            user_id, replacement.id
        )
        successor = replacement_document_ids[0] if replacement_document_ids else None
        before_state = source.state.value

        if relationship is DocumentVersionRelationship.POSSIBLE_VERSION:
            # Nothing moves yet, so the conditional request is honoured here
            # rather than by a write that has no fields to change.
            if source.version != expected_version:
                raise SourceFileStaleError(expectedVersion=expected_version)
            saved = source
        else:
            source.state = next_state(source.state, SourceFileEvent.LATER_VERSION_IDENTIFIED)
            source.superseded_by_source_file_id = replacement.id
            saved = await self._repo.update_source_file(source, expected_version)
            if self._fact_invalidation:
                await self._fact_invalidation.invalidate(
                    user_id=user_id,
                    matter_id=source.matter_id,
                    actor_id=actor_id,
                    change=FactEvidenceInvalidation(
                        source_file_id=source.id, reason="source-replaced"
                    ),
                    correlation_id=correlation_id,
                )
            log.info(
                "source_file.superseded",
                source_file_id=saved.id,
                before_state=before_state,
                replacement_source_file_id=replacement.id,
            )

        for document_id in document_ids:
            document = await self._repo.get_document(user_id, document_id)
            if document is None:
                continue
            fragments = await self._repo.list_fragments_for_document(user_id, document.id)
            if relationship is DocumentVersionRelationship.SUPERSEDED:
                await self._invalidate(document, fragments, actor_id, correlation_id)
            document.version_relationship = relationship
            # An earlier pointer is kept when the replacement has no documents of
            # its own yet: losing it would erase a pair a lawyer has already seen.
            document.duplicate_of_detected_document_id = (
                successor or document.duplicate_of_detected_document_id
            )
            await self._repo.update_document(document, document.version)
            if relationship is DocumentVersionRelationship.SUPERSEDED:
                await self._repo.snapshot_interpretation(document, list(fragments), actor_id)
            if relationship is DocumentVersionRelationship.SUPERSEDED and self._checklist_links:
                # The checklist keeps the link row and marks it superseded; the
                # requirement it satisfied does not silently become unsatisfied
                # without a trace (§5.4).
                await self._checklist_links.supersede_document_links(
                    user_id=user_id, detected_document_id=document_id
                )

        await self._record(
            user_id=user_id,
            matter_id=saved.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_SOURCE_FILE_STATE_CHANGED,
            target_type=AuditTargetType.SOURCE_FILE,
            target_id=saved.id,
            before_ref=before_state,
            after_ref=f"{relationship.value}->{replacement.id}",
            reason=reason,
        )
        fragments = await self._repo.list_fragments_for_matter(user_id, saved.matter_id)
        duplicates = self._duplicate_map(
            await self._repo.source_file_hashes(user_id, saved.matter_id)
        )
        return self._source_view(saved, fragments, duplicates)

    # ── Lawyer corrections (§6.5) ────────────────────────────────────────────

    async def create_group(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        ranges: Sequence[FragmentRange],
        class_id: str | None = None,
    ) -> DocumentView:
        if self._matter_lock:
            await self._matter_lock.lock(user_id, matter_id)
        if class_id is not None and get_document_class(class_id) is None:
            raise UnknownDocumentClassError(classId=class_id)
        await self._validate_ranges(user_id, matter_id, ranges)
        now = datetime.now(UTC)
        document = await self._repo.create_document(
            DetectedDocument(
                id=ids.new_id(ids.DETECTED_DOCUMENT),
                user_id=user_id,
                matter_id=matter_id,
                class_status=DocumentClassStatus.LAWYER_CONFIRMED
                if class_id and class_id != UNIDENTIFIED_DOCUMENT_CLASS_ID
                else DocumentClassStatus.UNIDENTIFIED,
                boundary_status=BoundaryStatus.CONFIRMED,
                class_id=class_id,
                extraction_state="refresh_required",
                created_at=now,
                updated_at=now,
            )
        )
        fragments = await self._repo.create_fragments(
            [
                DocumentFragment(
                    id=ids.new_id(ids.DOCUMENT_FRAGMENT),
                    user_id=user_id,
                    matter_id=matter_id,
                    detected_document_id=document.id,
                    source_file_id=item.source_file_id,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    order_in_document=item.order_in_document,
                    boundary_confidence=None,
                    boundary_status=BoundaryStatus.CONFIRMED,
                    created_at=now,
                )
                for item in ranges
            ]
        )
        await self._repo.snapshot_interpretation(document, fragments, actor_id)
        await self._record(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_DOCUMENT_BOUNDARY_DECIDED,
            target_type=AuditTargetType.DETECTED_DOCUMENT,
            target_id=document.id,
            after_ref=_describe_ranges(fragments),
        )
        return DocumentView(document, tuple(fragments))

    async def _validate_ranges(
        self,
        user_id: str,
        matter_id: str,
        ranges: Sequence[FragmentRange],
        *,
        excluded: set[str] | None = None,
    ) -> None:
        page_counts: dict[str, int | None] = {}
        for item in ranges:
            source = await self._require_source(user_id, item.source_file_id)
            if source.matter_id != matter_id:
                raise SourceFileNotFoundError()
            if source.superseded_by_source_file_id or not source.has_stored_bytes:
                raise DomainRuleError("The source is not current and readable.")
            if source.page_count is None:
                raise DomainRuleError(
                    "Establish the source page count before assigning pages.",
                    reason="PAGE_COUNT_UNKNOWN",
                )
            page_counts[source.id] = source.page_count
        validate_boundary_decision(ranges, page_counts=page_counts)
        pages = [
            (item.source_file_id, page)
            for item in ranges
            for page in range(item.page_start, item.page_end + 1)
        ]
        if len(set(pages)) != len(pages) or len({item.order_in_document for item in ranges}) != len(
            ranges
        ):
            raise DomainRuleError("A page or document position is repeated.", reason="PAGE_OVERLAP")
        documents = await self._repo.list_documents(user_id, matter_id)
        active = {
            item.id
            for item in documents
            if item.id not in (excluded or set())
            and item.version_relationship is not DocumentVersionRelationship.SUPERSEDED
        }
        claims = {
            (item.source_file_id, page)
            for item in await self._repo.list_fragments_for_matter(user_id, matter_id)
            if item.detected_document_id in active
            for page in range(item.page_start, item.page_end + 1)
        }
        claims.update(
            (item.source_file_id, item.page_number)
            for item in await self._repo.list_page_dispositions(user_id, matter_id)
            if item.disposition != "review_required"
        )
        if claims.intersection(pages):
            raise DomainRuleError(
                "A selected page is already assigned. Merge its document or clear its disposition first.",
                reason="PAGE_OVERLAP",
            )

    async def decide_page_disposition(
        self,
        *,
        user_id: str,
        source_file_id: str,
        page_number: int,
        disposition: str,
        reason: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        retire_documents: tuple[tuple[str, int], ...] = (),
    ) -> SourceFileView:
        source = await self._require_source(user_id, source_file_id)
        if self._matter_lock:
            await self._matter_lock.lock(user_id, source.matter_id)
            source = await self._require_source(user_id, source_file_id)
        if source.version != expected_version:
            raise PreconditionFailedError(currentVersion=source.version)
        if (
            source.superseded_by_source_file_id
            or not source.has_stored_bytes
            or source.page_count is None
            or not 1 <= page_number <= source.page_count
        ):
            raise DomainRuleError("The page is not in a current source with a known page count.")
        if disposition not in {"blank", "unsupported", "review_required"} or not reason.strip():
            raise DomainRuleError("A page review needs a disposition and reason.")
        retiring: dict[str, tuple[DetectedDocument, list[DocumentFragment]]] = {}
        for document_id, version in retire_documents:
            document = await self._require_document(user_id, document_id)
            fragments = await self._repo.list_fragments_for_document(user_id, document_id)
            if (
                document.matter_id != source.matter_id
                or document_id in retiring
                or document.version_relationship is DocumentVersionRelationship.SUPERSEDED
                or disposition == "review_required"
                or not fragments
                or any(
                    fragment.source_file_id != source.id
                    or fragment.page_start != page_number
                    or fragment.page_end != page_number
                    for fragment in fragments
                )
            ):
                raise DomainRuleError(
                    "Only an active group containing this single page can be retired here."
                )
            if document.version != version:
                raise DetectedDocumentStaleError(expectedVersion=version)
            retiring[document_id] = (document, fragments)
        if disposition != "review_required":
            documents = await self._repo.list_documents(user_id, source.matter_id)
            active = {
                item.id
                for item in documents
                if item.version_relationship is not DocumentVersionRelationship.SUPERSEDED
                and item.id not in retiring
            }
            if any(
                item.detected_document_id in active
                and item.source_file_id == source.id
                and item.page_start <= page_number <= item.page_end
                for item in await self._repo.list_fragments_for_matter(user_id, source.matter_id)
            ):
                raise DomainRuleError(
                    "Remove the page from its document before marking its disposition."
                )
        for document, fragments in retiring.values():
            await self._invalidate(document, fragments, actor_id, correlation_id)
            document.version_relationship = DocumentVersionRelationship.SUPERSEDED
            await self._repo.update_document(document, document.version)
            await self._repo.snapshot_interpretation(document, fragments, actor_id)
            await self._record(
                user_id=user_id,
                matter_id=source.matter_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                action=AuditAction.RTA_DOCUMENT_BOUNDARY_DECIDED,
                target_type=AuditTargetType.DETECTED_DOCUMENT,
                target_id=document.id,
                after_ref=f"retired:page:{page_number}/{disposition}",
                reason=reason,
            )
        await self._repo.create_page_disposition(
            PageDisposition(
                ids.new_id("page-decision"),
                user_id,
                source.matter_id,
                source.id,
                page_number,
                disposition,
                reason,
                actor_id,
                source.version,
                datetime.now(UTC),
            )
        )
        await self._repo.update_source_file(source, expected_version)
        await self._record(
            user_id=user_id,
            matter_id=source.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_DOCUMENT_BOUNDARY_DECIDED,
            target_type=AuditTargetType.SOURCE_FILE,
            target_id=source.id,
            after_ref=f"page:{page_number}/{disposition}",
            reason=reason,
        )
        return await self.get_source_file(user_id=user_id, source_file_id=source.id)

    async def decide_boundary(
        self,
        *,
        user_id: str,
        document_id: str,
        ranges: Sequence[FragmentRange],
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        note: str | None = None,
        retire_documents: tuple[tuple[str, int], ...] = (),
    ) -> DocumentView:
        """Replace a document's page ranges with the ones a lawyer drew.

        Source pages are never altered: the decision moves the document's claim
        over them (§6.3 "permit lawyer correction without altering source
        pages"). Ranges may name more than one file, which is how a bundle
        split across uploads is joined.
        """
        document = await self._document_for_update(user_id, document_id)
        if document.version != expected_version:
            raise DetectedDocumentStaleError(expectedVersion=expected_version)
        retired: list[DetectedDocument] = []
        for retired_id, version in retire_documents:
            other = await self._require_document(user_id, retired_id)
            if other.matter_id != document.matter_id or other.id == document.id:
                raise DetectedDocumentNotFoundError()
            if (
                other.version != version
                or other.version_relationship is DocumentVersionRelationship.SUPERSEDED
            ):
                raise DetectedDocumentStaleError(expectedVersion=version)
            retired.append(other)
        if len({item.id for item in retired}) != len(retired):
            raise DomainRuleError("A merged document was repeated.")
        await self._validate_ranges(
            user_id,
            document.matter_id,
            ranges,
            excluded={document.id, *(item.id for item in retired)},
        )

        previous = await self._repo.list_fragments_for_document(user_id, document.id)
        if _range_signature(previous) != _range_signature(ranges):
            await self._invalidate(document, previous, actor_id, correlation_id)
        now = datetime.now(tz=UTC)
        await self._repo.replace_fragments(
            user_id,
            document.id,
            [
                DocumentFragment(
                    id=ids.new_id(ids.DOCUMENT_FRAGMENT),
                    user_id=user_id,
                    matter_id=document.matter_id,
                    detected_document_id=document.id,
                    source_file_id=fragment_range.source_file_id,
                    page_start=fragment_range.page_start,
                    page_end=fragment_range.page_end,
                    order_in_document=fragment_range.order_in_document,
                    # A human drew this range, so it carries no model score.
                    boundary_confidence=None,
                    boundary_status=BoundaryStatus.CONFIRMED,
                    created_at=now,
                )
                for fragment_range in ranges
            ],
        )
        document.boundary_status = BoundaryStatus.CONFIRMED
        saved = await self._repo.update_document(document, expected_version)
        for other in retired:
            await self._invalidate(
                other,
                await self._repo.list_fragments_for_document(user_id, other.id),
                actor_id,
                correlation_id,
            )
            other.version_relationship = DocumentVersionRelationship.SUPERSEDED
            other.duplicate_of_detected_document_id = document.id
            await self._repo.update_document(other, other.version)
            await self._record(
                user_id=user_id,
                matter_id=document.matter_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                action=AuditAction.RTA_DOCUMENT_BOUNDARY_DECIDED,
                target_type=AuditTargetType.DETECTED_DOCUMENT,
                target_id=other.id,
                after_ref=f"merged-into:{document.id}",
                reason=note,
            )
        await self._repo.snapshot_interpretation(
            saved, await self._repo.list_fragments_for_document(user_id, saved.id), actor_id
        )
        await self._record(
            user_id=user_id,
            matter_id=saved.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_DOCUMENT_BOUNDARY_DECIDED,
            target_type=AuditTargetType.DETECTED_DOCUMENT,
            target_id=saved.id,
            before_ref=_describe_ranges(previous),
            after_ref=_describe_ranges(
                await self._repo.list_fragments_for_document(user_id, saved.id)
            ),
            reason=note,
        )
        await self._advance_if_documents_decided(
            user_id, saved.matter_id, AuditAction.RTA_DOCUMENT_BOUNDARY_DECIDED
        )
        return await self._document_view(user_id, saved)

    async def decide_classification(
        self,
        *,
        user_id: str,
        document_id: str,
        class_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        note: str | None = None,
    ) -> DocumentView:
        """Confirm or correct the controlled class of one document.

        Only ids in the current rule pack are accepted (§12.4): there is no
        free-text class, and ``UNIDENTIFIED`` stays available as a real answer
        rather than being resolved to the nearest plausible class.
        """
        document = await self._document_for_update(user_id, document_id)
        if document.version != expected_version:
            raise DetectedDocumentStaleError(expectedVersion=expected_version)
        if get_document_class(class_id) is None:
            raise UnknownDocumentClassError(classId=class_id)

        before = f"{document.class_id or '-'}/{document.class_status.value}"
        if class_id != document.class_id:
            await self._invalidate(
                document,
                await self._repo.list_fragments_for_document(user_id, document.id),
                actor_id,
                correlation_id,
            )
            # The stored score measured the class it was produced for. Carrying
            # it over to a class the lawyer chose would attribute a model's
            # confidence to a human's decision.
            document.class_confidence = None
        document.class_id = class_id
        document.class_status = (
            DocumentClassStatus.UNIDENTIFIED
            if class_id == UNIDENTIFIED_DOCUMENT_CLASS_ID
            else DocumentClassStatus.LAWYER_CONFIRMED
        )
        saved = await self._repo.update_document(document, expected_version)
        await self._repo.snapshot_interpretation(
            saved, await self._repo.list_fragments_for_document(user_id, saved.id), actor_id
        )
        await self._record(
            user_id=user_id,
            matter_id=saved.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_DOCUMENT_CLASSIFIED,
            target_type=AuditTargetType.DETECTED_DOCUMENT,
            target_id=saved.id,
            before_ref=before,
            after_ref=f"{saved.class_id}/{saved.class_status.value}",
            reason=note,
        )
        await self._advance_if_documents_decided(
            user_id, saved.matter_id, AuditAction.RTA_DOCUMENT_CLASSIFIED
        )
        return await self._document_view(user_id, saved)

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def refresh_extraction(
        self,
        *,
        user_id: str,
        document_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
    ) -> DocumentView:
        document = await self._document_for_update(user_id, document_id)
        if document.version != expected_version:
            raise DetectedDocumentStaleError(expectedVersion=expected_version)
        if document.version_relationship is DocumentVersionRelationship.SUPERSEDED:
            raise DomainRuleError("The document has been superseded.")
        fragments = await self._repo.list_fragments_for_document(user_id, document_id)
        if not fragments or document.boundary_status is not BoundaryStatus.CONFIRMED:
            raise DomainRuleError("Confirm the document's pages before refreshing extraction.")
        if document.class_status is not DocumentClassStatus.LAWYER_CONFIRMED:
            raise DomainRuleError("Confirm the document type before refreshing extraction.")
        if document.extraction_state == "current" and document.latest_refresh_run_id:
            return await self._document_view(user_id, document)
        # Existing generation-one candidates may be explicitly refreshed once;
        # their interpretation becomes historical before any provider call.
        if document.latest_refresh_run_id is None and document.extraction_state in {
            "current",
            "unavailable",
            "failed",
            "unsupported",
        }:
            await self._invalidate(document, fragments, actor_id, correlation_id)
            await self._repo.snapshot_interpretation(document, fragments, actor_id)
        run = ProcessingRun(
            id=ids.new_id(ids.PROCESSING_RUN),
            user_id=user_id,
            matter_id=document.matter_id,
            source_file_id=fragments[0].source_file_id,
            provider=self._refresh_provider,
            outcome=SourceFileState.PROCESSING_FAILED,
            started_at=datetime.now(UTC),
            correlation_id=correlation_id,
        )
        pages: list[InterpretationPage] = []
        run.kind = "interpretation"
        run.detected_document_id = document.id
        run.interpretation_generation = document.interpretation_generation
        candidates: tuple[ExtractedCandidate, ...] = ()
        try:
            if self._refresh_extractor is None or self._matter_document_types is None:
                raise DomainRuleError("Extraction is unavailable.", reason="NOT_CONFIGURED")
            if not self._refresh_data_approved:
                raise DomainRuleError(
                    "The provider data gate is closed.", reason="DATA_PROTECTION_GATE"
                )
            types = await self._matter_document_types.for_matter(
                user_id=user_id, matter_id=document.matter_id
            )
            fields = types.extraction_schemas.get(document.class_id or "", ())
            if not fields:
                raise DomainRuleError(
                    "This type requires manual review.", reason="UNSUPPORTED_TYPE"
                )
            text: list[str] = []
            checked: set[str] = set()
            for fragment in sorted(fragments, key=lambda item: item.order_in_document):
                source = await self._require_source(user_id, fragment.source_file_id)
                if (
                    source.matter_id != document.matter_id
                    or source.state is not SourceFileState.PROCESSED
                    or source.superseded_by_source_file_id
                    or source.page_count is None
                    or fragment.page_end > source.page_count
                ):
                    raise DomainRuleError(
                        "The cached source is not current.", reason="SOURCE_NOT_CURRENT"
                    )
                if source.id not in checked:
                    original = await self._storage.get(
                        source.storage_object_key, version=source.storage_object_version
                    )
                    if hashlib.sha256(original).hexdigest() != source.sha256:
                        raise SourceObjectIntegrityError()
                    checked.add(source.id)
                for number in range(fragment.page_start, fragment.page_end + 1):
                    page = await self._repo.cached_interpretation_page(
                        user_id, document.matter_id, source.id, number
                    )
                    if page is None or page.quality_status in {"ocr_failed", "likely_blank"}:
                        raise DomainRuleError(
                            "A page needs manual review.", reason="PAGE_REVIEW_REQUIRED"
                        )
                    await self._storage.get(page.image_ref[0], version=page.image_ref[1])
                    page_text = (
                        await self._storage.get(page.text_ref[0], version=page.text_ref[1])
                    ).decode("utf-8")
                    if not page_text.strip():
                        raise DomainRuleError(
                            "Cached OCR is unavailable.", reason="OCR_UNAVAILABLE"
                        )
                    pages.append(page)
                    text.append(f"[Page {len(pages)}]\n{page_text}")
            candidates = await self._refresh_extractor.extract_document(
                type_id=document.class_id or "",
                text="\n\n".join(text),
                page_numbers=tuple(range(1, len(pages) + 1)),
                fields=fields,
            )
            keys = {field.key for field in fields}
            if any(c.key not in keys or not 1 <= c.page_no <= len(pages) for c in candidates):
                raise ExtractionProviderError()
            run.outcome = SourceFileState.PROCESSED
            run.pages_processed = len(pages)
            run.ai_extraction_calls = 1
            document.extraction_state = "current"
        except (DraftlyError, OSError, ValueError, KeyError) as exc:
            reason = (
                str(exc.details.get("reason", exc.code))
                if isinstance(exc, DraftlyError)
                else "CACHE_UNAVAILABLE"
            )
            run.reasons = (reason,)
            document.extraction_state = "unsupported" if reason == "UNSUPPORTED_TYPE" else "failed"
        run.finished_at = datetime.now(UTC)
        await self._repo.create_run(run)
        if run.succeeded:
            await self._repo.create_interpretation_extraction(document, run, pages, candidates)
        document.latest_refresh_run_id = run.id
        document.refresh_failure_reason = run.reasons[0] if run.reasons else None
        saved = await self._repo.update_document(document, expected_version)
        await self._record(
            user_id=user_id,
            matter_id=document.matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_DOCUMENT_CLASSIFIED,
            target_type=AuditTargetType.DETECTED_DOCUMENT,
            target_id=document.id,
            after_ref=f"generation:{document.interpretation_generation}/refresh:{run.id}/{document.extraction_state}",
        )
        return await self._document_view(user_id, saved)

    async def _document_for_update(self, user_id: str, document_id: str) -> DetectedDocument:
        document = await self._require_document(user_id, document_id)
        if self._matter_lock:
            await self._matter_lock.lock(user_id, document.matter_id)
            document = await self._require_document(user_id, document_id)
        return document

    async def _source_for_update(self, user_id: str, source_file_id: str) -> SourceFile:
        source = await self._require_source(user_id, source_file_id)
        if self._matter_lock:
            await self._matter_lock.lock(user_id, source.matter_id)
            source = await self._require_source(user_id, source_file_id)
        return source

    async def interpretation_history(self, user_id: str, document_id: str) -> InterpretationHistory:
        document = await self._require_document(user_id, document_id)
        return await self._repo.interpretation_history(document)

    async def _invalidate(
        self,
        document: DetectedDocument,
        fragments: Sequence[DocumentFragment],
        actor_id: str,
        correlation_id: str,
    ) -> None:
        await self._repo.snapshot_interpretation(document, list(fragments), None)
        document.interpretation_generation += 1
        document.extraction_state = "refresh_required"
        document.latest_refresh_run_id = None
        document.refresh_failure_reason = None
        if self._fact_invalidation:
            await self._fact_invalidation.invalidate(
                user_id=document.user_id,
                matter_id=document.matter_id,
                actor_id=actor_id,
                change=FactEvidenceInvalidation(
                    source_file_id=fragments[0].source_file_id if fragments else "",
                    detected_document_ids=(document.id,),
                ),
                correlation_id=correlation_id,
            )

    async def _advance(
        self,
        user_id: str,
        matter_id: str,
        states: tuple[MatterState, ...],
        reason: AuditAction,
    ) -> None:
        """Ask the matter to move through ``states`` in order; it refuses any step it does not allow."""
        if self._matter_workflow is None:
            return
        for state in states:
            await self._matter_workflow.advance_state(
                user_id=user_id, matter_id=matter_id, state=state, reason=reason.value
            )

    async def _advance_if_documents_decided(
        self, user_id: str, matter_id: str, reason: AuditAction
    ) -> None:
        """§10.1 REVIEW_REQUIRED -> LEGAL_REVIEW once no boundary or class task is open."""
        if self._matter_workflow is None:
            return
        inbox = await self.get_document_inbox(user_id=user_id, matter_id=matter_id, limit=500)
        if (
            inbox.documents
            and inbox.next_cursor is None
            and all(not page.manual_review_required for page in inbox.page_accounting)
            and all(view.document.extraction_state == "current" for view in inbox.documents)
            and not inbox.boundary_review_document_ids
            and not inbox.classification_review_document_ids
            and not inbox.unidentified_document_ids
            and not inbox.unprocessed_source_file_ids
        ):
            await self._advance(
                user_id,
                matter_id,
                (MatterState.REVIEW_REQUIRED, MatterState.LEGAL_REVIEW),
                reason,
            )

    async def _require_source(self, user_id: str, source_file_id: str) -> SourceFile:
        source = await self._repo.get_source_file(user_id, source_file_id)
        if source is None:
            raise SourceFileNotFoundError()
        return source

    async def _require_document(self, user_id: str, document_id: str) -> DetectedDocument:
        document = await self._repo.get_document(user_id, document_id)
        if document is None:
            raise DetectedDocumentNotFoundError()
        return document

    async def _document_view(self, user_id: str, document: DetectedDocument) -> DocumentView:
        fragments = await self._repo.list_fragments_for_document(user_id, document.id)
        return DocumentView(document=document, fragments=tuple(fragments))

    def _source_view(
        self,
        source: SourceFile,
        fragments: Sequence[DocumentFragment],
        duplicates: dict[str, str],
    ) -> SourceFileView:
        document_ids: list[str] = []
        for fragment in fragments:
            if fragment.source_file_id == source.id and (
                fragment.detected_document_id not in document_ids
            ):
                document_ids.append(fragment.detected_document_id)
        duplicate_of = duplicates.get(source.id)
        return SourceFileView(
            source_file=source,
            detected_document_ids=tuple(document_ids),
            contains_multiple_documents=source_contains_multiple_documents(
                fragments, source_file_id=source.id
            ),
            duplicate_of_source_file_id=duplicate_of,
            version_relationship=(
                DocumentVersionRelationship.EXACT_DUPLICATE if duplicate_of else None
            ),
        )

    @staticmethod
    def _duplicate_map(hashes: Sequence[tuple[str, str]]) -> dict[str, str]:
        """Map each repeated upload to the copy of the same bytes that came first."""
        first_seen: dict[str, str] = {}
        duplicates: dict[str, str] = {}
        for source_file_id, sha256 in hashes:
            original = first_seen.setdefault(sha256, source_file_id)
            if original != source_file_id:
                duplicates[source_file_id] = original
        return duplicates

    async def _record(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        action: AuditAction,
        target_type: AuditTargetType,
        target_id: str,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=action.value,
                target_type=target_type.value,
                target_id=target_id,
                before_ref=before_ref,
                after_ref=after_ref,
                reason=reason,
                correlation_id=correlation_id,
            )
        )


def _range_signature(
    fragments: Sequence[DocumentFragment | FragmentRange],
) -> tuple[tuple[str, int], ...]:
    return tuple(
        (f.source_file_id, page)
        for f in sorted(fragments, key=lambda item: item.order_in_document)
        for page in range(f.page_start, f.page_end + 1)
    )


def _describe_ranges(fragments: Sequence[DocumentFragment]) -> str:
    """Compact page-range description for the audit trail's before/after refs."""
    return (
        ";".join(
            f"{fragment.source_file_id}:{fragment.page_start}-{fragment.page_end}"
            for fragment in sorted(fragments, key=lambda f: (f.order_in_document, f.id))
        )
        or "-"
    )

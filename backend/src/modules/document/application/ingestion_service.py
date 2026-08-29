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

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import (
    UNIDENTIFIED_DOCUMENT_CLASS_ID,
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    ProcessingFailureReason,
    SourceFileState,
    get_document_class,
)
from src.modules.document.domain.errors import (
    DetectedDocumentNotFoundError,
    SourceFileNotFoundError,
    SourceFileStaleError,
    SourceFileSupersedeTargetError,
    SourceFileTooLargeError,
    UnknownDocumentClassError,
)
from src.modules.document.domain.ingestion import (
    DEFAULT_RETENTION_CLASS,
    DetectedDocument,
    DocumentFragment,
    FragmentRange,
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
from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository
from src.modules.document.ports import ProcessingJobPort, SourceFileStoragePort
from src.modules.task.contracts import ChecklistLinkCommandPort
from src.platform import ids

log = structlog.get_logger(__name__)


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
class DocumentInboxView:
    """The grouped review queue for one matter (§11.1 Document Inbox)."""

    matter_id: str
    source_files: tuple[SourceFileView, ...]
    documents: tuple[DocumentView, ...]
    next_cursor: str | None = None

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
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._jobs = jobs
        self._audit = audit
        self._max_upload_bytes = max_upload_bytes
        self._max_page_count = max_page_count
        self._checklist_links = checklist_links

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
    ) -> ProcessingRunView:
        """Run the pipeline once and record what it actually did.

        The two state writes are deliberate: the file is ``PROCESSING`` while the
        run happens and lands on the outcome the run reports. Nothing else can
        set ``PROCESSED``, because §10.2 admits it only from ``PROCESSING``.
        """
        source = await self._require_source(user_id, source_file_id)
        before_state = source.state.value
        source.state = next_state(source.state, SourceFileEvent.PROCESSING_STARTED)
        running = await self._repo.update_source_file(source, expected_version)

        run = await self._jobs.enqueue(source_file=running, correlation_id=correlation_id)
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
        await self._repo.create_run(run)

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
        return ProcessingRunView(
            run=run,
            source_file=final,
            documents=documents,
            candidates_withheld=bool(existing) and bool(run.candidates),
        )

    async def _materialise(
        self, run: ProcessingRun, source: SourceFile
    ) -> tuple[DocumentView, ...]:
        """Turn a run's candidates into documents and fragments (§6.4 bands)."""
        now = datetime.now(tz=UTC)
        views: list[DocumentView] = []
        for candidate in run.candidates:
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
        source = await self._require_source(user_id, source_file_id)
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
            document.version_relationship = relationship
            # An earlier pointer is kept when the replacement has no documents of
            # its own yet: losing it would erase a pair a lawyer has already seen.
            document.duplicate_of_detected_document_id = (
                successor or document.duplicate_of_detected_document_id
            )
            await self._repo.update_document(document, document.version)
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
    ) -> DocumentView:
        """Replace a document's page ranges with the ones a lawyer drew.

        Source pages are never altered: the decision moves the document's claim
        over them (§6.3 "permit lawyer correction without altering source
        pages"). Ranges may name more than one file, which is how a bundle
        split across uploads is joined.
        """
        document = await self._require_document(user_id, document_id)
        page_counts: dict[str, int | None] = {}
        for fragment_range in ranges:
            source = await self._repo.get_source_file(user_id, fragment_range.source_file_id)
            if source is None or source.matter_id != document.matter_id:
                raise SourceFileNotFoundError()
            page_counts[source.id] = source.page_count
        validate_boundary_decision(ranges, page_counts=page_counts)

        previous = await self._repo.list_fragments_for_document(user_id, document.id)
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
        document = await self._require_document(user_id, document_id)
        if get_document_class(class_id) is None:
            raise UnknownDocumentClassError(classId=class_id)

        before = f"{document.class_id or '-'}/{document.class_status.value}"
        if class_id != document.class_id:
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
        return await self._document_view(user_id, saved)

    # ── Helpers ──────────────────────────────────────────────────────────────

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


def _describe_ranges(fragments: Sequence[DocumentFragment]) -> str:
    """Compact page-range description for the audit trail's before/after refs."""
    return (
        ";".join(
            f"{fragment.source_file_id}:{fragment.page_start}-{fragment.page_end}"
            for fragment in sorted(fragments, key=lambda f: (f.order_in_document, f.id))
        )
        or "-"
    )

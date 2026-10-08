"""SQLAlchemy repositories for source files, detected documents, and runs.

Every method takes ``user_id`` and every query filters on it first (plan §5.3
invariant 10). There is no read path that resolves a row by id alone, so a
leaked identifier cannot reach another account's evidence.

There is no delete method for a source file. Superseding sets a pointer and a
state; the row and its bytes stay (§6.3).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    ProcessingFailureReason,
    SourceFileState,
)
from src.modules.document.domain.errors import (
    CandidateAlreadyApprovedError,
    CandidateFieldStaleError,
    DetectedDocumentStaleError,
    DocumentReviewNotFoundError,
    SourceFileStaleError,
)
from src.modules.document.domain.ingestion import (
    DetectedDocument,
    DocumentFragment,
    ProcessingPageOutcome,
    ProcessingRun,
    SourceFile,
)
from src.modules.document.domain.ingestion_policies import failure_explanation_key
from src.modules.document.domain.registry import observational_field_key
from src.modules.document.domain.v1 import (
    DocumentReview,
    ProcessedLogicalDocument,
    ReviewCandidate,
    ReviewPage,
)
from src.modules.document.infrastructure.orm import (
    DetectedDocumentRow,
    DocumentFragmentRow,
    DocumentProcessingPageRow,
    ProcessingCandidateFieldRow,
    ProcessingLogicalDocumentRow,
    SourceFileProcessingRunRow,
    SourceFileRow,
)
from src.modules.verification.contracts import CandidateApprovalInput
from src.platform import ids
from src.platform.pagination import Cursor, decode_cursor, encode_cursor


def _to_source_file(row: SourceFileRow) -> SourceFile:
    return SourceFile(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        original_filename=row.original_filename,
        media_type=row.media_type,
        byte_length=row.byte_length,
        sha256=row.sha256,
        storage_object_key=row.storage_object_key,
        storage_object_version=row.storage_object_version,
        upload_actor_id=row.upload_actor_id,
        state=SourceFileState(row.state),
        retention_class=row.retention_class,
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
        page_count=row.page_count,
        detected_languages=tuple(row.detected_languages),
        failure_reason=(
            ProcessingFailureReason(row.failure_reason) if row.failure_reason else None
        ),
        failure_explanation_key=row.failure_explanation_key,
        superseded_by_source_file_id=row.superseded_by_source_file_id,
        derived_from_source_file_id=row.derived_from_source_file_id,
    )


def _apply_source_file(row: SourceFileRow, source: SourceFile) -> None:
    """Only the mutable columns. Bytes, hash, and filename are never rewritten."""
    row.state = source.state.value
    row.page_count = source.page_count
    row.detected_languages = list(source.detected_languages)
    row.failure_reason = source.failure_reason.value if source.failure_reason else None
    row.failure_explanation_key = source.failure_explanation_key
    row.superseded_by_source_file_id = source.superseded_by_source_file_id


def _to_document(row: DetectedDocumentRow) -> DetectedDocument:
    return DetectedDocument(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        class_status=DocumentClassStatus(row.class_status),
        boundary_status=BoundaryStatus(row.boundary_status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
        class_id=row.class_id,
        class_confidence=row.class_confidence,
        language_codes=tuple(row.language_codes),
        issuer=row.issuer,
        issue_or_execution_date_fact_id=row.issue_or_execution_date_fact_id,
        version_relationship=(
            DocumentVersionRelationship(row.version_relationship)
            if row.version_relationship
            else None
        ),
        duplicate_of_detected_document_id=row.duplicate_of_detected_document_id,
    )


def _apply_document(row: DetectedDocumentRow, document: DetectedDocument) -> None:
    row.class_id = document.class_id
    row.class_confidence = document.class_confidence
    row.class_status = document.class_status.value
    row.language_codes = list(document.language_codes)
    row.issuer = document.issuer
    row.issue_or_execution_date_fact_id = document.issue_or_execution_date_fact_id
    row.version_relationship = (
        document.version_relationship.value if document.version_relationship else None
    )
    row.duplicate_of_detected_document_id = document.duplicate_of_detected_document_id
    row.boundary_status = document.boundary_status.value


def _to_fragment(row: DocumentFragmentRow) -> DocumentFragment:
    return DocumentFragment(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        detected_document_id=row.detected_document_id,
        source_file_id=row.source_file_id,
        page_start=row.page_start,
        page_end=row.page_end,
        order_in_document=row.order_in_document,
        boundary_confidence=row.boundary_confidence,
        boundary_status=BoundaryStatus(row.boundary_status),
        created_at=row.created_at,
    )


def _encode_cursor(created_at: datetime, record_id: str) -> str:
    return encode_cursor(Cursor(created_at=created_at, id=record_id))


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """The keyset position, or InvalidCursorError (400) for a forged or bad cursor."""
    decoded = decode_cursor(cursor)
    return (decoded.created_at, decoded.id) if decoded is not None else None


class SqlDocumentIngestionRepository:
    """Source files, detected documents, fragments, and runs for one session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Source files ─────────────────────────────────────────────────────────

    async def create_source_file(self, source: SourceFile) -> SourceFile:
        row = SourceFileRow(
            id=source.id,
            user_id=source.user_id,
            matter_id=source.matter_id,
            original_filename=source.original_filename,
            media_type=source.media_type,
            byte_length=source.byte_length,
            sha256=source.sha256,
            storage_object_key=source.storage_object_key,
            storage_object_version=source.storage_object_version,
            upload_actor_id=source.upload_actor_id,
            state=source.state.value,
            page_count=source.page_count,
            detected_languages=list(source.detected_languages),
            retention_class=source.retention_class,
            failure_reason=source.failure_reason.value if source.failure_reason else None,
            failure_explanation_key=source.failure_explanation_key,
            superseded_by_source_file_id=source.superseded_by_source_file_id,
            derived_from_source_file_id=source.derived_from_source_file_id,
            created_at=source.created_at,
            updated_at=source.updated_at,
            version=source.version,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_source_file(row)

    async def get_source_file(self, user_id: str, source_file_id: str) -> SourceFile | None:
        row = await self._source_row(user_id, source_file_id)
        return _to_source_file(row) if row is not None else None

    async def _source_row(self, user_id: str, source_file_id: str) -> SourceFileRow | None:
        result = await self._session.execute(
            select(SourceFileRow).where(
                SourceFileRow.user_id == user_id, SourceFileRow.id == source_file_id
            )
        )
        return result.scalar_one_or_none()

    async def list_source_files(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None = None
    ) -> tuple[list[SourceFile], str | None]:
        query = select(SourceFileRow).where(
            SourceFileRow.user_id == user_id, SourceFileRow.matter_id == matter_id
        )
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            # Keyset pagination: offset double-counts while an upload lands
            # (api-conventions §2).
            query = query.where(
                (SourceFileRow.created_at < created_at)
                | ((SourceFileRow.created_at == created_at) & (SourceFileRow.id < last_id))
            )
        query = query.order_by(SourceFileRow.created_at.desc(), SourceFileRow.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_source_file(row) for row in rows], next_cursor

    async def list_source_files_by_sha256(
        self, user_id: str, matter_id: str, sha256: str
    ) -> list[SourceFile]:
        """Everything in this matter with the same bytes — the §6.3 duplicate probe."""
        result = await self._session.execute(
            select(SourceFileRow)
            .where(
                SourceFileRow.user_id == user_id,
                SourceFileRow.matter_id == matter_id,
                SourceFileRow.sha256 == sha256,
            )
            .order_by(SourceFileRow.created_at.asc(), SourceFileRow.id.asc())
        )
        return [_to_source_file(row) for row in result.scalars().all()]

    async def source_file_hashes(self, user_id: str, matter_id: str) -> list[tuple[str, str]]:
        """``(source_file_id, sha256)`` for the matter, oldest first.

        A narrow projection rather than whole rows: the inbox needs only enough
        to point a duplicate at the copy that arrived first.
        """
        result = await self._session.execute(
            select(SourceFileRow.id, SourceFileRow.sha256)
            .where(SourceFileRow.user_id == user_id, SourceFileRow.matter_id == matter_id)
            .where(SourceFileRow.state != SourceFileState.REJECTED.value)
            .order_by(SourceFileRow.created_at.asc(), SourceFileRow.id.asc())
        )
        return [(row_id, sha) for row_id, sha in result.all()]

    async def update_source_file(self, source: SourceFile, expected_version: int) -> SourceFile:
        result = await self._session.execute(
            update(SourceFileRow)
            .where(
                SourceFileRow.id == source.id,
                SourceFileRow.user_id == source.user_id,
                SourceFileRow.version == expected_version,
            )
            .values(version=expected_version + 1)
            .returning(SourceFileRow.id)
        )
        if result.scalar_one_or_none() is None:
            raise SourceFileStaleError(expectedVersion=expected_version)
        row = await self._source_row(source.user_id, source.id)
        if row is None:
            raise SourceFileStaleError(expectedVersion=expected_version)
        _apply_source_file(row, source)
        row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return _to_source_file(row)

    # ── Detected documents ───────────────────────────────────────────────────

    async def create_document(self, document: DetectedDocument) -> DetectedDocument:
        row = DetectedDocumentRow(
            id=document.id,
            user_id=document.user_id,
            matter_id=document.matter_id,
            class_id=document.class_id,
            class_confidence=document.class_confidence,
            class_status=document.class_status.value,
            language_codes=list(document.language_codes),
            issuer=document.issuer,
            issue_or_execution_date_fact_id=document.issue_or_execution_date_fact_id,
            version_relationship=(
                document.version_relationship.value if document.version_relationship else None
            ),
            duplicate_of_detected_document_id=document.duplicate_of_detected_document_id,
            boundary_status=document.boundary_status.value,
            created_at=document.created_at,
            updated_at=document.updated_at,
            version=document.version,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_document(row)

    async def get_document(self, user_id: str, document_id: str) -> DetectedDocument | None:
        row = await self._document_row(user_id, document_id)
        return _to_document(row) if row is not None else None

    async def _document_row(self, user_id: str, document_id: str) -> DetectedDocumentRow | None:
        result = await self._session.execute(
            select(DetectedDocumentRow).where(
                DetectedDocumentRow.user_id == user_id, DetectedDocumentRow.id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def list_documents(self, user_id: str, matter_id: str) -> list[DetectedDocument]:
        result = await self._session.execute(
            select(DetectedDocumentRow)
            .where(
                DetectedDocumentRow.user_id == user_id,
                DetectedDocumentRow.matter_id == matter_id,
            )
            .order_by(DetectedDocumentRow.created_at.asc(), DetectedDocumentRow.id.asc())
        )
        return [_to_document(row) for row in result.scalars().all()]

    async def update_document(
        self, document: DetectedDocument, expected_version: int
    ) -> DetectedDocument:
        result = await self._session.execute(
            update(DetectedDocumentRow)
            .where(
                DetectedDocumentRow.id == document.id,
                DetectedDocumentRow.user_id == document.user_id,
                DetectedDocumentRow.version == expected_version,
            )
            .values(version=expected_version + 1)
            .returning(DetectedDocumentRow.id)
        )
        if result.scalar_one_or_none() is None:
            raise DetectedDocumentStaleError(expectedVersion=expected_version)
        row = await self._document_row(document.user_id, document.id)
        if row is None:
            raise DetectedDocumentStaleError(expectedVersion=expected_version)
        _apply_document(row, document)
        row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return _to_document(row)

    # ── Fragments ────────────────────────────────────────────────────────────

    async def create_fragments(self, fragments: list[DocumentFragment]) -> list[DocumentFragment]:
        rows = []
        for fragment in fragments:
            row = DocumentFragmentRow(
                id=fragment.id,
                user_id=fragment.user_id,
                matter_id=fragment.matter_id,
                detected_document_id=fragment.detected_document_id,
                source_file_id=fragment.source_file_id,
                page_start=fragment.page_start,
                page_end=fragment.page_end,
                order_in_document=fragment.order_in_document,
                boundary_confidence=fragment.boundary_confidence,
                boundary_status=fragment.boundary_status.value,
                created_at=fragment.created_at,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return [_to_fragment(row) for row in rows]

    async def list_fragments_for_matter(
        self, user_id: str, matter_id: str
    ) -> list[DocumentFragment]:
        result = await self._session.execute(
            select(DocumentFragmentRow)
            .where(
                DocumentFragmentRow.user_id == user_id,
                DocumentFragmentRow.matter_id == matter_id,
            )
            .order_by(
                DocumentFragmentRow.detected_document_id.asc(),
                DocumentFragmentRow.order_in_document.asc(),
            )
        )
        return [_to_fragment(row) for row in result.scalars().all()]

    async def list_fragments_for_document(
        self, user_id: str, document_id: str
    ) -> list[DocumentFragment]:
        result = await self._session.execute(
            select(DocumentFragmentRow)
            .where(
                DocumentFragmentRow.user_id == user_id,
                DocumentFragmentRow.detected_document_id == document_id,
            )
            .order_by(DocumentFragmentRow.order_in_document.asc())
        )
        return [_to_fragment(row) for row in result.scalars().all()]

    async def list_document_ids_for_source_file(
        self, user_id: str, source_file_id: str
    ) -> list[str]:
        result = await self._session.execute(
            select(DocumentFragmentRow.detected_document_id)
            .where(
                DocumentFragmentRow.user_id == user_id,
                DocumentFragmentRow.source_file_id == source_file_id,
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def replace_fragments(
        self, user_id: str, document_id: str, fragments: list[DocumentFragment]
    ) -> list[DocumentFragment]:
        """Swap a document's fragment set for the one a lawyer drew (§6.5).

        The ranges that go are recorded in the audit event by the caller before
        this runs, so the previous split stays reconstructible. Nothing about
        the source files is touched.
        """
        await self._session.execute(
            delete(DocumentFragmentRow).where(
                DocumentFragmentRow.user_id == user_id,
                DocumentFragmentRow.detected_document_id == document_id,
            )
        )
        await self._session.flush()
        return await self.create_fragments(fragments)

    # ── Processing runs ──────────────────────────────────────────────────────

    async def create_run(self, run: ProcessingRun) -> ProcessingRun:
        row = SourceFileProcessingRunRow(
            id=run.id,
            user_id=run.user_id,
            matter_id=run.matter_id,
            source_file_id=run.source_file_id,
            provider=run.provider,
            outcome=run.outcome.value,
            reasons=list(run.reasons),
            pages_processed=run.pages_processed,
            ai_extraction_calls=run.ai_extraction_calls,
            started_at=run.started_at,
            finished_at=run.finished_at,
            correlation_id=run.correlation_id,
        )
        self._session.add(row)
        # SQLAlchemy cannot infer insert ordering here because the V1 child
        # rows are built from domain objects rather than ORM relationships.
        # Materialise the FK parent before adding pages/groups/candidates.
        await self._session.flush()
        if run.v1_report is not None:
            await self._add_v1_details(run)
        await self._session.flush()
        return run

    async def _add_v1_details(self, run: ProcessingRun) -> None:
        assert run.v1_report is not None
        for page in run.v1_report.pages:
            classification = page.classification
            assert classification is not None
            webp = page.derivative_refs["corrected_webp"]
            ocr = page.derivative_refs["corrected_ocr_json"]
            text = page.derivative_refs["plain_ocr_text"]
            self._session.add(
                DocumentProcessingPageRow(
                    id=ids.new_id(ids.PROCESSING_PAGE),
                    user_id=run.user_id,
                    matter_id=run.matter_id,
                    processing_run_id=run.id,
                    source_file_id=run.source_file_id,
                    page_no=page.page_no,
                    quality_status=page.quality_status.value,
                    original_width=page.original_width,
                    original_height=page.original_height,
                    corrected_width=page.corrected_width,
                    corrected_height=page.corrected_height,
                    detected_orientation=page.rotation.detected_orientation,
                    correction_degrees=page.rotation.correction_applied,
                    rotation_status=page.rotation.status.value,
                    rotation_vote_share=page.rotation.vote_share,
                    usable_word_count=page.rotation.usable_word_count,
                    detected_languages=[
                        {"code": item.code, "confidence": item.confidence}
                        for item in page.ocr.detected_languages
                    ],
                    classification_type_id=classification.type_id,
                    suggested_name=classification.suggested_name,
                    starts_new_document=classification.starts_new_document,
                    classification_confidence=classification.model_reported_confidence,
                    corrected_webp_key=webp[0],
                    corrected_webp_version=webp[1],
                    corrected_ocr_key=ocr[0],
                    corrected_ocr_version=ocr[1],
                    plain_text_key=text[0],
                    plain_text_version=text[1],
                )
            )
        logical_rows: list[tuple[str, ProcessedLogicalDocument]] = []
        for document in run.v1_report.logical_documents:
            logical = document.logical_document
            logical_id = ids.new_id(ids.LOGICAL_DOCUMENT)
            self._session.add(
                ProcessingLogicalDocumentRow(
                    id=logical_id,
                    user_id=run.user_id,
                    matter_id=run.matter_id,
                    processing_run_id=run.id,
                    source_file_id=run.source_file_id,
                    document_index=logical.index,
                    type_id=logical.type_id,
                    suggested_name=logical.suggested_name,
                    page_numbers=list(logical.page_numbers),
                )
            )
            logical_rows.append((logical_id, document))

        # Candidate rows reference logical-document ids, but these ORM rows are
        # intentionally assembled without relationships. Persist every parent
        # first so SQLAlchemy cannot schedule candidates ahead of them.
        if logical_rows:
            await self._session.flush()

        for logical_id, document in logical_rows:
            for candidate in document.candidates:
                self._session.add(
                    ProcessingCandidateFieldRow(
                        id=ids.new_id(ids.CANDIDATE_FIELD),
                        user_id=run.user_id,
                        matter_id=run.matter_id,
                        logical_document_id=logical_id,
                        key=candidate.key,
                        candidate_value=str(candidate.value),
                        page_no=candidate.page_no,
                        model_reported_confidence=candidate.model_reported_confidence,
                        review_state="unverified",
                    )
                )

    async def link_v1_logical_documents(
        self, user_id: str, run_id: str, detected_document_ids: tuple[str, ...]
    ) -> None:
        rows = list(
            (
                await self._session.execute(
                    select(ProcessingLogicalDocumentRow)
                    .where(
                        ProcessingLogicalDocumentRow.user_id == user_id,
                        ProcessingLogicalDocumentRow.processing_run_id == run_id,
                    )
                    .order_by(ProcessingLogicalDocumentRow.document_index)
                )
            )
            .scalars()
            .all()
        )
        for row, document_id in zip(rows, detected_document_ids, strict=False):
            row.detected_document_id = document_id
        await self._session.flush()

    async def get_document_review(
        self, user_id: str, detected_document_id: str
    ) -> DocumentReview | None:
        logical = (
            await self._session.execute(
                select(ProcessingLogicalDocumentRow).where(
                    ProcessingLogicalDocumentRow.user_id == user_id,
                    ProcessingLogicalDocumentRow.detected_document_id == detected_document_id,
                )
            )
        ).scalar_one_or_none()
        if logical is None:
            return None
        page_rows = list(
            (
                await self._session.execute(
                    select(DocumentProcessingPageRow)
                    .where(
                        DocumentProcessingPageRow.user_id == user_id,
                        DocumentProcessingPageRow.processing_run_id == logical.processing_run_id,
                        DocumentProcessingPageRow.page_no.in_(logical.page_numbers),
                    )
                    .order_by(DocumentProcessingPageRow.page_no)
                )
            )
            .scalars()
            .all()
        )
        candidate_rows = list(
            (
                await self._session.execute(
                    select(ProcessingCandidateFieldRow)
                    .where(
                        ProcessingCandidateFieldRow.user_id == user_id,
                        ProcessingCandidateFieldRow.logical_document_id == logical.id,
                    )
                    .order_by(ProcessingCandidateFieldRow.key)
                )
            )
            .scalars()
            .all()
        )
        return DocumentReview(
            id=logical.id,
            matter_id=logical.matter_id,
            detected_document_id=detected_document_id,
            type_id=logical.type_id,
            suggested_name=logical.suggested_name,
            pages=tuple(
                ReviewPage(
                    id=row.id,
                    page_no=row.page_no,
                    corrected_width=row.corrected_width,
                    corrected_height=row.corrected_height,
                    quality_status=row.quality_status,
                    rotation_status=row.rotation_status,
                    classification_type_id=row.classification_type_id,
                    classification_confidence=row.classification_confidence,
                    corrected_webp_ref=(row.corrected_webp_key, row.corrected_webp_version),
                    corrected_ocr_ref=(row.corrected_ocr_key, row.corrected_ocr_version),
                )
                for row in page_rows
            ),
            candidates=tuple(
                replace(
                    self._to_review_candidate(row),
                    key=observational_field_key(logical.type_id, row.key),
                )
                for row in candidate_rows
            ),
        )

    async def get_page_artifact_ref(
        self, user_id: str, page_id: str, kind: str
    ) -> tuple[str, str] | None:
        row = (
            await self._session.execute(
                select(DocumentProcessingPageRow).where(
                    DocumentProcessingPageRow.user_id == user_id,
                    DocumentProcessingPageRow.id == page_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if kind == "image":
            return row.corrected_webp_key, row.corrected_webp_version
        if kind == "ocr":
            return row.corrected_ocr_key, row.corrected_ocr_version
        return None

    async def get_page_matter_id(self, user_id: str, page_id: str) -> str | None:
        return (
            await self._session.execute(
                select(DocumentProcessingPageRow.matter_id).where(
                    DocumentProcessingPageRow.user_id == user_id,
                    DocumentProcessingPageRow.id == page_id,
                )
            )
        ).scalar_one_or_none()

    async def get_candidate_matter_id(self, user_id: str, candidate_id: str) -> str | None:
        return (
            await self._session.execute(
                select(ProcessingCandidateFieldRow.matter_id).where(
                    ProcessingCandidateFieldRow.user_id == user_id,
                    ProcessingCandidateFieldRow.id == candidate_id,
                )
            )
        ).scalar_one_or_none()

    async def get_candidate_approval_input(
        self, user_id: str, candidate_id: str
    ) -> CandidateApprovalInput | None:
        result = await self._session.execute(
            select(
                ProcessingCandidateFieldRow,
                ProcessingLogicalDocumentRow,
                SourceFileRow,
            )
            .join(
                ProcessingLogicalDocumentRow,
                ProcessingLogicalDocumentRow.id == ProcessingCandidateFieldRow.logical_document_id,
            )
            .join(SourceFileRow, SourceFileRow.id == ProcessingLogicalDocumentRow.source_file_id)
            .where(
                ProcessingCandidateFieldRow.user_id == user_id,
                ProcessingLogicalDocumentRow.user_id == user_id,
                SourceFileRow.user_id == user_id,
                ProcessingCandidateFieldRow.id == candidate_id,
            )
        )
        row = result.one_or_none()
        if row is None or row[1].detected_document_id is None:
            return None
        candidate, logical, source = row
        return CandidateApprovalInput(
            candidate_id=candidate.id,
            user_id=user_id,
            matter_id=candidate.matter_id,
            source_file_id=source.id,
            detected_document_id=logical.detected_document_id,
            extraction_run_id=logical.processing_run_id,
            source_sha256=source.sha256,
            field_key=observational_field_key(logical.type_id, candidate.key),
            value=candidate.edited_value
            if candidate.edited_value is not None
            else candidate.candidate_value,
            original_value=candidate.candidate_value,
            version=candidate.version,
            page_no=candidate.page_no,
            model_reported_confidence=candidate.model_reported_confidence,
            review_state=candidate.review_state,
        )

    @staticmethod
    def _to_review_candidate(row: ProcessingCandidateFieldRow) -> ReviewCandidate:
        return ReviewCandidate(
            id=row.id,
            key=row.key,
            candidate_value=row.candidate_value,
            edited_value=row.edited_value,
            page_no=row.page_no,
            model_reported_confidence=row.model_reported_confidence,
            review_state=row.review_state,
            version=row.version,
        )

    async def update_candidate(
        self, user_id: str, candidate_id: str, value: str, expected_version: int
    ) -> ReviewCandidate:
        result = await self._session.execute(
            update(ProcessingCandidateFieldRow)
            .where(
                ProcessingCandidateFieldRow.user_id == user_id,
                ProcessingCandidateFieldRow.id == candidate_id,
                ProcessingCandidateFieldRow.version == expected_version,
                ProcessingCandidateFieldRow.review_state != "approved",
            )
            .values(
                edited_value=value,
                review_state="unverified",
                approved_by=None,
                approved_at=None,
                version=expected_version + 1,
            )
            .returning(ProcessingCandidateFieldRow)
        )
        row = result.scalar_one_or_none()
        if row is None:
            if await self.get_candidate_matter_id(user_id, candidate_id) is None:
                raise DocumentReviewNotFoundError()
            current = await self.get_candidate_approval_input(user_id, candidate_id)
            if current is not None and current.review_state == "approved":
                raise CandidateAlreadyApprovedError()
            raise CandidateFieldStaleError(expectedVersion=expected_version)
        return self._to_review_candidate(row)

    async def approve_candidate(
        self,
        user_id: str,
        candidate_id: str,
        actor_id: str,
        approved_fact_id: str,
        expected_version: int,
    ) -> ReviewCandidate:
        result = await self._session.execute(
            update(ProcessingCandidateFieldRow)
            .where(
                ProcessingCandidateFieldRow.user_id == user_id,
                ProcessingCandidateFieldRow.id == candidate_id,
                ProcessingCandidateFieldRow.version == expected_version,
                ProcessingCandidateFieldRow.review_state != "approved",
            )
            .values(
                review_state="approved",
                approved_by=actor_id,
                approved_at=datetime.now(tz=UTC),
                approved_fact_id=approved_fact_id,
                version=expected_version + 1,
            )
            .returning(ProcessingCandidateFieldRow)
        )
        row = result.scalar_one_or_none()
        if row is None:
            if await self.get_candidate_matter_id(user_id, candidate_id) is None:
                raise DocumentReviewNotFoundError()
            current = await self.get_candidate_approval_input(user_id, candidate_id)
            if current is not None and current.review_state == "approved":
                raise CandidateAlreadyApprovedError()
            raise CandidateFieldStaleError(expectedVersion=expected_version)
        return self._to_review_candidate(row)

    async def list_runs_for_source_file(
        self, user_id: str, source_file_id: str
    ) -> list[ProcessingRun]:
        result = await self._session.execute(
            select(SourceFileProcessingRunRow)
            .where(
                SourceFileProcessingRunRow.user_id == user_id,
                SourceFileProcessingRunRow.source_file_id == source_file_id,
            )
            .order_by(
                SourceFileProcessingRunRow.started_at.desc(), SourceFileProcessingRunRow.id.desc()
            )
        )
        return [
            ProcessingRun(
                id=row.id,
                user_id=row.user_id,
                matter_id=row.matter_id,
                source_file_id=row.source_file_id,
                provider=row.provider,
                outcome=SourceFileState(row.outcome),
                started_at=row.started_at,
                correlation_id=row.correlation_id,
                reasons=tuple(row.reasons),
                pages_processed=row.pages_processed,
                ai_extraction_calls=row.ai_extraction_calls,
                finished_at=row.finished_at,
                failure_reason=_run_failure_reason(row),
                failure_explanation_key=(
                    failure_explanation_key(reason)
                    if (reason := _run_failure_reason(row))
                    else None
                ),
            )
            for row in result.scalars().all()
        ]

    async def get_latest_run_for_source_file(
        self, user_id: str, matter_id: str, source_file_id: str
    ) -> ProcessingRun | None:
        result = await self._session.execute(
            select(SourceFileProcessingRunRow)
            .where(
                SourceFileProcessingRunRow.user_id == user_id,
                SourceFileProcessingRunRow.matter_id == matter_id,
                SourceFileProcessingRunRow.source_file_id == source_file_id,
            )
            .order_by(
                SourceFileProcessingRunRow.started_at.desc(), SourceFileProcessingRunRow.id.desc()
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        reason = _run_failure_reason(row)
        return ProcessingRun(
            id=row.id,
            user_id=row.user_id,
            matter_id=row.matter_id,
            source_file_id=row.source_file_id,
            provider=row.provider,
            outcome=SourceFileState(row.outcome),
            started_at=row.started_at,
            correlation_id=row.correlation_id,
            reasons=tuple(row.reasons),
            pages_processed=row.pages_processed,
            ai_extraction_calls=row.ai_extraction_calls,
            finished_at=row.finished_at,
            failure_reason=reason,
            failure_explanation_key=failure_explanation_key(reason) if reason else None,
        )

    async def list_run_page_outcomes(
        self, user_id: str, matter_id: str, source_file_id: str, run_id: str
    ) -> tuple[ProcessingPageOutcome, ...]:
        result = await self._session.execute(
            select(
                DocumentProcessingPageRow.page_no,
                DocumentProcessingPageRow.quality_status,
                DocumentProcessingPageRow.rotation_status,
            )
            .where(
                DocumentProcessingPageRow.user_id == user_id,
                DocumentProcessingPageRow.matter_id == matter_id,
                DocumentProcessingPageRow.source_file_id == source_file_id,
                DocumentProcessingPageRow.processing_run_id == run_id,
            )
            .order_by(DocumentProcessingPageRow.page_no)
        )
        return tuple(ProcessingPageOutcome(*row) for row in result.all())


def _run_failure_reason(row: SourceFileProcessingRunRow) -> ProcessingFailureReason | None:
    """Existing jobs persist the failure enum in reasons; preserve legacy rows."""
    if row.outcome != SourceFileState.PROCESSING_FAILED.value:
        return None
    for reason in row.reasons:
        try:
            return ProcessingFailureReason(reason)
        except ValueError:
            continue
    return None

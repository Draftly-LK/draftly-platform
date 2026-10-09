"""The boundary between a stored source file and the extraction pipeline.

`SynchronousProcessingJob` implements `ProcessingJobPort` by calling the
existing `DocumentProcessingService` inline. There is no queue, no worker, and
no timer: the run this returns is already terminal.

The important behaviour is what happens when nothing can process the file.
Two gates are checked before any byte is read:

1. **No provider configured** — the run finishes ``PROCESSING_FAILED`` with
   ``NOT_CONFIGURED``.
2. **The §10A data-protection gate is closed** — the run finishes
   ``PROCESSING_FAILED`` with ``DATA_PROTECTION_GATE``, and the client's
   evidence never leaves the deployment.

A third check sits between the read and the pipeline: the bytes are hashed and
compared against the hash recorded at upload. Storage pins the object version,
which proves the bytes came from the object of record; this proves they are
still the bytes of record. It raises rather than failing the run, because a
mismatch means stored evidence was altered — that is a fault to investigate,
not an outcome to file against the document.

Neither path invents progress, sleeps, or marks the file ``PROCESSED``. A
document nothing processed is reported as unprocessed, with a reason the lawyer
can act on. The persisted-ingestion path deliberately has no ``synthetic``
escape hatch: a matter's uploaded evidence is client material by definition, so
there is no flag a caller could set to talk its way past the closed gate.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import structlog

from src.modules.content_governance.contracts import ProcessingFailureReason, SourceFileState
from src.modules.document.application.processing_service import (
    REASON_DATA_APPROVAL,
    DocumentProcessingService,
)
from src.modules.document.application.v1_pipeline import V1DocumentPipeline
from src.modules.document.domain.errors import (
    ExtractionProviderError,
    ExtractionProviderTimeoutError,
    SourceFileNotProcessableError,
    SourceObjectIntegrityError,
    UnsupportedDocumentError,
)
from src.modules.document.domain.ingestion import (
    CandidateFieldRef,
    DocumentCandidate,
    ProcessingRun,
    SourceFile,
)
from src.modules.document.domain.ingestion_policies import (
    document_class_for_extraction_kind,
    failure_explanation_key,
)
from src.modules.document.domain.models import ProcessingOutcome, ProcessingReport
from src.modules.document.domain.v1 import V1PipelineReport
from src.modules.document.ports import MatterDocumentTypesPort, SourceFileStoragePort
from src.platform import ids

log = structlog.get_logger(__name__)


class SynchronousProcessingJob:
    """Runs the pipeline over one stored source file and reports honestly."""

    def __init__(
        self,
        *,
        storage: SourceFileStoragePort,
        pipeline: DocumentProcessingService | None,
        provider_name: str,
        data_protection_approved: bool,
        v1_pipeline: V1DocumentPipeline | None = None,
        matter_document_types: MatterDocumentTypesPort | None = None,
    ) -> None:
        self._storage = storage
        self._pipeline = pipeline
        self._provider_name = provider_name
        self._data_protection_approved = data_protection_approved
        self._v1_pipeline = v1_pipeline
        self._matter_document_types = matter_document_types

    async def enqueue(self, *, source_file: SourceFile, correlation_id: str = "") -> ProcessingRun:
        started_at = datetime.now(tz=UTC)

        if self._pipeline is None and self._v1_pipeline is None:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.NOT_CONFIGURED, correlation_id
            )
        if not self._data_protection_approved:
            return self._failed(
                source_file,
                started_at,
                ProcessingFailureReason.DATA_PROTECTION_GATE,
                correlation_id,
            )
        if not source_file.has_stored_bytes:
            # Reachable only for a rejected source, which holds no object to read.
            raise SourceFileNotProcessableError(
                "This source file was rejected in quarantine and holds no stored bytes.",
                sourceFileId=source_file.id,
                state=source_file.state.value,
            )

        data = await self._storage.get(
            source_file.storage_object_key, version=source_file.storage_object_version
        )
        # Storage proved these bytes came from the recorded object; this proves
        # they are the bytes that were hashed at upload. It runs before the
        # pipeline so nothing unverified reaches a provider.
        digest = hashlib.sha256(data).hexdigest()
        if digest != source_file.sha256:
            log.error(
                "source_file.storage.integrity_failed",
                source_file_id=source_file.id,
                storage_object_key=source_file.storage_object_key,
                expected_sha256=source_file.sha256,
                found_sha256=digest,
            )
            raise SourceObjectIntegrityError(
                sourceFileId=source_file.id,
                storageObjectKey=source_file.storage_object_key,
                storageObjectVersion=source_file.storage_object_version,
            )

        try:
            if self._v1_pipeline is not None and self._matter_document_types is not None:
                types = await self._matter_document_types.for_matter(
                    user_id=source_file.user_id, matter_id=source_file.matter_id
                )
                v1_report = await self._v1_pipeline.process(
                    data,
                    source_file.media_type,
                    allowed_type_ids=types.allowed_type_ids,
                    extraction_schemas=types.extraction_schemas,
                )
                return await self._from_v1_report(
                    source_file, started_at, v1_report, correlation_id
                )
            assert self._pipeline is not None
            report = await self._pipeline.process(
                data, source_file.media_type, synthetic=False, correlation_id=correlation_id
            )
        except UnsupportedDocumentError:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.UNSUPPORTED_MEDIA, correlation_id
            )
        except ExtractionProviderTimeoutError:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.TIMEOUT, correlation_id
            )
        except ExtractionProviderError:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.PROVIDER_ERROR, correlation_id
            )

        return self._from_report(source_file, started_at, report, correlation_id)

    async def _from_v1_report(
        self,
        source_file: SourceFile,
        started_at: datetime,
        report: V1PipelineReport,
        correlation_id: str,
    ) -> ProcessingRun:
        """Persist rebuildable page artifacts and map groups to existing candidates."""
        run_id = ids.new_id(ids.PROCESSING_RUN)
        for page in report.pages:
            # Derivatives sit under their own prefix, beside the original rather than
            # inside its key: on filesystem storage the original key is a file, so a
            # path beneath it cannot exist. Earlier runs keep the refs they recorded.
            base = f"derivatives/{source_file.storage_object_key}/{run_id}/pages/{page.page_no}"
            for kind, suffix, payload in (
                ("corrected_webp", "page.webp", page.corrected_webp),
                ("corrected_ocr_json", "ocr.json", page.ocr_json),
                ("plain_ocr_text", "text.txt", page.plain_text),
            ):
                key = f"{base}/{suffix}"
                version = await self._storage.put(key, payload)
                page.derivative_refs[kind] = (key, version)

        pages_by_no = {page.page_no: page for page in report.pages}
        candidates: list[DocumentCandidate] = []
        for document in report.logical_documents:
            logical = document.logical_document
            page_classifications = [
                pages_by_no[page_no].classification for page_no in logical.page_numbers
            ]
            assert all(item is not None for item in page_classifications)
            confidence = min(
                item.model_reported_confidence for item in page_classifications if item is not None
            )
            languages = sorted(
                {
                    language.code
                    for page_no in logical.page_numbers
                    for language in pages_by_no[page_no].ocr.detected_languages
                }
            )
            class_id = logical.type_id if logical.type_id != "other" else None
            candidates.append(
                DocumentCandidate(
                    page_start=min(logical.page_numbers),
                    page_end=max(logical.page_numbers),
                    source_file_id=source_file.id,
                    boundary_confidence=confidence,
                    continuity_anomaly=False,
                    class_id=class_id,
                    class_confidence=confidence,
                    class_top_two_margin=0.0,
                    language_codes=tuple(languages),
                    candidate_fields=tuple(
                        CandidateFieldRef(
                            key=item.key,
                            value=item.value,
                            page_no=item.page_no,
                            source_file_id=source_file.id,
                            model_reported_confidence=item.model_reported_confidence,
                            provider="gemini-2.5-flash-lite",
                        )
                        for item in document.candidates
                    ),
                )
            )
        return ProcessingRun(
            id=run_id,
            user_id=source_file.user_id,
            matter_id=source_file.matter_id,
            source_file_id=source_file.id,
            provider="google-vision+gemini-2.5-flash-lite",
            outcome=SourceFileState.PROCESSED,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            correlation_id=correlation_id,
            pages_processed=len(report.pages),
            ai_extraction_calls=report.classification_calls + report.extraction_calls,
            candidates=tuple(candidates),
            v1_report=report,
        )

    # ── Mapping ──────────────────────────────────────────────────────────────

    def _from_report(
        self,
        source_file: SourceFile,
        started_at: datetime,
        report: ProcessingReport,
        correlation_id: str,
    ) -> ProcessingRun:
        if REASON_DATA_APPROVAL in report.reasons:
            # Belt and braces: the gate is checked above, and again on whatever
            # the pipeline reports, so a refused document can never be recorded
            # as processed by a future change to either side.
            return self._failed(
                source_file,
                started_at,
                ProcessingFailureReason.DATA_PROTECTION_GATE,
                correlation_id,
            )
        if report.outcome is ProcessingOutcome.UNSUPPORTED:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.UNSUPPORTED_MEDIA, correlation_id
            )

        # MANUAL_REVIEW is a successful run (§5 Level 3): the pages were read and
        # the document is waiting for a human, which is a state, not a failure.
        page_count = report.page_count or source_file.page_count or 1
        class_id = document_class_for_extraction_kind(report.kind)
        candidate = DocumentCandidate(
            page_start=1,
            page_end=max(page_count, 1),
            source_file_id=source_file.id,
            # No boundary detector runs in this pipeline, so the proposed range
            # is the whole file and carries no score (§6.2 stage 5 is not built).
            boundary_confidence=None,
            continuity_anomaly=False,
            class_id=class_id,
            class_confidence=report.kind_model_confidence if class_id else 0.0,
            # The provider reports one score, not a ranking, so the §6.4
            # top-two margin is unknown and scores 0 — which keeps every class
            # out of the auto-organize band until a ranking engine exists.
            class_top_two_margin=0.0,
            candidate_fields=tuple(
                CandidateFieldRef(
                    key=field.key,
                    value=field.value,
                    page_no=field.page_no,
                    source_file_id=source_file.id,
                    model_reported_confidence=field.model_reported_confidence,
                    provider=field.source,
                    format_valid=field.format_valid,
                )
                for field in report.fields
            ),
        )
        return ProcessingRun(
            id=ids.new_id(ids.PROCESSING_RUN),
            user_id=source_file.user_id,
            matter_id=source_file.matter_id,
            source_file_id=source_file.id,
            provider=report.provider,
            outcome=SourceFileState.PROCESSED,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            correlation_id=correlation_id,
            reasons=tuple(report.reasons),
            pages_processed=report.pages_processed,
            ai_extraction_calls=report.ai_extraction_calls,
            candidates=(candidate,),
        )

    def _failed(
        self,
        source_file: SourceFile,
        started_at: datetime,
        reason: ProcessingFailureReason,
        correlation_id: str,
    ) -> ProcessingRun:
        log.info(
            "source_file.processing.not_performed",
            source_file_id=source_file.id,
            reason=reason.value,
            provider=self._provider_name,
        )
        return ProcessingRun(
            id=ids.new_id(ids.PROCESSING_RUN),
            user_id=source_file.user_id,
            matter_id=source_file.matter_id,
            source_file_id=source_file.id,
            provider=self._provider_name,
            outcome=SourceFileState.PROCESSING_FAILED,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            correlation_id=correlation_id,
            reasons=(reason.value,),
            failure_reason=reason,
            failure_explanation_key=failure_explanation_key(reason),
        )

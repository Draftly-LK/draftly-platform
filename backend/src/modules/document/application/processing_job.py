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

Neither path invents progress, sleeps, or marks the file ``PROCESSED``. A
document nothing processed is reported as unprocessed, with a reason the lawyer
can act on. The persisted-ingestion path deliberately has no ``synthetic``
escape hatch: a matter's uploaded evidence is client material by definition, so
there is no flag a caller could set to talk its way past the closed gate.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from src.modules.content_governance.contracts import ProcessingFailureReason, SourceFileState
from src.modules.document.application.processing_service import (
    REASON_DATA_APPROVAL,
    DocumentProcessingService,
)
from src.modules.document.domain.errors import (
    ExtractionProviderError,
    SourceFileNotProcessableError,
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
from src.modules.document.ports import SourceFileStoragePort
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
    ) -> None:
        self._storage = storage
        self._pipeline = pipeline
        self._provider_name = provider_name
        self._data_protection_approved = data_protection_approved

    async def enqueue(self, *, source_file: SourceFile, correlation_id: str = "") -> ProcessingRun:
        started_at = datetime.now(tz=UTC)

        if self._pipeline is None:
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

        data = await self._storage.get(source_file.storage_object_key)
        try:
            report = await self._pipeline.process(
                data,
                source_file.media_type,
                synthetic=False,
                correlation_id=correlation_id,
            )
        except UnsupportedDocumentError:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.UNSUPPORTED_MEDIA, correlation_id
            )
        except ExtractionProviderError:
            return self._failed(
                source_file, started_at, ProcessingFailureReason.PROVIDER_ERROR, correlation_id
            )

        return self._from_report(source_file, started_at, report, correlation_id)

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

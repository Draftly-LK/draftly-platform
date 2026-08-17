"""Document-processing API router.

Routes:
  POST /api/v1/documents/process → run the extraction pipeline on one upload

Persisted ingestion (source files, the document inbox, boundary and
classification decisions) lives in ``api/ingestion_router.py`` and is included
below, so the module still mounts exactly one router.

INTERIM SYNCHRONOUS ROUTE. document-processing.md §1 places this pipeline in
the ``document_jobs`` worker behind the outbox (jobs-and-workers.md §5,
``document.process``). Neither the outbox nor the worker runtime exists yet,
so this route invokes the same ``DocumentProcessingService`` inline. When the
worker lands, ``modules/document/jobs.py`` calls the identical service and
this route becomes an upload-and-enqueue.

Everything returned is a CANDIDATE for lawyer verification — nothing here is,
or can become, a verified particular (§8 honesty rules).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.api.deps import get_correlation_id, get_request_context
from src.modules.document.api.ingestion_router import router as ingestion_router
from src.modules.document.api.schemas import CandidateFieldRead, ProcessingReportRead
from src.modules.document.application.processing_service import (
    DocumentProcessingService,
)
from src.modules.document.domain.errors import UnsupportedDocumentError
from src.modules.document.domain.models import ProcessingReport
from src.platform.request_context import RequestContext

router = APIRouter(tags=["documents"])
router.include_router(ingestion_router)

_ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}

_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
}


def get_processing_service() -> DocumentProcessingService:
    """Request dependency; the adapter set is chosen once in bootstrap."""
    from src.bootstrap import build_processing_service

    return build_processing_service()


def _to_read(report: ProcessingReport) -> ProcessingReportRead:
    return ProcessingReportRead(
        outcome=report.outcome.value,
        kind=report.kind,
        kind_model_confidence=report.kind_model_confidence,
        page_count=report.page_count,
        provider=report.provider,
        fields=[
            CandidateFieldRead(
                key=field.key,
                value=field.value,
                page_no=field.page_no,
                source=field.source,
                model_reported_confidence=field.model_reported_confidence,
                format_valid=field.format_valid,
            )
            for field in report.fields
        ],
        transcripts=report.transcripts,
        reasons=report.reasons,
        ai_extraction_calls=report.ai_extraction_calls,
        pages_processed=report.pages_processed,
    )


@router.post("/documents/process", response_model=ProcessingReportRead)
async def process_document(
    file: Annotated[UploadFile, File()],
    synthetic: Annotated[bool, Form()] = False,
    ctx: RequestContext = Depends(get_request_context),
    correlation_id: str = Depends(get_correlation_id),
    service: DocumentProcessingService = Depends(get_processing_service),
) -> ProcessingReportRead:
    """Extract candidate particulars from one uploaded document.

    ``synthetic`` must be true for demo/fixture material; real documents are
    refused into ``manual_review`` until ``PROVIDER_DATA_APPROVAL`` is granted
    (document-processing.md §10A) — a state, not an error.
    """
    _ = ctx  # auth perimeter; the report is caller-scoped, nothing persists yet
    mime = _MIME_ALIASES.get(file.content_type or "", file.content_type or "")
    if mime not in _ALLOWED_MIME:
        raise UnsupportedDocumentError(f"Unsupported content type '{file.content_type}'.")
    data = await file.read()
    if not data:
        raise UnsupportedDocumentError("The uploaded file is empty.")
    report = await service.process(
        data,
        mime,
        synthetic=synthetic,
        correlation_id=correlation_id,
    )
    return _to_read(report)

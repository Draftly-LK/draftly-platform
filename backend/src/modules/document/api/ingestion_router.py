"""Source-file ingestion and document-inbox routes.

```text
POST /api/v1/matters/{id}/source-files                       upload (multipart)
GET  /api/v1/matters/{id}/source-files                       paginated list
GET  /api/v1/source-files/{id}                               ETag = version
POST /api/v1/source-files/{id}/process                       run the pipeline
POST /api/v1/source-files/{id}/supersede                     newer version
GET  /api/v1/matters/{id}/document-inbox                     grouped review queue
POST /api/v1/detected-documents/{id}/boundary-decisions      split / join pages
POST /api/v1/detected-documents/{id}/classification-decisions
```

Included by ``api/router.py`` so the module keeps one mounted router.

Documents and source files are addressed without their matter in the path (§12.4),
so every one of those routes resolves the row under the caller's ``user_id``
first and authorises against the matter it turns out to belong to. A 404 covers
both "absent" and "not yours", which is why the resolution happens before any
capability is named.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_request_context, require_if_match
from src.modules.content_governance.contracts import (
    CAP_DOCUMENT_CLASSIFY,
    CAP_SOURCE_UPLOAD,
    DocumentVersionRelationship,
)
from src.modules.document.api.schemas import (
    BoundaryDecisionRequest,
    ClassificationDecisionRequest,
    DetectedDocumentRead,
    DocumentFragmentRead,
    DocumentInboxRead,
    PageCandidateRead,
    PageInfo,
    ProcessingRunRead,
    SourceFileListRead,
    SourceFileRead,
    SupersedeSourceFileRequest,
)
from src.modules.document.application.ingestion_service import (
    DocumentInboxView,
    DocumentView,
    ProcessingRunView,
    SourceFileIngestionService,
    SourceFileView,
)
from src.modules.document.domain.errors import SourceFileTooLargeError
from src.modules.document.domain.ingestion import FragmentRange
from src.modules.matter.contracts import require_rta_capability
from src.modules.matter.domain.errors import MatterNotFoundError
from src.platform.db.session import get_db, get_uow
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.errors import DomainRuleError
from src.platform.request_context import RequestContext

router = APIRouter(tags=["source-files"])

#: Upload bytes are read in chunks so an oversized file is refused before it is
#: buffered in full (§6.2 stage 1 is a server-side limit, not a client hint).
_UPLOAD_CHUNK_BYTES = 1024 * 1024


def get_ingestion_service(session: AsyncSession = Depends(get_db)) -> SourceFileIngestionService:
    from src.bootstrap import build_ingestion_service

    return build_ingestion_service(session)


async def _authorized_matter(
    ctx: RequestContext, matter_id: str, session: AsyncSession, capability: str
) -> None:
    """Resolve the matter through its own module, then check the capability."""
    from src.bootstrap import build_matter_service

    summary = await build_matter_service(session).get_access_summary(ctx.actor_id, matter_id)
    if summary is None:
        raise MatterNotFoundError()
    require_rta_capability(
        account_role=ctx.account_role.value,
        actor_id=ctx.actor_id,
        matter=summary,
        capability=capability,
    )


async def _read_within_limit(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise SourceFileTooLargeError(maxByteLength=limit)
        chunks.append(chunk)
    return b"".join(chunks)


def _to_source_read(view: SourceFileView) -> SourceFileRead:
    source = view.source_file
    return SourceFileRead(
        id=source.id,
        matter_id=source.matter_id,
        original_filename=source.original_filename,
        media_type=source.media_type,
        byte_length=source.byte_length,
        sha256=source.sha256,
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
        duplicate_of_source_file_id=view.duplicate_of_source_file_id,
        version_relationship=(
            view.version_relationship.value if view.version_relationship else None
        ),
        detected_document_ids=list(view.detected_document_ids),
        contains_multiple_documents=view.contains_multiple_documents,
        created_at=source.created_at.isoformat(),
        updated_at=source.updated_at.isoformat(),
        version=source.version,
    )


def _to_document_read(view: DocumentView) -> DetectedDocumentRead:
    document = view.document
    return DetectedDocumentRead(
        id=document.id,
        matter_id=document.matter_id,
        class_id=document.class_id,
        class_confidence=document.class_confidence,
        class_status=document.class_status.value,
        boundary_status=document.boundary_status.value,
        language_codes=list(document.language_codes),
        issuer=document.issuer,
        issue_or_execution_date_fact_id=document.issue_or_execution_date_fact_id,
        version_relationship=(
            document.version_relationship.value if document.version_relationship else None
        ),
        duplicate_of_detected_document_id=document.duplicate_of_detected_document_id,
        fragments=[
            DocumentFragmentRead(
                id=fragment.id,
                source_file_id=fragment.source_file_id,
                page_start=fragment.page_start,
                page_end=fragment.page_end,
                order_in_document=fragment.order_in_document,
                boundary_confidence=fragment.boundary_confidence,
                boundary_status=fragment.boundary_status.value,
            )
            for fragment in view.fragments
        ],
        source_file_ids=list(view.source_file_ids),
        spans_multiple_sources=view.spans_multiple_sources,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
        version=document.version,
    )


def _to_inbox_read(view: DocumentInboxView, limit: int) -> DocumentInboxRead:
    return DocumentInboxRead(
        matter_id=view.matter_id,
        source_files=[_to_source_read(source) for source in view.source_files],
        documents=[_to_document_read(document) for document in view.documents],
        boundary_review_document_ids=list(view.boundary_review_document_ids),
        classification_review_document_ids=list(view.classification_review_document_ids),
        unidentified_document_ids=list(view.unidentified_document_ids),
        unprocessed_source_file_ids=list(view.unprocessed_source_file_ids),
        page=PageInfo(
            next_cursor=view.next_cursor, has_more=view.next_cursor is not None, limit=limit
        ),
    )


def _to_run_read(view: ProcessingRunView) -> ProcessingRunRead:
    run = view.run
    documents = list(view.documents)
    # Attribution is per page, not per file: one PDF can hold several documents,
    # and a candidate read from page 3 belongs to whichever of them claims page 3.
    # Verification turns these into evidence references.
    document_by_page: dict[tuple[str, int], str] = {
        (fragment.source_file_id, page): document.document.id
        for document in documents
        for fragment in document.fragments
        for page in range(fragment.page_start, fragment.page_end + 1)
    }
    return ProcessingRunRead(
        job_id=run.id,
        state="succeeded" if run.succeeded else "failed",
        poll_after_ms=None,
        source_file_id=run.source_file_id,
        provider=run.provider,
        outcome=run.outcome.value,
        reasons=list(run.reasons),
        failure_reason=run.failure_reason.value if run.failure_reason else None,
        failure_explanation_key=run.failure_explanation_key,
        pages_processed=run.pages_processed,
        ai_extraction_calls=run.ai_extraction_calls,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        correlation_id=run.correlation_id,
        source_file=_to_source_read(
            SourceFileView(
                source_file=view.source_file,
                detected_document_ids=tuple(document.document.id for document in documents),
                contains_multiple_documents=len(documents) > 1,
            )
        ),
        detected_documents=[_to_document_read(document) for document in documents],
        candidate_fields=[
            PageCandidateRead(
                key=field.key,
                value=field.value,
                page_no=field.page_no,
                source_file_id=field.source_file_id,
                detected_document_id=document_by_page.get((field.source_file_id, field.page_no)),
                provider=field.provider,
                model_reported_confidence=field.model_reported_confidence,
                format_valid=field.format_valid,
            )
            for candidate in run.candidates
            for field in candidate.candidate_fields
        ],
        candidates_withheld=view.candidates_withheld,
    )


@router.post("/matters/{matter_id}/source-files", response_model=SourceFileRead, status_code=201)
async def upload_source_file(
    matter_id: str,
    file: Annotated[UploadFile, File()],
    response: Response,
    original_filename: Annotated[str | None, Form()] = None,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
) -> SourceFileRead:
    """Upload one file into a matter.

    Returns 201 even when quarantine refused the bytes: the refusal is itself a
    record the lawyer needs, carrying ``state = REJECTED``, a machine-readable
    ``failureReason``, and an explanation key (§6.2 stage 1, §10.2). An exact
    duplicate is reported through ``duplicateOfSourceFileId`` and both copies
    are kept (§6.3).
    """
    _ = uow
    await _authorized_matter(ctx, matter_id, session, CAP_SOURCE_UPLOAD)
    data = await _read_within_limit(file, service.max_upload_bytes)
    result = await service.upload_source_file(
        user_id=ctx.actor_id,
        matter_id=matter_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        filename=original_filename or file.filename or "upload",
        declared_media_type=file.content_type,
        data=data,
    )
    response.headers["ETag"] = f'"{result.source_file.version}"'
    return _to_source_read(result.view)


@router.get("/matters/{matter_id}/source-files", response_model=SourceFileListRead)
async def list_source_files(
    matter_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
) -> SourceFileListRead:
    await _authorized_matter(ctx, matter_id, session, CAP_DOCUMENT_CLASSIFY)
    views, next_cursor = await service.list_source_files(
        user_id=ctx.actor_id, matter_id=matter_id, limit=limit, cursor=cursor
    )
    return SourceFileListRead(
        items=[_to_source_read(view) for view in views],
        page=PageInfo(next_cursor=next_cursor, has_more=next_cursor is not None, limit=limit),
    )


@router.get("/source-files/{source_file_id}", response_model=SourceFileRead)
async def get_source_file(
    source_file_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
) -> SourceFileRead:
    view = await service.get_source_file(user_id=ctx.actor_id, source_file_id=source_file_id)
    await _authorized_matter(ctx, view.source_file.matter_id, session, CAP_DOCUMENT_CLASSIFY)
    response.headers["ETag"] = f'"{view.source_file.version}"'
    return _to_source_read(view)


@router.post("/source-files/{source_file_id}/process", response_model=ProcessingRunRead)
async def process_source_file(
    source_file_id: str,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> ProcessingRunRead:
    """Run the pipeline over one stored file and report what it did.

    The response is a terminal run envelope, not a promise. With no provider
    configured, or with the data-protection gate closed, ``state`` is ``failed``
    with ``failureReason`` ``NOT_CONFIGURED`` / ``DATA_PROTECTION_GATE`` — the
    file stays readable and honestly unprocessed.
    """
    _ = uow
    view = await service.get_source_file(user_id=ctx.actor_id, source_file_id=source_file_id)
    await _authorized_matter(ctx, view.source_file.matter_id, session, CAP_SOURCE_UPLOAD)
    run_view = await service.process_source_file(
        user_id=ctx.actor_id,
        source_file_id=source_file_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
    )
    response.headers["ETag"] = f'"{run_view.source_file.version}"'
    return _to_run_read(run_view)


@router.post("/source-files/{source_file_id}/supersede", response_model=SourceFileRead)
async def supersede_source_file(
    source_file_id: str,
    body: SupersedeSourceFileRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> SourceFileRead:
    """Record that a newer upload replaces this one. The row and bytes stay."""
    _ = uow
    view = await service.get_source_file(user_id=ctx.actor_id, source_file_id=source_file_id)
    await _authorized_matter(ctx, view.source_file.matter_id, session, CAP_DOCUMENT_CLASSIFY)
    try:
        relationship = DocumentVersionRelationship(body.relationship)
    except ValueError:
        raise DomainRuleError(
            f"'{body.relationship}' is not a valid version relationship.",
            field="relationship",
            value=body.relationship,
        )
    saved = await service.supersede_source_file(
        user_id=ctx.actor_id,
        source_file_id=source_file_id,
        replacement_source_file_id=body.superseded_by_source_file_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        relationship=relationship,
        reason=body.reason,
    )
    response.headers["ETag"] = f'"{saved.source_file.version}"'
    return _to_source_read(saved)


@router.get("/matters/{matter_id}/document-inbox", response_model=DocumentInboxRead)
async def get_document_inbox(
    matter_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
) -> DocumentInboxRead:
    """The review queue: files, the documents found in them, and the pairs."""
    await _authorized_matter(ctx, matter_id, session, CAP_DOCUMENT_CLASSIFY)
    view = await service.get_document_inbox(
        user_id=ctx.actor_id, matter_id=matter_id, limit=limit, cursor=cursor
    )
    return _to_inbox_read(view, limit)


@router.post(
    "/detected-documents/{document_id}/boundary-decisions", response_model=DetectedDocumentRead
)
async def decide_boundary(
    document_id: str,
    body: BoundaryDecisionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> DetectedDocumentRead:
    """Split, join, or reorder the pages a document claims. Sources are untouched."""
    _ = uow
    document = await service.get_detected_document(user_id=ctx.actor_id, document_id=document_id)
    await _authorized_matter(ctx, document.document.matter_id, session, CAP_DOCUMENT_CLASSIFY)
    view = await service.decide_boundary(
        user_id=ctx.actor_id,
        document_id=document_id,
        ranges=[
            FragmentRange(
                source_file_id=fragment.source_file_id,
                page_start=fragment.page_start,
                page_end=fragment.page_end,
                order_in_document=fragment.order_in_document or index,
            )
            for index, fragment in enumerate(body.fragments)
        ],
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        note=body.note,
    )
    response.headers["ETag"] = f'"{view.document.version}"'
    return _to_document_read(view)


@router.post(
    "/detected-documents/{document_id}/classification-decisions",
    response_model=DetectedDocumentRead,
)
async def decide_classification(
    document_id: str,
    body: ClassificationDecisionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    service: SourceFileIngestionService = Depends(get_ingestion_service),
    session: AsyncSession = Depends(get_db),
    uow: UnitOfWork = Depends(get_uow),
    expected_version: int = Depends(require_if_match),
) -> DetectedDocumentRead:
    """Confirm or correct the class. Only controlled ids are accepted."""
    _ = uow
    document = await service.get_detected_document(user_id=ctx.actor_id, document_id=document_id)
    await _authorized_matter(ctx, document.document.matter_id, session, CAP_DOCUMENT_CLASSIFY)
    view = await service.decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id=body.class_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        expected_version=expected_version,
        note=body.note,
    )
    response.headers["ETag"] = f'"{view.document.version}"'
    return _to_document_read(view)

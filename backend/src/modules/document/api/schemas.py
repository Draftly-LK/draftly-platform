"""Wire schemas for the document API (camelCase like auth).

Two families live here: the interim ``/documents/process`` report, and the
persisted ingestion contract (source files, detected documents, the inbox).

The inbox contract is shaped so one matter can show, at the same time, several
documents inside one PDF, one document spanning two files, an exact-duplicate
pair, a probable-newer-version pair, and an ``UNIDENTIFIED`` document. Those are
the §6.3 situations a lawyer must be able to see; a shape that cannot express
them would force the server to pick a lie.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _StrictCamel(_CamelModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CandidateFieldRead(_CamelModel):
    """One candidate particular. ``region`` is deliberately absent: the
    Gemini-only pipeline has page-level provenance and never fabricates
    bounding boxes."""

    key: str
    value: str | None
    page_no: int
    source: str
    model_reported_confidence: float
    format_valid: bool | None


class ProcessingReportRead(_CamelModel):
    outcome: str  # "extracted" | "manual_review" | "unsupported"
    kind: str
    kind_model_confidence: float
    page_count: int
    provider: str
    fields: list[CandidateFieldRead]
    transcripts: dict[int, str]
    reasons: list[str]
    ai_extraction_calls: int
    pages_processed: int


# ── Ingestion (§6.2, §12.2) ──────────────────────────────────────────────────


class PageInfo(_CamelModel):
    next_cursor: str | None
    has_more: bool
    limit: int


class SourceFileRead(_CamelModel):
    """One uploaded file. ``storageObjectKey`` is never exposed."""

    id: str
    matter_id: str
    original_filename: str
    media_type: str
    byte_length: int
    sha256: str
    storage_object_version: str
    upload_actor_id: str
    state: str
    page_count: int | None
    detected_languages: list[str]
    retention_class: str
    failure_reason: str | None
    #: Translation key telling the lawyer what to do about a failure or refusal.
    failure_explanation_key: str | None
    superseded_by_source_file_id: str | None
    derived_from_source_file_id: str | None
    #: The earlier upload with identical bytes, when this one repeats it (§6.3).
    duplicate_of_source_file_id: str | None
    #: ``EXACT_DUPLICATE`` when those bytes are already in the matter. A lawyer's
    #: version decision shows instead in ``state`` and ``supersededBySourceFileId``
    #: here, and on each detected document's own ``versionRelationship``.
    version_relationship: str | None
    detected_document_ids: list[str]
    #: Several documents were detected inside this one file (§6.3).
    contains_multiple_documents: bool
    created_at: str
    updated_at: str
    version: int


class SourceFileListRead(_CamelModel):
    items: list[SourceFileRead]
    page: PageInfo


class DocumentFragmentRead(_CamelModel):
    id: str
    source_file_id: str
    page_start: int
    page_end: int
    order_in_document: int
    #: Null when a human drew the range — a decision is not a model score.
    boundary_confidence: float | None
    boundary_status: str


class DetectedDocumentRead(_CamelModel):
    id: str
    matter_id: str
    class_id: str | None
    class_confidence: float | None
    class_status: str
    boundary_status: str
    language_codes: list[str]
    issuer: str | None
    issue_or_execution_date_fact_id: str | None
    version_relationship: str | None
    duplicate_of_detected_document_id: str | None
    fragments: list[DocumentFragmentRead]
    source_file_ids: list[str]
    #: One logical document assembled from fragments in more than one file (§6.3).
    spans_multiple_sources: bool
    created_at: str
    updated_at: str
    version: int


class DocumentInboxRead(_CamelModel):
    """The grouped review queue, paginated over source files."""

    matter_id: str
    source_files: list[SourceFileRead]
    documents: list[DetectedDocumentRead]
    boundary_review_document_ids: list[str]
    classification_review_document_ids: list[str]
    unidentified_document_ids: list[str]
    #: Stored, processing, or failed — never quietly counted as done.
    unprocessed_source_file_ids: list[str]
    page: PageInfo


class PageCandidateRead(_CamelModel):
    """One page-level candidate particular produced by a run.

    Returned rather than persisted here: the evidence table belongs to
    verification, which creates the ``EvidenceReference`` and candidate fact
    rows from these (§6.2 stage 8). Nothing in this payload is verified.
    """

    key: str
    value: str | None
    page_no: int
    source_file_id: str
    detected_document_id: str | None
    provider: str
    model_reported_confidence: float
    format_valid: bool | None


class ProcessingRunRead(_CamelModel):
    """The job envelope for one processing attempt (api-conventions §6).

    ``state`` is already terminal on return: the run is synchronous until the
    outbox and worker runtime exist, so ``pollAfterMs`` is null rather than a
    number that would invite a client to poll something that never changes.
    """

    job_id: str
    state: str  # "succeeded" | "failed"
    poll_after_ms: int | None
    source_file_id: str
    provider: str
    outcome: str
    reasons: list[str]
    failure_reason: str | None
    failure_explanation_key: str | None
    pages_processed: int
    ai_extraction_calls: int
    started_at: str
    finished_at: str | None
    correlation_id: str
    source_file: SourceFileRead
    detected_documents: list[DetectedDocumentRead]
    candidate_fields: list[PageCandidateRead]
    #: True when the run's candidates were withheld because the file already has
    #: documents a lawyer may have decided on (§6.5).
    candidates_withheld: bool


class SupersedeSourceFileRequest(_StrictCamel):
    """§6.3 newer version. Nothing is deleted either way."""

    superseded_by_source_file_id: str
    #: "SUPERSEDED" (the lawyer's decision) or "POSSIBLE_VERSION" (flag the pair
    #: for a decision without moving any state).
    relationship: str = "SUPERSEDED"
    reason: str | None = None


class FragmentRangeInput(_StrictCamel):
    source_file_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    order_in_document: int = Field(default=0, ge=0)


class BoundaryDecisionRequest(_StrictCamel):
    """Split, join, or reorder the pages this document claims.

    The ranges replace the current set. Naming more than one source file is how
    a document split across uploads is joined; the source bytes are untouched.
    """

    fragments: list[FragmentRangeInput] = Field(min_length=1)
    note: str | None = None


class ClassificationDecisionRequest(_StrictCamel):
    """Controlled class id only (§12.4), plus an optional lawyer note."""

    class_id: str
    note: str | None = None

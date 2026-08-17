"""Ingestion policies — the §10.2 state machine and the §6.3/§6.4 decisions.

Four rules in this file carry the legal safety of ingestion:

1. **Source bytes never become "edited".** `next_state` implements §10.2 and
   nothing else. There is no event that rewrites a stored file; a cleaned or
   rotated copy is a new `SourceFile` with ``derived_from_source_file_id``.
2. **`PROCESSED` is reachable only from `PROCESSING`.** A file nothing ran over
   cannot be marked processed by any caller, which is what keeps "unprocessed"
   honest when no provider is configured.
3. **A duplicate is detected, never deleted** (§6.3). `classify_duplicate`
   reports the relationship and returns; removal is a human act elsewhere.
4. **Thresholds are not re-derived here.** The automation decisions delegate to
   `content_governance.contracts`, which owns the §6.4 numbers, so a calibration
   change lands in one place.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Iterable, Mapping, Sequence

from src.modules.content_governance.contracts import (
    CONFIDENCE_POLICY,
    DOCUMENT_CLASSES,
    UNIDENTIFIED_DOCUMENT_CLASS_ID,
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    ProcessingFailureReason,
    SourceFileState,
    may_auto_organize_class,
    may_auto_split_boundary,
)
from src.modules.document.domain.errors import (
    BoundaryDecisionRequiresFragmentsError,
    IllegalSourceFileTransitionError,
    InvalidFragmentRangeError,
)
from src.modules.document.domain.ingestion import (
    DocumentFragment,
    FragmentRange,
    SourceFile,
)


class SourceFileEvent(str, enum.Enum):
    """The §10.2 guard column, named so a transition is auditable as an event."""

    BYTES_RECEIVED = "BYTES_RECEIVED"
    CHECKS_PASSED = "CHECKS_PASSED"
    CHECK_FAILED = "CHECK_FAILED"
    IMMUTABLE_WRITE_CONFIRMED = "IMMUTABLE_WRITE_CONFIRMED"
    PROCESSING_STARTED = "PROCESSING_STARTED"
    PROCESSING_COMPLETED = "PROCESSING_COMPLETED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    LATER_VERSION_IDENTIFIED = "LATER_VERSION_IDENTIFIED"


#: §10.2 exactly, plus two rows the specification implies rather than lists:
#:
#: - a retry after a failure — the table says "retry creates a new job attempt",
#:   which is only expressible if PROCESSING_FAILED can re-enter PROCESSING;
#: - a re-run of an already-processed file — §6.5 says reprocessing with a new
#:   OCR/model version creates a new extraction run, which needs the same door.
#:
#: Neither weakens the invariant that matters: both land in PROCESSING, and the
#: only way out of PROCESSING to PROCESSED is a run that finished. What §6.5
#: forbids — a re-run silently mutating an organised matter — is enforced by the
#: ingestion service, which withholds a re-run's candidates rather than
#: overwriting documents a lawyer may already have decided on.
_TRANSITIONS: dict[tuple[SourceFileState, SourceFileEvent], SourceFileState] = {
    (SourceFileState.UPLOAD_INITIATED, SourceFileEvent.BYTES_RECEIVED): (
        SourceFileState.QUARANTINED
    ),
    (SourceFileState.QUARANTINED, SourceFileEvent.CHECKS_PASSED): SourceFileState.VALIDATED,
    (SourceFileState.QUARANTINED, SourceFileEvent.CHECK_FAILED): SourceFileState.REJECTED,
    (SourceFileState.VALIDATED, SourceFileEvent.IMMUTABLE_WRITE_CONFIRMED): (
        SourceFileState.STORED
    ),
    (SourceFileState.STORED, SourceFileEvent.PROCESSING_STARTED): SourceFileState.PROCESSING,
    (SourceFileState.PROCESSING, SourceFileEvent.PROCESSING_COMPLETED): (SourceFileState.PROCESSED),
    (SourceFileState.PROCESSING, SourceFileEvent.PROCESSING_FAILED): (
        SourceFileState.PROCESSING_FAILED
    ),
    (SourceFileState.PROCESSING_FAILED, SourceFileEvent.PROCESSING_STARTED): (
        SourceFileState.PROCESSING
    ),
    (SourceFileState.PROCESSED, SourceFileEvent.PROCESSING_STARTED): SourceFileState.PROCESSING,
    (SourceFileState.PROCESSED, SourceFileEvent.LATER_VERSION_IDENTIFIED): (
        SourceFileState.SUPERSEDED
    ),
}


def next_state(current: SourceFileState, event: SourceFileEvent) -> SourceFileState:
    """Apply one §10.2 transition, or refuse it.

    Refusing is a 422 with both ends of the attempted move in ``details``, so a
    client can tell "wrong order" from "wrong file" without reading prose.
    """
    target = _TRANSITIONS.get((current, event))
    if target is None:
        raise IllegalSourceFileTransitionError(
            fromState=current.value,
            event=event.value,
        )
    return target


def can_transition(current: SourceFileState, event: SourceFileEvent) -> bool:
    return (current, event) in _TRANSITIONS


def failure_explanation_key(reason: ProcessingFailureReason) -> str:
    """The translation key telling the lawyer what to do about this failure.

    Derived rather than looked up so a reason added to the rule pack cannot
    reach a lawyer as a blank explanation; the missing string surfaces in the
    translation files instead, where it is visible.
    """
    return f"rta.source_file.failure.{reason.value.lower()}"


# ── Duplicates and versions (§6.3) ───────────────────────────────────────────


def classify_duplicate(
    new_sha256: str, existing: Iterable[SourceFile]
) -> DocumentVersionRelationship | None:
    """Report how a newly hashed upload relates to what the matter already has.

    Only an exact hash match is claimed. A *probable* content duplicate needs a
    perceptual or text similarity signal this pipeline does not compute, and
    guessing ``POSSIBLE_VERSION`` from a filename would be a fabricated
    relationship. ``POSSIBLE_VERSION`` therefore arrives only from a lawyer's
    supersede decision.

    Nothing is deleted here, and nothing is deleted by the caller: §6.3 keeps
    both copies and marks the relationship.
    """
    return (
        DocumentVersionRelationship.EXACT_DUPLICATE
        if find_exact_duplicate(new_sha256, existing) is not None
        else None
    )


def find_exact_duplicate(new_sha256: str, existing: Iterable[SourceFile]) -> SourceFile | None:
    """The earliest stored file with the same hash, so the pair is reportable.

    Rejected uploads are skipped: they hold no bytes, so calling a new upload a
    duplicate of one would point the lawyer at nothing.
    """
    candidates = [
        source
        for source in existing
        if source.sha256 == new_sha256 and source.state is not SourceFileState.REJECTED
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda source: (source.created_at, source.id))


# ── Automation limits (§6.4) — thresholds live in content_governance ─────────


def may_auto_confirm_boundary(confidence: float | None, *, continuity_anomaly: bool) -> bool:
    """Delegates to the rule pack; a continuity anomaly means missing pages.

    An absent score is not a low score with the benefit of the doubt — it is no
    detection at all, and it can never auto-confirm.
    """
    return confidence is not None and may_auto_split_boundary(confidence, continuity_anomaly)


def may_auto_organize_document_class(confidence: float, *, top_two_margin: float) -> bool:
    """Delegates to the rule pack. ``AI_ORGANIZED`` is never lawyer-confirmed."""
    return may_auto_organize_class(confidence, top_two_margin)


def boundary_status_for(confidence: float | None, *, continuity_anomaly: bool) -> BoundaryStatus:
    """Map a boundary score onto the §6.4 band the fragment may occupy."""
    if confidence is None:
        return BoundaryStatus.CANDIDATE
    if may_auto_confirm_boundary(confidence, continuity_anomaly=continuity_anomaly):
        return BoundaryStatus.CONFIRMED
    if confidence >= CONFIDENCE_POLICY.boundary_review_floor:
        return BoundaryStatus.REVIEW_REQUIRED
    # Below the floor the split is not proposed at all; the range stays a
    # candidate over the whole file until a human draws it.
    return BoundaryStatus.CANDIDATE


def class_status_for(
    class_id: str | None, confidence: float, *, top_two_margin: float
) -> DocumentClassStatus:
    """Map a classification score onto the §6.4 band.

    Below the review floor the result is ``UNIDENTIFIED``, which §6.3 makes a
    first-class outcome: the file stays in the inbox asking to be classified and
    is never relabelled ``other``.
    """
    if class_id is None or class_id == UNIDENTIFIED_DOCUMENT_CLASS_ID:
        return DocumentClassStatus.UNIDENTIFIED
    if may_auto_organize_document_class(confidence, top_two_margin=top_two_margin):
        return DocumentClassStatus.AI_ORGANIZED
    if confidence >= CONFIDENCE_POLICY.class_review_floor:
        return DocumentClassStatus.REVIEW_REQUIRED
    return DocumentClassStatus.UNIDENTIFIED


_CLASS_BY_EXTRACTION_KIND = {
    definition.extraction_template_kind: definition.id
    for definition in DOCUMENT_CLASSES
    if definition.extraction_template_kind
}


def document_class_for_extraction_kind(kind: str) -> str | None:
    """Translate an extraction registry kind into a controlled class id.

    A kind with no controlled class is not force-fitted to the nearest one: it
    returns ``None`` and the document lands as ``UNIDENTIFIED`` (§6.3).
    """
    return _CLASS_BY_EXTRACTION_KIND.get(kind)


# ── The two §6.3 shapes that must be representable ───────────────────────────


def bundle_spans_multiple_sources(fragments: Sequence[DocumentFragment]) -> bool:
    """One logical document assembled from fragments in more than one file.

    Source bytes are never merged to make this true — the relationship lives in
    the fragment set (§6.3 "one document split over files").
    """
    return len({fragment.source_file_id for fragment in fragments}) > 1


def source_contains_multiple_documents(
    fragments: Sequence[DocumentFragment], *, source_file_id: str
) -> bool:
    """Several documents detected inside one uploaded file (§6.3).

    Counted over documents, not fragments: a document split into two ranges of
    the same PDF around an inserted page is still one document.
    """
    documents = {
        fragment.detected_document_id
        for fragment in fragments
        if fragment.source_file_id == source_file_id
    }
    return len(documents) > 1


def validate_boundary_decision(
    ranges: Sequence[FragmentRange], *, page_counts: Mapping[str, int | None]
) -> None:
    """Check a lawyer's split/join before it replaces a fragment set (§6.5).

    ``page_counts`` maps each source file the decision names to its known page
    count, or ``None`` when the count was never established. An unknown count
    does not refuse the range: the file is readable and the lawyer can see the
    page they are pointing at, so refusing would be the pipeline overruling a
    human on the strength of something it failed to measure.
    """
    if not ranges:
        raise BoundaryDecisionRequiresFragmentsError()
    for fragment_range in ranges:
        if fragment_range.page_start < 1 or fragment_range.page_end < fragment_range.page_start:
            raise InvalidFragmentRangeError(
                sourceFileId=fragment_range.source_file_id,
                pageStart=fragment_range.page_start,
                pageEnd=fragment_range.page_end,
            )
        known = page_counts.get(fragment_range.source_file_id)
        if known is not None and fragment_range.page_end > known:
            raise InvalidFragmentRangeError(
                "That page range runs past the end of the source file.",
                sourceFileId=fragment_range.source_file_id,
                pageEnd=fragment_range.page_end,
                pageCount=known,
            )


# ── Content-based validation (§6.2 stage 1) ──────────────────────────────────

#: Magic bytes, because a filename extension is a claim by the uploader. Order
#: matters only in that each prefix is unambiguous.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
)

_PDF_ENCRYPT_RE = re.compile(rb"/Encrypt[\s/<\d]")
#: Counts page objects in an uncompressed cross-reference table. A PDF using
#: object streams hides them, which is why an unreadable count is ``None``
#: ("unknown") and never 0 ("empty").
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page[^s]")


def sniff_media_type(data: bytes) -> str | None:
    """Return the media type the *bytes* say they are, or None if unsupported."""
    for prefix, media_type in _MAGIC:
        if data.startswith(prefix):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_password_protected_pdf(data: bytes) -> bool:
    """A locked PDF is rejected with a reason, not silently half-processed."""
    return data.startswith(b"%PDF-") and _PDF_ENCRYPT_RE.search(data) is not None


def estimate_pdf_page_count(data: bytes) -> int | None:
    """Best-effort page count from the raw bytes, or None when unknowable.

    Used only to refuse an obviously over-limit upload before storing it. The
    authoritative count comes from the rasterizer during processing, so a PDF
    whose structure hides its page objects is accepted here and limited there —
    an uncertain count never becomes a confident rejection.
    """
    if not data.startswith(b"%PDF-"):
        return None
    found = len(_PDF_PAGE_RE.findall(data))
    return found or None

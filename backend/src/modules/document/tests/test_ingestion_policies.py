"""Ingestion policies — the §10.2 table, duplicates, and the §6.4 bands.

The transition table is restated here from the specification rather than
imported from the implementation. A test that reads the same dict it is
checking would pass for any table at all.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.modules.content_governance.contracts import (
    CONFIDENCE_POLICY,
    UNIDENTIFIED_DOCUMENT_CLASS_ID,
    BoundaryStatus,
    DocumentClassStatus,
    DocumentVersionRelationship,
    ProcessingFailureReason,
    SourceFileState,
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

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)

#: §10.2 as written in the specification, plus the two re-run rows it implies:
#: the retry its own note requires, and the reprocessing §6.5 contemplates.
LEGAL_TRANSITIONS = [
    (SourceFileState.UPLOAD_INITIATED, SourceFileEvent.BYTES_RECEIVED, SourceFileState.QUARANTINED),
    (SourceFileState.QUARANTINED, SourceFileEvent.CHECKS_PASSED, SourceFileState.VALIDATED),
    (SourceFileState.QUARANTINED, SourceFileEvent.CHECK_FAILED, SourceFileState.REJECTED),
    (
        SourceFileState.VALIDATED,
        SourceFileEvent.IMMUTABLE_WRITE_CONFIRMED,
        SourceFileState.STORED,
    ),
    (SourceFileState.STORED, SourceFileEvent.PROCESSING_STARTED, SourceFileState.PROCESSING),
    (
        SourceFileState.PROCESSING,
        SourceFileEvent.PROCESSING_COMPLETED,
        SourceFileState.PROCESSED,
    ),
    (
        SourceFileState.PROCESSING,
        SourceFileEvent.PROCESSING_FAILED,
        SourceFileState.PROCESSING_FAILED,
    ),
    (
        SourceFileState.PROCESSING_FAILED,
        SourceFileEvent.PROCESSING_STARTED,
        SourceFileState.PROCESSING,
    ),
    (
        SourceFileState.PROCESSED,
        SourceFileEvent.PROCESSING_STARTED,
        SourceFileState.PROCESSING,
    ),
    (
        SourceFileState.PROCESSED,
        SourceFileEvent.LATER_VERSION_IDENTIFIED,
        SourceFileState.SUPERSEDED,
    ),
]


def make_source(
    source_id: str = "src_1",
    *,
    sha256: str = "a" * 64,
    state: SourceFileState = SourceFileState.STORED,
    created_at: datetime = NOW,
) -> SourceFile:
    """A synthetic stored upload. No real client material anywhere in tests."""
    return SourceFile(
        id=source_id,
        user_id="usr_1",
        matter_id="mat_1",
        original_filename="synthetic-title-certificate.pdf",
        media_type="application/pdf",
        byte_length=1024,
        sha256=sha256,
        storage_object_key=f"sources/usr_1/mat_1/{source_id}",
        storage_object_version=f"sha256:{sha256}",
        upload_actor_id="usr_1",
        state=state,
        retention_class="rta.client-evidence",
        created_at=created_at,
        updated_at=created_at,
        page_count=4,
    )


def make_fragment(
    fragment_id: str,
    *,
    document_id: str,
    source_file_id: str,
    page_start: int = 1,
    page_end: int = 2,
    order: int = 0,
) -> DocumentFragment:
    return DocumentFragment(
        id=fragment_id,
        user_id="usr_1",
        matter_id="mat_1",
        detected_document_id=document_id,
        source_file_id=source_file_id,
        page_start=page_start,
        page_end=page_end,
        order_in_document=order,
        boundary_confidence=None,
        boundary_status=BoundaryStatus.CONFIRMED,
        created_at=NOW,
    )


# ── §10.2 state machine ──────────────────────────────────────────────────────


@pytest.mark.parametrize(("current", "event", "expected"), LEGAL_TRANSITIONS)
def test_every_legal_transition_is_permitted(
    current: SourceFileState, event: SourceFileEvent, expected: SourceFileState
) -> None:
    assert next_state(current, event) is expected


@pytest.mark.parametrize(
    ("current", "event"),
    [
        # Skipping quarantine entirely.
        (SourceFileState.UPLOAD_INITIATED, SourceFileEvent.CHECKS_PASSED),
        # Storing bytes that never passed the checks.
        (SourceFileState.QUARANTINED, SourceFileEvent.IMMUTABLE_WRITE_CONFIRMED),
        # Marking a stored file processed without a run.
        (SourceFileState.STORED, SourceFileEvent.PROCESSING_COMPLETED),
        # Reviving a rejected file instead of uploading a new one.
        (SourceFileState.REJECTED, SourceFileEvent.CHECKS_PASSED),
        # Re-processing a superseded source.
        (SourceFileState.SUPERSEDED, SourceFileEvent.PROCESSING_STARTED),
    ],
)
def test_illegal_transitions_are_refused(current: SourceFileState, event: SourceFileEvent) -> None:
    with pytest.raises(IllegalSourceFileTransitionError) as raised:
        next_state(current, event)
    # 422 with both ends named: a client can tell wrong order from wrong file.
    assert raised.value.http_status == 422
    assert raised.value.details == {"fromState": current.value, "event": event.value}


def test_processed_is_reachable_only_from_processing() -> None:
    """The invariant behind honest reporting: nothing else can claim PROCESSED."""
    into_processed = [
        (state, event)
        for state, event, target in LEGAL_TRANSITIONS
        if target is SourceFileState.PROCESSED
    ]
    assert into_processed == [(SourceFileState.PROCESSING, SourceFileEvent.PROCESSING_COMPLETED)]
    for state in SourceFileState:
        for event in SourceFileEvent:
            if state is SourceFileState.PROCESSING:
                continue
            try:
                assert next_state(state, event) is not SourceFileState.PROCESSED
            except IllegalSourceFileTransitionError:
                pass


def test_there_is_no_edited_state_for_source_bytes() -> None:
    """§10.2: a cleaned file is a new source, so no event rewrites one."""
    assert not any(state.value == "EDITED" for state in SourceFileState)


# ── Duplicates (§6.3) ────────────────────────────────────────────────────────


def test_identical_bytes_are_reported_as_an_exact_duplicate() -> None:
    existing = [make_source("src_1", sha256="b" * 64)]
    assert classify_duplicate("b" * 64, existing) is DocumentVersionRelationship.EXACT_DUPLICATE


def test_different_bytes_claim_no_relationship() -> None:
    """A version relationship needs evidence; a filename would not be evidence."""
    existing = [make_source("src_1", sha256="b" * 64)]
    assert classify_duplicate("c" * 64, existing) is None


def test_the_duplicate_points_at_the_copy_that_arrived_first() -> None:
    older = make_source("src_1", sha256="b" * 64, created_at=NOW)
    newer = make_source("src_2", sha256="b" * 64, created_at=NOW + timedelta(minutes=5))
    assert find_exact_duplicate("b" * 64, [newer, older]) is older


def test_a_rejected_upload_is_never_offered_as_the_original() -> None:
    """It holds no bytes, so pointing a lawyer at it would point at nothing."""
    rejected = make_source("src_1", sha256="b" * 64, state=SourceFileState.REJECTED)
    assert find_exact_duplicate("b" * 64, [rejected]) is None
    assert classify_duplicate("b" * 64, [rejected]) is None


# ── §6.4 automation bands ────────────────────────────────────────────────────


def test_boundary_bands_follow_the_rule_pack_thresholds() -> None:
    assert (
        boundary_status_for(CONFIDENCE_POLICY.boundary_auto_threshold, continuity_anomaly=False)
        is BoundaryStatus.CONFIRMED
    )
    assert (
        boundary_status_for(CONFIDENCE_POLICY.boundary_review_floor, continuity_anomaly=False)
        is BoundaryStatus.REVIEW_REQUIRED
    )
    assert (
        boundary_status_for(
            CONFIDENCE_POLICY.boundary_review_floor - 0.01, continuity_anomaly=False
        )
        is BoundaryStatus.CANDIDATE
    )


def test_a_continuity_anomaly_blocks_an_automatic_split() -> None:
    """Missing pages beat any score (§6.3 DOCUMENT_INCOMPLETE)."""
    assert boundary_status_for(0.99, continuity_anomaly=True) is BoundaryStatus.REVIEW_REQUIRED


def test_an_absent_boundary_score_is_not_a_confident_one() -> None:
    assert boundary_status_for(None, continuity_anomaly=False) is BoundaryStatus.CANDIDATE


def test_class_bands_require_both_the_score_and_the_margin() -> None:
    high = CONFIDENCE_POLICY.class_auto_threshold
    margin = CONFIDENCE_POLICY.class_top_two_margin
    assert (
        class_status_for("rta.doc.title_certificate", high, top_two_margin=margin)
        is DocumentClassStatus.AI_ORGANIZED
    )
    # The same score with no reported margin cannot be auto-filed.
    assert (
        class_status_for("rta.doc.title_certificate", high, top_two_margin=0.0)
        is DocumentClassStatus.REVIEW_REQUIRED
    )
    assert (
        class_status_for("rta.doc.title_certificate", 0.5, top_two_margin=margin)
        is DocumentClassStatus.UNIDENTIFIED
    )


def test_unidentified_is_a_first_class_outcome() -> None:
    assert class_status_for(None, 0.99, top_two_margin=0.9) is DocumentClassStatus.UNIDENTIFIED
    assert (
        class_status_for(UNIDENTIFIED_DOCUMENT_CLASS_ID, 0.99, top_two_margin=0.9)
        is DocumentClassStatus.UNIDENTIFIED
    )


# ── The two §6.3 shapes ──────────────────────────────────────────────────────


def test_a_bundle_spanning_two_files_is_representable() -> None:
    fragments = [
        make_fragment("frg_1", document_id="doc_1", source_file_id="src_1", order=0),
        make_fragment("frg_2", document_id="doc_1", source_file_id="src_2", order=1),
    ]
    assert bundle_spans_multiple_sources(fragments) is True


def test_two_ranges_of_one_file_are_still_one_document() -> None:
    fragments = [
        make_fragment(
            "frg_1", document_id="doc_1", source_file_id="src_1", page_start=1, page_end=2, order=0
        ),
        make_fragment(
            "frg_2", document_id="doc_1", source_file_id="src_1", page_start=5, page_end=6, order=1
        ),
    ]
    assert bundle_spans_multiple_sources(fragments) is False
    assert source_contains_multiple_documents(fragments, source_file_id="src_1") is False


def test_several_documents_in_one_pdf_are_representable() -> None:
    fragments = [
        make_fragment("frg_1", document_id="doc_1", source_file_id="src_1"),
        make_fragment("frg_2", document_id="doc_2", source_file_id="src_1"),
    ]
    assert source_contains_multiple_documents(fragments, source_file_id="src_1") is True


# ── Boundary decisions (§6.5) ────────────────────────────────────────────────


def test_a_decision_must_leave_the_document_with_pages() -> None:
    with pytest.raises(BoundaryDecisionRequiresFragmentsError):
        validate_boundary_decision([], page_counts={})


@pytest.mark.parametrize(("start", "end"), [(0, 2), (3, 2), (-1, 1)])
def test_impossible_page_ranges_are_refused(start: int, end: int) -> None:
    ranges = [
        FragmentRange(source_file_id="src_1", page_start=start, page_end=end, order_in_document=0)
    ]
    with pytest.raises(InvalidFragmentRangeError):
        validate_boundary_decision(ranges, page_counts={"src_1": 10})


def test_a_range_past_the_end_of_a_known_file_is_refused() -> None:
    ranges = [FragmentRange(source_file_id="src_1", page_start=1, page_end=11, order_in_document=0)]
    with pytest.raises(InvalidFragmentRangeError):
        validate_boundary_decision(ranges, page_counts={"src_1": 10})


def test_an_unknown_page_count_does_not_overrule_the_lawyer() -> None:
    ranges = [FragmentRange(source_file_id="src_1", page_start=1, page_end=99, order_in_document=0)]
    validate_boundary_decision(ranges, page_counts={"src_1": None})


# ── Content-based validation (§6.2 stage 1) ──────────────────────────────────


def test_media_type_comes_from_the_bytes() -> None:
    assert sniff_media_type(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3") == "application/pdf"
    assert sniff_media_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert sniff_media_type(b"this is not a document") is None


def test_a_password_protected_pdf_is_detectable() -> None:
    locked = b"%PDF-1.7\ntrailer<</Encrypt 12 0 R/Size 20>>"
    assert is_password_protected_pdf(locked) is True
    assert is_password_protected_pdf(b"%PDF-1.7\ntrailer<</Size 20>>") is False


def test_an_unreadable_page_count_is_unknown_rather_than_zero() -> None:
    assert estimate_pdf_page_count(b"%PDF-1.7\nno page objects here") is None
    assert estimate_pdf_page_count(b"not a pdf") is None
    assert estimate_pdf_page_count(b"%PDF-1.7\n/Type /Page x /Type /Page y") == 2


def test_every_failure_reason_has_an_explanation_key() -> None:
    keys = {failure_explanation_key(reason) for reason in ProcessingFailureReason}
    assert len(keys) == len(ProcessingFailureReason)
    assert all(key.startswith("rta.source_file.failure.") for key in keys)

"""Domain errors for document processing."""

from __future__ import annotations

from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    DraftlyError,
    NotFoundError,
)

__all__ = [
    "BoundaryDecisionRequiresFragmentsError",
    "DetectedDocumentNotFoundError",
    "DetectedDocumentStaleError",
    "ExtractionProviderError",
    "IllegalSourceFileTransitionError",
    "InvalidFragmentRangeError",
    "SourceFileNotFoundError",
    "SourceFileNotProcessableError",
    "SourceFileStaleError",
    "SourceFileSupersedeTargetError",
    "SourceFileTooLargeError",
    "SourceObjectImmutableError",
    "SourceObjectIntegrityError",
    "SourceObjectNotFoundError",
    "SourceObjectUnavailableError",
    "SourceStorageNotApprovedError",
    "UnknownDocumentClassError",
    "UnsupportedDocumentError",
    "DocumentReviewNotFoundError",
    "CandidateFieldStaleError",
    "CandidateAlreadyApprovedError",
]


class UnsupportedDocumentError(DomainRuleError):
    """The file type cannot be read by the pipeline (rejected to manual entry)."""

    code = "document_unsupported"
    http_status = 422
    message = "This file type is not supported for automatic extraction."


class ExtractionProviderError(DomainRuleError):
    """The extraction provider failed after retries.

    Deliberately carries no provider response text: raw provider errors can
    embed request payload fragments, and error envelopes reach the client.
    """

    code = "extraction_provider_failed"
    http_status = 502
    message = "The document extraction provider is unavailable."


class SourceFileNotFoundError(NotFoundError):
    """Absent, or owned by another account — deliberately indistinguishable."""

    code = "source_file_not_found"
    message = "The requested source file was not found."


class DetectedDocumentNotFoundError(NotFoundError):
    code = "detected_document_not_found"
    message = "The requested detected document was not found."


class DocumentReviewNotFoundError(NotFoundError):
    code = "document_review_not_found"
    message = "The requested document review was not found."


class CandidateFieldStaleError(ConflictError):
    code = "candidate_field_version_stale"
    message = "The candidate field changed since your last read."


class CandidateAlreadyApprovedError(ConflictError):
    code = "candidate_field_already_approved"
    message = "An approved candidate cannot be edited or approved again."


class IllegalSourceFileTransitionError(DomainRuleError):
    """§10.2 refused the move. 422, never 500 — the request was well formed.

    Notably this is what stops a caller marking an unprocessed file
    ``PROCESSED``: the only route to that state is a run that actually ran.
    """

    code = "rta_source_file_transition_illegal"
    message = "That source-file state transition is not permitted."


class SourceFileTooLargeError(DomainRuleError):
    """Recoverable: the lawyer can split or re-scan the file (§6.2 stage 1)."""

    code = "rta_source_file_too_large"
    message = "This file exceeds the configured upload size limit."


class SourceFileNotProcessableError(DomainRuleError):
    code = "rta_source_file_not_processable"
    message = "This source file is not in a state that can be processed."


class SourceFileSupersedeTargetError(DomainRuleError):
    """The replacement named in a supersede decision cannot stand in for this file."""

    code = "rta_source_file_supersede_target_invalid"
    message = "The replacement source file must be a different file on the same matter."


class InvalidFragmentRangeError(DomainRuleError):
    code = "rta_document_fragment_range_invalid"
    message = "A fragment page range must start at page 1 or later and end on or after it starts."


class BoundaryDecisionRequiresFragmentsError(DomainRuleError):
    """A document with no pages is not a document; rejecting it is a separate act."""

    code = "rta_boundary_decision_requires_fragments"
    message = "A boundary decision must leave the document with at least one fragment."


class UnknownDocumentClassError(DomainRuleError):
    """Only controlled class ids are accepted (§12.4) — no free-text class."""

    code = "rta_document_class_unknown"
    message = "That document class does not exist in the current rule pack."


class SourceObjectImmutableError(ConflictError):
    """Different bytes were offered under a key that already holds an object.

    Original evidence is immutable (plan §5.3 invariant 1), so the write is
    refused rather than resolved in favour of either copy.
    """

    code = "source_object_immutable"
    message = "A different object is already stored under that key."


class SourceObjectNotFoundError(NotFoundError):
    """The recorded object, at the recorded version, is not there to be read.

    Raised when the key is absent and when the pinned version no longer names a
    live object. Both are reported the same way on purpose: from the caller's
    position the evidence of record cannot be produced, and guessing at a
    different version would defeat the point of pinning one.
    """

    code = "source_object_not_found"
    message = "The stored object for this source file could not be found."


class SourceObjectIntegrityError(DraftlyError):
    """Stored bytes did not match the hash recorded when they were uploaded.

    500 rather than 422: the request was well formed and the caller can do
    nothing about it. Something replaced, truncated, or corrupted evidence of
    record, and the honest response is a server fault, not a validation
    complaint. `storage-service.md` §5 forbids silently replacing the object,
    so the read fails and the bytes go nowhere.
    """

    code = "source_object_integrity_failed"
    http_status = 500
    message = "The stored bytes do not match the hash recorded for this source file."


class SourceObjectUnavailableError(DomainRuleError):
    """Object storage could not be reached, or refused the read.

    Carries no provider text, for the same reason `ExtractionProviderError`
    does not: provider messages embed keys and request fragments, and error
    envelopes reach the client.
    """

    code = "source_object_unavailable"
    http_status = 502
    message = "Object storage is unavailable."


class SourceStorageNotApprovedError(CapabilityDeniedError):
    """The real-data gate is closed, so client evidence must not be uploaded.

    Mirrors the provider-data gate on extraction: an unapproved destination is
    a refusal to send, not a failure to store (`storage-service.md` §7).
    """

    code = "storage_real_data_not_approved"
    message = "Storing client evidence in this environment has not been approved."


class SourceFileStaleError(ConflictError):
    code = "source_file_version_stale"
    message = "The source file changed since your last read."


class DetectedDocumentStaleError(ConflictError):
    code = "detected_document_version_stale"
    message = "The detected document changed since your last read."

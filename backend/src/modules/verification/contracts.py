"""The only surface other modules may import from verification.

`matter` needs confirmed values to evaluate the eligibility gates. `check` needs
exact fact versions to pin a check result to. `draft` needs to know which
critical facts are still unconfirmed. Those consumers get read ports. The matter
conversation also receives the review command input for explicit lawyer-confirmed
proposals; authorization and immutable decisions remain owned by verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from src.modules.document.contracts import FactEvidenceLocator


@dataclass(frozen=True)
class ConfirmedFactValue:
    """One lawyer-confirmed value, with the version a caller must pin."""

    fact_id: str
    fact_type_id: str
    value: Any
    version: int
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    transaction_id: str | None = None
    subject_id: str | None = None
    scope_status: str = "legacy-unassigned"


@dataclass(frozen=True)
class FactTierSummary:
    """The state of a matter's fact tier, as the gates need to see it."""

    #: Compatibility only: withheld when eligible values span scopes, even
    #: across different types. Scoped consumers must select from scoped_confirmed.
    confirmed: dict[str, ConfirmedFactValue] = field(default_factory=dict)
    unconfirmed_critical_fact_type_ids: tuple[str, ...] = ()
    conflicted_fact_type_ids: tuple[str, ...] = ()
    #: Compatibility search presence. Scoped negative-conclusion commands must
    #: match eligible search transaction/subject in scoped_confirmed (§6.4, §7.2).
    has_current_search_evidence: bool = False
    #: Lossless eligible values. Consumers must select an explicit scope.
    scoped_confirmed: tuple[ConfirmedFactValue, ...] = ()
    scoped_conflicts: tuple[tuple[str | None, str | None, str], ...] = ()
    scoped_gaps: tuple[tuple[str | None, str | None, str, str], ...] = ()


class ConfirmedFactReadPort(Protocol):
    """Read the confirmed fact tier for one matter."""

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary: ...


class EvidenceReadPort(Protocol):
    """Resolve evidence references for display beside a value or a form field."""

    async def source_pages(
        self, user_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> tuple[tuple[str, int], ...]:
        """Return ``(source_file_id, page_number)`` for each reference, in order."""
        ...


class RequirementEvidencePort(Protocol):
    async def requirement_locators(
        self, user_id: str, matter_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> tuple[FactEvidenceLocator, ...]: ...


@dataclass(frozen=True)
class FactEvidenceInvalidation:
    """Document lifecycle supplies immutable reference IDs, never fact values.

    Implemented by Task 4. Consumers already withhold evidence_stale facts;
    refresh must create new reviewable observations rather than clear history.
    """

    source_file_id: str
    detected_document_ids: tuple[str, ...] = ()
    extraction_run_ids: tuple[str, ...] = ()
    reason: str = "interpretation-changed"


class FactEvidenceInvalidationPort(Protocol):
    async def invalidate(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        change: FactEvidenceInvalidation,
        correlation_id: str,
    ) -> tuple[str, ...]:
        """Mark affected live facts stale in the caller's transaction; return IDs."""
        ...


@dataclass(frozen=True)
class CandidateApprovalInput:
    candidate_id: str
    user_id: str
    matter_id: str
    source_file_id: str
    detected_document_id: str
    extraction_run_id: str
    source_sha256: str
    field_key: str
    value: str
    page_no: int
    model_reported_confidence: float
    review_state: str
    version: int = 1
    correlation_id: str = ""
    original_value: str | None = None


class CandidateApprovalPort(Protocol):
    """Promote one explicitly approved candidate into verification-owned records."""

    async def approve(
        self, candidate: CandidateApprovalInput, *, reviewer_id: str, reviewer_role: str
    ) -> str: ...

    async def project(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> CandidateReviewProjection | None: ...

    async def edit(
        self,
        *,
        user_id: str,
        matter_id: str,
        candidate_id: str,
        value: str,
        expected_version: int,
        reviewer_role: str,
        correlation_id: str,
    ) -> CandidateReviewProjection: ...


@dataclass(frozen=True)
class CandidateReviewProjection:
    value: str
    review_state: str
    version: int


class FactScopeDependenciesPort(Protocol):
    async def fact_ids_for_transaction(
        self, user_id: str, matter_id: str, transaction_id: str
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class ReviewFactInput:
    action: Literal["accept", "correct", "reject", "associate", "edit"]
    expected_version: int
    reason: str | None = None
    value: Any = None
    transaction_id: str | None = None
    subject_id: str | None = None
    expected_scope_token: str | None = None
    resolve_fact_ids: tuple[str, ...] = ()
    evidence: FactEvidenceLocator | None = None

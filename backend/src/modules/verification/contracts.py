"""The only surface other modules may import from verification.

`matter` needs confirmed values to evaluate the eligibility gates. `check` needs
exact fact versions to pin a check result to. `draft` needs to know which
critical facts are still unconfirmed. All three get read ports; none gets the
ability to confirm a fact, which is a human act recorded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ConfirmedFactValue:
    """One lawyer-confirmed value, with the version a caller must pin."""

    fact_id: str
    fact_type_id: str
    value: Any
    version: int
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FactTierSummary:
    """The state of a matter's fact tier, as the gates need to see it."""

    confirmed: dict[str, ConfirmedFactValue] = field(default_factory=dict)
    unconfirmed_critical_fact_type_ids: tuple[str, ...] = ()
    conflicted_fact_type_ids: tuple[str, ...] = ()
    #: True when a dated Title Register / encumbrance search has been confirmed.
    #: Without it, no negative conclusion about a registered interest is
    #: recordable (§6.4, §7.2).
    has_current_search_evidence: bool = False


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


class CandidateApprovalPort(Protocol):
    """Promote one explicitly approved candidate into verification-owned records."""

    async def approve(
        self, candidate: CandidateApprovalInput, *, reviewer_id: str, reviewer_role: str
    ) -> str: ...

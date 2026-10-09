"""Public evidence/candidate reads; document remains the owner of source state."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class FactEvidenceLocator:
    source_file_id: str
    page_number: int
    source_sha256: str
    extraction_run_id: str | None = None
    detected_document_id: str | None = None
    candidate_id: str | None = None
    candidate_version: int | None = None
    snippet: str | None = None
    interpretation_generation: int | None = None


@dataclass(frozen=True)
class FactEvidenceSource:
    locator: FactEvidenceLocator
    page_text: str
    supporting_text: str | None
    precision: str


@dataclass(frozen=True, order=True)
class OriginalSourcePin:
    source_file_id: str
    sha256: str
    storage_version: str
    detected_document_id: str = ""
    interpretation_generation: int = 0
    page_numbers: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        # JSON histories restore arrays as lists; keep pins immutable/hashable.
        object.__setattr__(self, "page_numbers", tuple(self.page_numbers))

    @property
    def precise(self) -> bool:
        return bool(
            self.detected_document_id and self.interpretation_generation > 0 and self.page_numbers
        )


@dataclass(frozen=True)
class RequirementDocument:
    id: str
    version: int
    interpretation_generation: int
    class_id: str | None
    review_ready: bool
    originals: tuple[OriginalSourcePin, ...]
    pages: tuple[FactEvidenceLocator, ...]


class RequirementDocumentPort(Protocol):
    async def requirement_document(
        self, user_id: str, matter_id: str, document_id: str
    ) -> RequirementDocument: ...

    async def validate_evidence(
        self, user_id: str, matter_id: str, evidence: FactEvidenceLocator
    ) -> FactEvidenceSource: ...


@dataclass(frozen=True)
class CandidateObservation:
    id: str
    user_id: str
    matter_id: str
    field_key: str
    original_value: str
    value: str
    confidence: float
    version: int
    created_at: datetime
    evidence: FactEvidenceLocator
    current: bool = True
    approved_fact_id: str | None = None


class DocumentFactPort(Protocol):
    async def list_candidates(
        self, user_id: str, matter_id: str, *, after: str | None = None, limit: int = 100
    ) -> list[CandidateObservation]: ...
    async def get_candidate(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> CandidateObservation | None: ...
    async def validate_evidence(
        self, user_id: str, matter_id: str, evidence: FactEvidenceLocator
    ) -> FactEvidenceSource:
        """Validate original/page availability and the complete extraction grouping.

        Unavailable originals/pages raise DomainRuleError. Missing optional OCR
        yields empty page_text, no supporting_text and page precision. Ownership
        misses remain NotFoundError; changed candidates retain their precondition.
        """
        ...

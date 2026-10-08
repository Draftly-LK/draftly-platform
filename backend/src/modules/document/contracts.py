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


@dataclass(frozen=True)
class FactEvidenceSource:
    locator: FactEvidenceLocator
    page_text: str
    supporting_text: str | None
    precision: str


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
    ) -> FactEvidenceSource: ...

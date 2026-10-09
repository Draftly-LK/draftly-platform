"""Internal ports for the verification module."""

from __future__ import annotations

from typing import Protocol

from src.modules.verification.domain.models import EvidenceReference, ExtractedFact, ReviewDecision
from src.platform.request_context import RequestContext


class VerificationReadRepository(Protocol):
    """Matter-scoped reads used by the verified-facts query service."""

    async def list_live_facts(self, user_id: str, matter_id: str) -> list[ExtractedFact]: ...

    async def list_evidence(
        self, user_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> list[EvidenceReference]: ...


class PractisingNotaryPort(Protocol):
    async def assert_practising(self, ctx: RequestContext) -> None: ...


class FactReviewRepository(VerificationReadRepository, Protocol):
    async def get_fact(self, user_id: str, fact_id: str) -> ExtractedFact | None: ...
    async def create_fact(self, fact: ExtractedFact) -> ExtractedFact: ...
    async def create_evidence(self, evidence: EvidenceReference) -> EvidenceReference: ...
    async def create_decision(
        self, decision: ReviewDecision, *, human: bool = True
    ) -> ReviewDecision: ...
    async def mark_superseded(
        self, user_id: str, fact_id: str, *, superseded_by_fact_id: str
    ) -> None: ...
    async def next_version(
        self,
        user_id: str,
        matter_id: str,
        fact_type_id: str,
        *,
        transaction_id: str | None = None,
        subject_id: str | None = None,
    ) -> int: ...
    async def list_scope(
        self,
        user_id: str,
        matter_id: str,
        fact_type_id: str,
        transaction_id: str | None,
        subject_id: str | None,
    ) -> list[ExtractedFact]: ...
    async def list_page(
        self, user_id: str, matter_id: str, *, after: str | None, limit: int
    ) -> list[ExtractedFact]: ...
    async def by_candidate(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> ExtractedFact | None: ...
    async def has_candidate_history(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> bool: ...
    async def history(
        self, user_id: str, matter_id: str, lineage_id: str, limit: int, *, after: str | None = None
    ) -> list[ExtractedFact]: ...
    async def decisions_for(
        self, user_id: str, matter_id: str, fact_ids: tuple[str, ...], limit: int
    ) -> list[ReviewDecision]: ...

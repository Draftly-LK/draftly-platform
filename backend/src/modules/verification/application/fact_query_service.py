"""Matter-scoped queries over the authoritative fact tier."""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.verification.domain.models import EvidenceReference, ExtractedFact
from src.modules.verification.ports import VerificationReadRepository


@dataclass(frozen=True)
class FactView:
    fact: ExtractedFact
    evidence: tuple[EvidenceReference, ...]


class FactQueryService:
    """Return live facts and their evidence without exposing storage details."""

    def __init__(self, repository: VerificationReadRepository) -> None:
        self._repository = repository

    async def list_facts(self, *, user_id: str, matter_id: str) -> list[FactView]:
        facts = await self._repository.list_live_facts(user_id, matter_id)
        evidence_ids = tuple(
            dict.fromkeys(
                evidence_id for fact in facts for evidence_id in fact.evidence_reference_ids
            )
        )
        evidence = await self._repository.list_evidence(user_id, evidence_ids)
        evidence_by_id = {reference.id: reference for reference in evidence}
        return [
            FactView(
                fact=fact,
                evidence=tuple(
                    evidence_by_id[evidence_id]
                    for evidence_id in fact.evidence_reference_ids
                    if evidence_id in evidence_by_id
                ),
            )
            for fact in facts
        ]

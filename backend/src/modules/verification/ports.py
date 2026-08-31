"""Internal ports for the verification module."""

from __future__ import annotations

from typing import Protocol

from src.modules.verification.domain.models import EvidenceReference, ExtractedFact


class VerificationReadRepository(Protocol):
    """Matter-scoped reads used by the verified-facts query service."""

    async def list_live_facts(self, user_id: str, matter_id: str) -> list[ExtractedFact]: ...

    async def list_evidence(
        self, user_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> list[EvidenceReference]: ...

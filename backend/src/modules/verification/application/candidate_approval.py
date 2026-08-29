"""Human candidate approval into evidence, decision, and confirmed fact records."""

from __future__ import annotations

from datetime import UTC, datetime

from src.modules.content_governance.contracts import (
    FactStatus,
    ReviewTargetType,
    fact_type_for_field,
)
from src.modules.verification.contracts import CandidateApprovalInput
from src.modules.verification.domain.errors import CandidateFactTypeNotFoundError
from src.modules.verification.domain.models import EvidenceReference, ExtractedFact, ReviewDecision
from src.modules.verification.domain.policies import guard_human_confirmation
from src.modules.verification.infrastructure.repository import SqlVerificationRepository
from src.platform import ids


class VerificationCandidateApprovalAdapter:
    def __init__(self, repository: SqlVerificationRepository) -> None:
        self._repo = repository

    async def approve(
        self, candidate: CandidateApprovalInput, *, reviewer_id: str, reviewer_role: str
    ) -> str:
        fact_type = fact_type_for_field(candidate.field_key)
        if fact_type is None:
            raise CandidateFactTypeNotFoundError(fieldKey=candidate.field_key)
        guard_human_confirmation(fact_type.id, confirmed_by_human=True)
        now = datetime.now(tz=UTC)
        evidence_id = ids.new_id(ids.EVIDENCE_REFERENCE)
        decision_id = ids.new_id(ids.REVIEW_DECISION)
        fact_id = ids.new_id(ids.EXTRACTED_FACT)
        await self._repo.create_evidence(
            EvidenceReference(
                id=evidence_id,
                user_id=candidate.user_id,
                matter_id=candidate.matter_id,
                source_file_id=candidate.source_file_id,
                detected_document_id=candidate.detected_document_id,
                page_number=candidate.page_no,
                source_sha256=candidate.source_sha256,
                extraction_run_id=candidate.extraction_run_id,
                created_at=now,
            )
        )
        await self._repo.create_decision(
            ReviewDecision(
                id=decision_id,
                user_id=candidate.user_id,
                matter_id=candidate.matter_id,
                target_type=ReviewTargetType.FACT,
                target_id=fact_id,
                decision="confirmed",
                reviewer_id=reviewer_id,
                reviewer_role=reviewer_role,
                previous_value=candidate.value,
                new_value=candidate.value,
                created_at=now,
            ),
            human=True,
        )
        version = await self._repo.next_version(
            candidate.user_id, candidate.matter_id, fact_type.id
        )
        await self._repo.create_fact(
            ExtractedFact(
                id=fact_id,
                user_id=candidate.user_id,
                matter_id=candidate.matter_id,
                fact_type_id=fact_type.id,
                value=candidate.value,
                status=FactStatus.LAWYER_CONFIRMED,
                model_reported_confidence=candidate.model_reported_confidence,
                evidence_reference_ids=(evidence_id,),
                reviewed_by=reviewer_id,
                reviewed_at=now,
                review_decision_id=decision_id,
                version=version,
                created_at=now,
            )
        )
        return fact_id

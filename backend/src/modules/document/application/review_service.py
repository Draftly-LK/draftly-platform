"""Tenant-scoped review reads and explicit candidate edit/approval commands."""

from __future__ import annotations

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import (
    CAP_FACT_CONFIRM_CRITICAL,
    CAP_FACT_CONFIRM_NONCRITICAL,
    fact_type_for_field,
)
from src.modules.document.domain.errors import (
    CandidateAlreadyApprovedError,
    DocumentReviewNotFoundError,
)
from src.modules.document.domain.v1 import DocumentReview, ReviewCandidate
from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository
from src.modules.document.ports import SourceFileStoragePort
from src.modules.verification.contracts import CandidateApprovalPort


class DocumentReviewService:
    def __init__(
        self,
        *,
        repository: SqlDocumentIngestionRepository,
        storage: SourceFileStoragePort,
        audit: AuditPort,
        candidate_approval: CandidateApprovalPort,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._audit = audit
        self._candidate_approval = candidate_approval

    async def get_review(self, *, user_id: str, detected_document_id: str) -> DocumentReview:
        review = await self._repo.get_document_review(user_id, detected_document_id)
        if review is None:
            raise DocumentReviewNotFoundError()
        return review

    async def get_artifact(self, *, user_id: str, page_id: str, kind: str) -> bytes:
        reference = await self._repo.get_page_artifact_ref(user_id, page_id, kind)
        if reference is None:
            raise DocumentReviewNotFoundError()
        return await self._storage.get(reference[0], version=reference[1])

    async def page_matter_id(self, *, user_id: str, page_id: str) -> str:
        matter_id = await self._repo.get_page_matter_id(user_id, page_id)
        if matter_id is None:
            raise DocumentReviewNotFoundError()
        return matter_id

    async def candidate_matter_id(self, *, user_id: str, candidate_id: str) -> str:
        matter_id = await self._repo.get_candidate_matter_id(user_id, candidate_id)
        if matter_id is None:
            raise DocumentReviewNotFoundError()
        return matter_id

    async def candidate_approval_capability(self, *, user_id: str, candidate_id: str) -> str:
        candidate = await self._repo.get_candidate_approval_input(user_id, candidate_id)
        if candidate is None:
            raise DocumentReviewNotFoundError()
        fact_type = fact_type_for_field(candidate.field_key)
        if fact_type is None:
            raise DocumentReviewNotFoundError()
        if candidate.review_state == "approved":
            raise CandidateAlreadyApprovedError()
        return CAP_FACT_CONFIRM_CRITICAL if fact_type.critical else CAP_FACT_CONFIRM_NONCRITICAL

    async def edit_candidate(
        self,
        *,
        user_id: str,
        actor_id: str,
        candidate_id: str,
        value: str,
        expected_version: int,
        correlation_id: str,
    ) -> ReviewCandidate:
        matter_id = await self.candidate_matter_id(user_id=user_id, candidate_id=candidate_id)
        candidate = await self._repo.update_candidate(
            user_id, candidate_id, value, expected_version
        )
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=AuditAction.RTA_FACT_CORRECTED.value,
                target_type=AuditTargetType.FACT.value,
                target_id=candidate_id,
                before_ref=f"candidate@{expected_version}",
                after_ref=f"unverified@{candidate.version}",
                correlation_id=correlation_id,
            )
        )
        return candidate

    async def approve_candidate(
        self,
        *,
        user_id: str,
        actor_id: str,
        candidate_id: str,
        expected_version: int,
        correlation_id: str,
        reviewer_role: str,
    ) -> ReviewCandidate:
        matter_id = await self.candidate_matter_id(user_id=user_id, candidate_id=candidate_id)
        approval_input = await self._repo.get_candidate_approval_input(user_id, candidate_id)
        if approval_input is None:
            raise DocumentReviewNotFoundError()
        if approval_input.review_state == "approved":
            raise CandidateAlreadyApprovedError()
        fact_id = await self._candidate_approval.approve(
            approval_input, reviewer_id=actor_id, reviewer_role=reviewer_role
        )
        candidate = await self._repo.approve_candidate(
            user_id, candidate_id, actor_id, fact_id, expected_version
        )
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=AuditAction.RTA_FACT_CONFIRMED.value,
                target_type=AuditTargetType.FACT.value,
                target_id=candidate_id,
                before_ref=f"unverified@{expected_version}",
                after_ref=f"approved@{candidate.version}",
                correlation_id=correlation_id,
            )
        )
        return candidate

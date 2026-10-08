"""Tenant-scoped review reads and explicit candidate edit/approval commands."""

from __future__ import annotations

from dataclasses import replace

from src.modules.auth.ports import AuditPort
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
        candidates = []
        for candidate in review.candidates:
            projected = await self._candidate_approval.project(
                user_id, review.matter_id, candidate.id
            )
            candidates.append(
                replace(
                    candidate,
                    edited_value=projected.value,
                    review_state=projected.review_state,
                    version=projected.version,
                )
                if projected
                else candidate
            )
        return replace(review, candidates=tuple(candidates))

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
        reviewer_role: str,
    ) -> ReviewCandidate:
        matter_id = await self.candidate_matter_id(user_id=user_id, candidate_id=candidate_id)
        if actor_id != user_id:
            raise DocumentReviewNotFoundError()
        original = await self._repo.get_candidate_approval_input(user_id, candidate_id)
        if original is None:
            raise DocumentReviewNotFoundError()
        saved = await self._candidate_approval.edit(
            user_id=user_id,
            matter_id=matter_id,
            candidate_id=candidate_id,
            value=value,
            expected_version=expected_version,
            reviewer_role=reviewer_role,
            correlation_id=correlation_id,
        )
        return ReviewCandidate(
            id=candidate_id,
            key=original.field_key,
            candidate_value=original.original_value
            if original.original_value is not None
            else original.value,
            edited_value=saved.value,
            page_no=original.page_no,
            model_reported_confidence=original.model_reported_confidence,
            review_state=saved.review_state,
            version=saved.version,
        )

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
        await self._candidate_approval.approve(
            replace(approval_input, version=expected_version, correlation_id=correlation_id),
            reviewer_id=actor_id,
            reviewer_role=reviewer_role,
        )
        saved = await self._candidate_approval.project(user_id, matter_id, candidate_id)
        if saved is None:
            raise DocumentReviewNotFoundError()
        return ReviewCandidate(
            id=candidate_id,
            key=approval_input.field_key,
            candidate_value=approval_input.original_value
            if approval_input.original_value is not None
            else approval_input.value,
            edited_value=saved.value,
            page_no=approval_input.page_no,
            model_reported_confidence=approval_input.model_reported_confidence,
            review_state=saved.review_state,
            version=saved.version,
        )

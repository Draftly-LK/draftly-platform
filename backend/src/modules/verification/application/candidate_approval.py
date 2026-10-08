"""Compatibility adapter: document review delegates to canonical decisions."""

from src.modules.auth.domain.models import Role
from src.modules.verification.application.review_service import FactReviewService
from src.modules.verification.contracts import CandidateApprovalInput, CandidateReviewProjection
from src.modules.verification.ports import FactReviewRepository
from src.platform.errors import CapabilityDeniedError
from src.platform.request_context import RequestContext


class VerificationCandidateApprovalAdapter:
    def __init__(self, service: FactReviewService, repository: FactReviewRepository) -> None:
        self._service, self._repo = service, repository

    async def project(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> CandidateReviewProjection | None:
        fact = await self._repo.by_candidate(user_id, matter_id, candidate_id)
        if fact is None:
            return None
        return CandidateReviewProjection(
            str(fact.value) if fact.value is not None else "",
            "approved" if fact.is_confirmed and not fact.evidence_stale else "unverified",
            fact.version,
        )

    async def approve(
        self, candidate: CandidateApprovalInput, *, reviewer_id: str, reviewer_role: str
    ) -> str:
        if reviewer_id != candidate.user_id:
            raise CapabilityDeniedError()
        try:
            role = Role(reviewer_role)
        except ValueError as exc:
            raise CapabilityDeniedError() from exc
        ctx = RequestContext(reviewer_id, role, candidate.correlation_id)
        saved = await self._service.decide_candidate(
            ctx,
            candidate.matter_id,
            candidate.candidate_id,
            action="accept",
            expected_version=candidate.version,
        )
        return saved.id

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
    ) -> CandidateReviewProjection:
        try:
            role = Role(reviewer_role)
        except ValueError as exc:
            raise CapabilityDeniedError() from exc
        ctx = RequestContext(user_id, role, correlation_id)
        saved = await self._service.decide_candidate(
            ctx,
            matter_id,
            candidate_id,
            action="edit",
            expected_version=expected_version,
            value=value,
        )
        return CandidateReviewProjection(str(saved.value), "unverified", saved.version)

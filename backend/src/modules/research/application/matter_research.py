"""Authorized, metered grounded answers for the durable matter conversation."""

import asyncio
from typing import Any

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.research.application.service import ResearchService
from src.modules.research.contracts import GroundedResearch
from src.modules.research.domain.models import ComposedClaim, RetrievalStatus, SourceScope
from src.platform.request_context import RequestContext


class MatterResearchService:
    def __init__(self, research: ResearchService, billing: Any, audit: AuditPort) -> None:
        self._research, self._billing, self._audit = research, billing, audit

    async def answer(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        question: str,
        sources: SourceScope,
        operation_id: str,
    ) -> GroundedResearch:
        scope = await self._research.resolve_scope(ctx, "matter", matter_id)
        await self._billing.require_feature_or_raise(ctx.actor_id, "research.enabled")
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter_id,
                actor=ctx.actor_id,
                action="assistant.question-asked",
                target_type="agent_job",
                target_id=operation_id,
                correlation_id=ctx.correlation_id,
            )
        )
        # No configured/approved composer means no provider call or invented answer.
        if self._research.composer is None:
            return GroundedResearch(unavailable_reason="legal_research_unavailable")
        reservation = await self._billing.reserve_usage(
            ctx.actor_id, "research_queries.monthly", 1, operation_id
        )
        try:
            result, _, _ = await self._research.retrieve(question, scope, sources)
            if result.status is RetrievalStatus.UNAVAILABLE:
                await self._billing.release_usage(ctx.actor_id, reservation.id)
                return GroundedResearch(
                    unavailable_reason="legal_research_unavailable",
                    degraded_channels=tuple(result.degraded_channels),
                )
            eligible = [p for p in result.passages if p.text.strip() and p.corpus_version]
            composed = await self._research.composer.compose(question, eligible) if eligible else ()
            available = {
                p.authority_id.upper(): p
                for p in result.passages
                if p.text.strip() and p.corpus_version
            }
            retained = []
            for claim in composed:
                citations = tuple(
                    dict.fromkeys(c.upper() for c in claim.citation_ids if c.upper() in available)
                )
                if (
                    claim.text.strip()
                    and citations
                    and all(c.upper() in available for c in claim.citation_ids)
                ):
                    retained.append(ComposedClaim(claim.text, citations))
            used = {citation for claim in retained for citation in claim.citation_ids}
            answer = GroundedResearch(
                claims=tuple(retained),
                passages=tuple(p for key, p in available.items() if key in used),
                unavailable_reason=None if retained else "insufficient_authority",
                degraded_channels=tuple(result.degraded_channels),
            )
        except asyncio.CancelledError:
            await self._billing.release_usage(ctx.actor_id, reservation.id)
            raise
        except Exception:
            # Failure classes only are surfaced. No provider response or question is logged.
            await self._billing.release_usage(ctx.actor_id, reservation.id)
            answer = GroundedResearch(unavailable_reason="legal_research_unavailable")
        else:
            await self._billing.consume_usage(ctx.actor_id, reservation.id, 1)
        return answer

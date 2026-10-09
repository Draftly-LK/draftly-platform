"""Grounded research boundary for matter tools; no research persistence internals."""

from dataclasses import dataclass
from typing import Protocol

from src.modules.research.domain.models import ComposedClaim, RetrievalPassage, SourceScope
from src.platform.request_context import RequestContext


@dataclass(frozen=True)
class GroundedResearch:
    claims: tuple[ComposedClaim, ...] = ()
    passages: tuple[RetrievalPassage, ...] = ()
    unavailable_reason: str | None = None
    degraded_channels: tuple[str, ...] = ()


class MatterResearchPort(Protocol):
    async def answer(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        question: str,
        sources: SourceScope,
        operation_id: str,
    ) -> GroundedResearch: ...


class LegalSourceAvailabilityPort(Protocol):
    """Fresh permission for exact stored legal passages; unknown/empty fails closed."""

    async def passages_available(
        self, source_ids: tuple[str, ...], *, corpus_version: str
    ) -> bool: ...

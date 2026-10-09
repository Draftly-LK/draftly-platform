"""Grounded research boundary for matter tools; no research persistence internals."""

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from src.modules.corpus_governance.contracts import AuthorityMetadata
from src.modules.research.domain.models import ComposedClaim, RetrievalPassage, SourceScope
from src.platform.request_context import RequestContext


@dataclass(frozen=True)
class LegalDateContext:
    current_date: date
    transaction_id: str | None = None
    association_version: int | None = None
    transaction_date: date | None = None
    fact_id: str | None = None
    fact_version: int | None = None
    reason: Literal["reviewed-date", "date-missing", "date-conflict", "transaction-required"] = (
        "transaction-required"
    )


@dataclass(frozen=True)
class GroundedResearch:
    claims: tuple[ComposedClaim, ...] = ()
    passages: tuple[RetrievalPassage, ...] = ()
    unavailable_reason: str | None = None
    degraded_channels: tuple[str, ...] = ()
    date_context: LegalDateContext | None = None
    authorities: tuple[AuthorityMetadata, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    source_release_version: str | None = None


class MatterResearchPort(Protocol):
    async def answer(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        question: str,
        sources: SourceScope,
        operation_id: str,
        transaction_id: str | None = None,
        association_version: int | None = None,
    ) -> GroundedResearch: ...


class LegalSourceAvailabilityPort(Protocol):
    """Fresh permission for exact stored legal passages; unknown/empty fails closed."""

    async def passages_available(
        self, source_ids: tuple[str, ...], *, corpus_version: str
    ) -> bool: ...

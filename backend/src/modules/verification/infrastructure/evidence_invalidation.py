"""Verification-owned eligibility invalidation; values and decisions stay immutable."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.verification.contracts import FactEvidenceInvalidation
from src.modules.verification.infrastructure.orm import EvidenceReferenceRow, ExtractedFactRow


class SqlFactEvidenceInvalidation:
    def __init__(self, session: AsyncSession, audit: AuditPort) -> None:
        self._session, self._audit = session, audit

    async def invalidate(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        change: FactEvidenceInvalidation,
        correlation_id: str,
    ) -> tuple[str, ...]:
        query = select(EvidenceReferenceRow.id).where(
            EvidenceReferenceRow.user_id == user_id,
            EvidenceReferenceRow.matter_id == matter_id,
        )
        # Logical corrections include every source in that document. A source
        # replacement targets every reference to that source instead.
        if change.detected_document_ids:
            query = query.where(
                EvidenceReferenceRow.detected_document_id.in_(change.detected_document_ids)
            )
        elif change.extraction_run_ids:
            query = query.where(
                EvidenceReferenceRow.extraction_run_id.in_(change.extraction_run_ids)
            )
        else:
            query = query.where(EvidenceReferenceRow.source_file_id == change.source_file_id)
        evidence_ids = set((await self._session.execute(query)).scalars())
        facts = list(
            (
                await self._session.execute(
                    select(ExtractedFactRow).where(
                        ExtractedFactRow.user_id == user_id,
                        ExtractedFactRow.matter_id == matter_id,
                        ExtractedFactRow.superseded_by_fact_id.is_(None),
                    )
                )
            ).scalars()
        )
        affected: set[str] = set()
        while True:
            before = len(affected)
            for fact in facts:
                if evidence_ids.intersection(fact.evidence_reference_ids) or affected.intersection(
                    fact.derivation_input_fact_ids
                ):
                    affected.add(fact.id)
            if len(affected) == before:
                break
        for fact in facts:
            if fact.id not in affected or fact.evidence_stale:
                continue
            fact.evidence_stale = True
            await self._audit.record(
                AuditEventInput(
                    user_id=user_id,
                    matter_id=matter_id,
                    actor=actor_id,
                    action="rta.fact.evidence-stale",
                    target_type="fact",
                    target_id=fact.id,
                    after_ref=change.reason,
                    correlation_id=correlation_id,
                )
            )
        await self._session.flush()
        return tuple(sorted(affected))

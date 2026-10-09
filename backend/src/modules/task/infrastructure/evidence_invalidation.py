"""Invalidate only requirements that relied on changed document interpretations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import DigitalReviewStatus, get_requirement
from src.modules.task.domain.policies import compute_resolution
from src.modules.task.infrastructure.orm import SatisfactionLinkRow
from src.modules.task.infrastructure.repository import SqlChecklistRepository


class SqlDocumentLinkInvalidation:
    def __init__(self, session: AsyncSession, audit: AuditPort) -> None:
        self._session, self._audit = session, audit
        self._repo = SqlChecklistRepository(session)

    async def invalidate_documents(
        self,
        *,
        user_id: str,
        matter_id: str,
        document_ids: tuple[str, ...],
        actor_id: str,
        correlation_id: str,
    ) -> None:
        links = list(
            (
                await self._session.execute(
                    select(SatisfactionLinkRow).where(
                        SatisfactionLinkRow.user_id == user_id,
                        SatisfactionLinkRow.matter_id == matter_id,
                        SatisfactionLinkRow.detected_document_id.in_(document_ids),
                        SatisfactionLinkRow.digital_review.not_in(("SUPERSEDED", "REJECTED")),
                    )
                )
            ).scalars()
        )
        for link in links:
            link.digital_review = "SUPERSEDED"
        for item_id in sorted({link.checklist_item_id for link in links}):
            item = await self._repo.get_item(user_id, item_id)
            if item is None:
                continue
            requirement = get_requirement(item.requirement_definition_id)
            if requirement is None:
                continue
            before = f"{item.digital_review.value}/{item.resolution.value}"
            item.digital_review = DigitalReviewStatus.UNREVIEWED
            item.resolution = compute_resolution(item, requirement)
            await self._repo.update_item(item, item.version)
            await self._audit.record(
                AuditEventInput(
                    user_id=user_id,
                    matter_id=matter_id,
                    actor=actor_id,
                    action="rta.checklist.evidence-stale",
                    target_type="checklist-item",
                    target_id=item_id,
                    before_ref=before,
                    after_ref=f"{item.digital_review.value}/{item.resolution.value}",
                    correlation_id=correlation_id,
                )
            )
        await self._session.flush()

"""Form-owned invalidation preserves every approved snapshot and binding."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.draft.infrastructure.form_commands import SqlGeneratedFormCommandAdapter
from src.modules.draft.infrastructure.orm import GeneratedFormFieldRow


class SqlFormInputInvalidation:
    def __init__(self, session: AsyncSession, audit: AuditPort) -> None:
        self._session, self._audit = session, audit

    async def invalidate_inputs(
        self,
        *,
        user_id: str,
        matter_id: str,
        fact_ids: tuple[str, ...],
        actor_id: str,
        correlation_id: str,
    ) -> None:
        form_ids = (
            await self._session.execute(
                select(GeneratedFormFieldRow.generated_form_id)
                .where(
                    GeneratedFormFieldRow.user_id == user_id,
                    GeneratedFormFieldRow.matter_id == matter_id,
                    GeneratedFormFieldRow.fact_id.in_(fact_ids),
                )
                .distinct()
            )
        ).scalars()
        for form_id in form_ids:
            await SqlGeneratedFormCommandAdapter(self._session).mark_stale(
                user_id=user_id, form_id=form_id, reason="FACT_NO_LONGER_CONFIRMED"
            )
            await self._audit.record(
                AuditEventInput(
                    user_id=user_id,
                    matter_id=matter_id,
                    actor=actor_id,
                    action="rta.form.marked-stale",
                    target_type="generated-form",
                    target_id=form_id,
                    after_ref="interpretation-changed",
                    correlation_id=correlation_id,
                )
            )

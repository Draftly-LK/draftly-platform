"""The two writes the approval module makes into the form aggregate (§10.7).

Approval owns neither the form nor its optimistic concurrency, so it names the
effect it needs and this module performs it. The adapter satisfies
``approval.ports.GeneratedFormCommandPort`` structurally — that protocol is
deliberately not imported, because a module may only import another module's
``contracts``, and the composition root is what connects the two sides.

Nothing here can change a binding. Approving freezes a snapshot; it does not
draft, and it does not populate, correct, or clear a single field.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.domain.enums import GeneratedFormState
from src.modules.draft.domain.errors import GeneratedFormNotFoundError
from src.modules.draft.infrastructure.repository import SqlGeneratedFormRepository


class SqlGeneratedFormCommandAdapter:
    """Applies approval-driven state changes to a generated form."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SqlGeneratedFormRepository(session)

    async def record_approval(
        self,
        *,
        user_id: str,
        form_id: str,
        approval_id: str,
        approved_artifact_hash: str,
        expected_version: int,
    ) -> None:
        """Freeze the snapshot: record the approval and move to ``APPROVED``.

        ``expected_version`` comes from the snapshot the approver actually read,
        so a form edited between preflight and approval raises
        ``GeneratedFormStaleError`` rather than approving a different draft than
        the one that was reviewed.
        """
        form = await self._repo.get_form(user_id, form_id)
        if form is None:
            raise GeneratedFormNotFoundError(formId=form_id)

        await self._repo.update_form(
            replace(
                form,
                state=GeneratedFormState.APPROVED,
                approval_id=approval_id,
                approved_artifact_hash=approved_artifact_hash,
                # The form matched its inputs at the moment of approval. Any
                # staleness recorded before this point is now answered.
                stale_reason=None,
            ),
            expected_version,
        )

    async def mark_stale(self, *, user_id: str, form_id: str, reason: str) -> None:
        """§17 — a correction after approval marks the form stale.

        An approved form goes to ``STALE_AFTER_APPROVAL`` and keeps every
        binding exactly as approved: the snapshot is immutable, and amending it
        requires a new form version. An unapproved form simply returns to
        ``UNRESOLVED`` for re-review.
        """
        form = await self._repo.get_form(user_id, form_id)
        if form is None:
            raise GeneratedFormNotFoundError(formId=form_id)

        target = (
            GeneratedFormState.STALE_AFTER_APPROVAL
            if form.is_approved
            else GeneratedFormState.UNRESOLVED
        )
        if form.state is target and form.stale_reason == reason:
            # Already recorded. Re-writing would burn a version and make the
            # audit trail suggest a second, independent correction.
            return

        await self._repo.update_form(replace(form, state=target, stale_reason=reason), form.version)


__all__ = ["SqlGeneratedFormCommandAdapter"]

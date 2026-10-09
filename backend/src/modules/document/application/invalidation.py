"""Immediate propagation through owning contracts in the caller's matter transaction."""

from src.modules.check.contracts import CheckInputInvalidationPort
from src.modules.draft.contracts import FormInputInvalidationPort
from src.modules.task.contracts import DocumentLinkInvalidationPort
from src.modules.verification.contracts import (
    FactEvidenceInvalidation,
    FactEvidenceInvalidationPort,
)


class DocumentEvidenceInvalidation:
    def __init__(
        self,
        facts: FactEvidenceInvalidationPort,
        links: DocumentLinkInvalidationPort,
        checks: CheckInputInvalidationPort,
        forms: FormInputInvalidationPort,
    ) -> None:
        self._facts, self._links, self._checks, self._forms = facts, links, checks, forms

    async def invalidate(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        change: FactEvidenceInvalidation,
        correlation_id: str,
    ) -> tuple[str, ...]:
        fact_ids = await self._facts.invalidate(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            change=change,
            correlation_id=correlation_id,
        )
        await self._links.invalidate_documents(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            document_ids=change.detected_document_ids,
            correlation_id=correlation_id,
        )
        await self._checks.invalidate_inputs(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            fact_ids=fact_ids,
            correlation_id=correlation_id,
        )
        await self._forms.invalidate_inputs(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            fact_ids=fact_ids,
            correlation_id=correlation_id,
        )
        return fact_ids

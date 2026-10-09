"""Invalidate only consumers bound to the revised transaction in the same matter lock."""

from src.modules.draft.contracts import FormInputInvalidationPort
from src.modules.matter.contracts import ScopeAssociationInvalidationPort
from src.modules.verification.contracts import FactScopeDependenciesPort


class MatterAssociationInvalidation:
    def __init__(
        self,
        checks: ScopeAssociationInvalidationPort,
        facts: FactScopeDependenciesPort,
        forms: FormInputInvalidationPort,
    ) -> None:
        self._checks, self._facts, self._forms = checks, facts, forms

    async def invalidate_scope(
        self,
        *,
        user_id: str,
        matter_id: str,
        transaction_id: str,
        actor_id: str,
        correlation_id: str,
    ) -> None:
        await self._checks.invalidate_scope(
            user_id=user_id,
            matter_id=matter_id,
            transaction_id=transaction_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        fact_ids = await self._facts.fact_ids_for_transaction(user_id, matter_id, transaction_id)
        await self._forms.invalidate_inputs(
            user_id=user_id,
            matter_id=matter_id,
            fact_ids=fact_ids,
            actor_id=actor_id,
            correlation_id=correlation_id,
            reason="SCOPE_ASSOCIATION_CHANGED",
        )

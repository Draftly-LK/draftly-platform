"""Resolve a dated research snapshot exclusively through authorized owner ports."""

from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.modules.matter.contracts import MatterScopePort
from src.modules.research.contracts import LegalDateContext
from src.modules.verification.contracts import ConfirmedFactReadPort
from src.platform.request_context import RequestContext

ATTESTATION_DATE = "rta.instrument.attestation_date"


def current_business_date() -> date:
    return datetime.now(ZoneInfo("Asia/Colombo")).date()


class MatterDateResolver:
    def __init__(
        self,
        scopes: MatterScopePort,
        facts: ConfirmedFactReadPort,
        *,
        today: Callable[[], date] = current_business_date,
    ) -> None:
        self._scopes, self._facts, self._today = scopes, facts, today

    async def resolve(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        transaction_id: str | None = None,
        association_version: int | None = None,
    ) -> LegalDateContext:
        context = LegalDateContext(self._today(), transaction_id, association_version)
        if transaction_id is None:
            return context
        # The existing mutation lock keeps scope revision and fact reads coherent.
        await self._scopes.lock(ctx, matter_id)
        transaction = await self._scopes.get_transaction(ctx, matter_id, transaction_id)
        if association_version is None:
            return context
        if transaction.version != association_version:
            return replace(context, reason="date-conflict")
        summary = await self._facts.summarise(ctx.actor_id, matter_id)
        values = [
            v
            for v in summary.scoped_confirmed
            if v.transaction_id == transaction_id and v.fact_type_id == ATTESTATION_DATE
        ]
        conflicts = any(
            tx == transaction_id and kind == ATTESTATION_DATE
            for tx, _, kind in summary.scoped_conflicts
        )
        gaps = any(
            tx == transaction_id and kind == ATTESTATION_DATE
            for tx, _, kind, _ in summary.scoped_gaps
        )
        if conflicts or len(values) > 1 or any(v.subject_id is not None for v in values):
            return replace(context, reason="date-conflict")
        if gaps or len(values) != 1 or values[0].scope_status != "assigned":
            return replace(context, reason="date-missing")
        fact = values[0]
        try:
            if type(fact.value) is date:
                value = fact.value
            elif isinstance(fact.value, str):
                value = date.fromisoformat(fact.value)
                if value.isoformat() != fact.value:
                    raise ValueError("Non-canonical date")
            else:
                raise ValueError("Missing reviewed date")
        except ValueError:
            return replace(context, reason="date-missing")
        return replace(
            context,
            transaction_date=value,
            fact_id=fact.fact_id,
            fact_version=fact.version,
            reason="reviewed-date",
        )

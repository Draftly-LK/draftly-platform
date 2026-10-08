"""Demo gate overrides, wired by `bootstrap` only when ``DEMO_RELAXED_GATES`` is on.

Two matter-wide rules stop every approval today, and both are open decisions in
the workflow plan rather than settled policy:

- every critical fact type in the rule pack must be confirmed, including ones
  the transaction does not involve (company, mortgage, lease…);
- every blocking checklist requirement must be satisfied, and no confirmed
  document satisfies one yet.

For a synthetic demo the overrides below set both aside. They do not decide
either question, and they leave the form's own guarantees alone: every critical
field the template binds must still come from a lawyer-confirmed fact with
evidence (`CRITICAL_FIELD_UNPOPULATED`, `CRITICAL_FIELD_EVIDENCE_MISSING`),
open legal issues still block, and a transcribed template still cannot back a
registration-ready export. Bootstrap refuses the switch outside the stub
environments.
"""

from __future__ import annotations

from dataclasses import replace

from src.modules.verification.contracts import ConfirmedFactReadPort, FactTierSummary


class FormScopedFactReader:
    """Reports confirmed facts as they are, with no matter-wide unconfirmed list."""

    def __init__(self, inner: ConfirmedFactReadPort) -> None:
        self._inner = inner

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
        summary = await self._inner.summarise(user_id, matter_id)
        return replace(summary, unconfirmed_critical_fact_type_ids=())


class NonBlockingChecklist:
    """Open checklist requirements are shown on the checklist but block nothing."""

    async def blocking_requirement_ids(self, *, user_id: str, matter_id: str) -> tuple[str, ...]:
        _ = user_id, matter_id
        return ()


__all__ = ["FormScopedFactReader", "NonBlockingChecklist"]

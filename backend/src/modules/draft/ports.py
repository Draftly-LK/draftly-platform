"""Draft module ports.

The application service depends on these protocols only. Three of the four
inputs preflight needs already have ports owned by the module that owns the
truth — `verification.contracts.ConfirmedFactReadPort`,
`check.contracts.IssueGatePort`, and `task.contracts.ChecklistBlockerPort` — and
none of them is redeclared here: reading someone else's record through their own
contract is the point of the boundary.

`CandidateFactReadPort` is the one shape that has no owner yet. §9.3 lets a
non-critical field prefill from a high-confidence candidate and §9.4 requires
both sides of a conflict to be shown, and neither is expressible through
`FactTierSummary`, which reports only what is confirmed. The port is declared
here so the rule is implemented and tested rather than deferred; until
`verification` exposes an adapter for it the service runs without one, and every
non-critical field simply stays unresolved instead of quietly guessing.
"""

from __future__ import annotations

from typing import Protocol

from src.modules.draft.domain.models import FactCandidate, GeneratedForm, GeneratedFormField


class CandidateFactReadPort(Protocol):
    """Live, not-yet-confirmed fact values for one matter (§10.5).

    A candidate never reaches a critical field at any confidence; this exists
    for the §9.3 non-critical prefill and the §9.4 conflict display.
    """

    async def candidates(self, user_id: str, matter_id: str) -> tuple[FactCandidate, ...]: ...


class GeneratedFormRepository(Protocol):
    """Forms and their field bindings.

    Every method takes ``user_id`` first because that is the tenancy boundary in
    this deployment: no query reaches a row without it (plan §5.3 invariant 10).
    """

    async def create_form(self, form: GeneratedForm) -> GeneratedForm: ...

    async def get_form(self, user_id: str, form_id: str) -> GeneratedForm | None: ...

    async def list_forms(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[GeneratedForm], str | None]: ...

    async def next_form_version(self, user_id: str, matter_id: str, template_id: str) -> int:
        """The next version for this matter and template.

        An amendment after approval is a new version rather than an edit, so the
        counter is per ``(matter, template)`` and never reused (§9.5).
        """
        ...

    async def update_form(self, form: GeneratedForm, expected_version: int) -> GeneratedForm:
        """Persist and bump ``version``; raise on a stale ``expected_version``."""
        ...

    async def create_fields(self, fields: list[GeneratedFormField]) -> list[GeneratedFormField]: ...

    async def list_fields(self, user_id: str, form_id: str) -> list[GeneratedFormField]: ...

    async def update_field(self, form_field: GeneratedFormField) -> GeneratedFormField:
        """Fields carry no version of their own: the form is the aggregate.

        Concurrency is controlled at the form, so two lawyers editing two fields
        of one draft still meet each other's ``If-Match``.
        """
        ...


__all__ = ["CandidateFactReadPort", "GeneratedFormRepository"]

"""The only surface other modules may import from draft.

`approval` needs to pin an approval to an exact snapshot: which template
version, which form version, which fact versions, which artifact hash, and what
was still unresolved when the lawyer accepted responsibility (§9.6). It gets a
read port carrying exactly that, and no way to generate a form, resolve a field,
or move a state — approving is a separate legal act recorded by its own module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.modules.content_governance.contracts import GeneratedFormState


@dataclass(frozen=True)
class BoundFact:
    """One canonical fact bound into a form, at the version that was bound."""

    field_id: str
    fact_id: str
    version: int
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FormSnapshot:
    """Everything an approval must pin itself to (§9.6).

    ``unresolved_field_ids`` travels with the snapshot rather than being derived
    later: §9.6 requires the approval to carry the unresolved warnings the
    lawyer accepted, and a list recomputed after the fact would be a different
    list.
    """

    form_id: str
    user_id: str
    matter_id: str
    state: GeneratedFormState
    template_id: str
    template_version: str
    form_version: int
    subtype_id: str
    rule_pack_version: str
    draft_artifact_hash: str | None
    approved_artifact_hash: str | None
    approval_id: str | None
    stale_reason: str | None
    version: int
    #: Critical fields only. A non-critical prefill is not part of what an
    #: approval certifies; a critical binding is (§9.3).
    critical_fact_bindings: tuple[BoundFact, ...] = field(default_factory=tuple)
    unresolved_field_ids: tuple[str, ...] = field(default_factory=tuple)


class GeneratedFormReadPort(Protocol):
    """Read one form's snapshot. Returns ``None`` for absent or foreign."""

    async def get_form_snapshot(self, user_id: str, form_id: str) -> FormSnapshot | None: ...


class FormInputInvalidationPort(Protocol):
    async def invalidate_inputs(
        self,
        *,
        user_id: str,
        matter_id: str,
        fact_ids: tuple[str, ...],
        actor_id: str,
        correlation_id: str,
        reason: str = "FACT_NO_LONGER_CONFIRMED",
    ) -> None: ...

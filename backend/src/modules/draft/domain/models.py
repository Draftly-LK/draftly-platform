"""Generated-form and generated-form-field entities.

A generated form is a *binding record*, not a rendering. It stores which
template version was used, which fact version each field was populated from, and
which page-level evidence backs it. The rendered artifact is derived from that
record; the record is what an approval pins to and what an auditor reads (§9.3,
§9.6).

Two properties carry the legal weight:

``GeneratedFormField.is_populated`` and ``is_unresolved`` are mutually exclusive
by construction — a field either carries a value or carries a named reason why
it does not, and never both (§9.4). The database enforces the same pair.

``GeneratedForm.is_approved`` is what makes a snapshot immutable. After it, no
field decision, no regeneration, and no staleness sweep may edit this row's
bindings; an amendment is a new ``form_version`` (§9.5, §10.7).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.modules.content_governance.contracts import (
    FactStatus,
    GeneratedFormState,
    UnresolvedReason,
)
from src.modules.draft.contracts import FormScope

#: §9.4 — a missing value renders a named token, never blank space and never
#: plausible filler. The exact shape is part of the contract: the lawyer must be
#: able to search a working draft for what is still missing.
UNRESOLVED_TOKEN_PREFIX = "[[UNRESOLVED: "
UNRESOLVED_TOKEN_SUFFIX = "]]"


def unresolved_token(field_id: str) -> str:
    """Render the §9.4 token for one field, e.g. ``[[UNRESOLVED: transferee_nic]]``."""
    return f"{UNRESOLVED_TOKEN_PREFIX}{field_id}{UNRESOLVED_TOKEN_SUFFIX}"


class StaleReason(str, enum.Enum):
    """Why a form stopped matching the record it was generated from (§10.7).

    Kept as a closed enum rather than free text because the reason drives what
    the lawyer must do next: a superseded fact needs re-review of one field, a
    template change needs a new form version against the new template.
    """

    #: A fact bound into the form has been corrected; the bound version is no
    #: longer live (§10.5).
    FACT_SUPERSEDED = "FACT_SUPERSEDED"
    #: A fact bound into the form is no longer in the confirmed tier at all —
    #: the confirmation was withdrawn or the fact type left the catalogue.
    FACT_NO_LONGER_CONFIRMED = "FACT_NO_LONGER_CONFIRMED"
    TEMPLATE_VERSION_CHANGED = "TEMPLATE_VERSION_CHANGED"
    RULE_PACK_VERSION_CHANGED = "RULE_PACK_VERSION_CHANGED"
    #: The checklist recompiled, so the evidence scope the draft was prepared
    #: under has moved. Declared by the caller: this module cannot observe it.
    CHECKLIST_RECOMPILED = "CHECKLIST_RECOMPILED"


@dataclass(frozen=True)
class FactCandidate:
    """One live, not-yet-confirmed value for a fact type (§10.5).

    Candidates never populate a critical field at any confidence (§6.4). They
    exist here for two narrower jobs: a §9.3 non-critical prefill, and showing
    both sides of a conflict to the lawyer (§9.4).
    """

    fact_id: str
    fact_type_id: str
    value: Any
    version: int
    status: FactStatus
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    #: The provider's own estimate. It routes work to a human; it verifies
    #: nothing (§6.4).
    model_reported_confidence: float | None = None
    #: Whether the page this was read from produced clean OCR. Required by
    #: `may_prefill_noncritical`, and False when nothing reported it.
    clean_ocr: bool = False


@dataclass
class GeneratedForm:
    """One drafted instrument, pinned to the versions that produced it (§9.2)."""

    id: str
    user_id: str
    matter_id: str
    template_id: str
    template_version: str
    form_version: int
    state: GeneratedFormState
    subtype_id: str
    rule_pack_version: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    #: Digest over the binding record, so "which draft was this?" is answerable
    #: without keeping every rendered artifact (§9.6).
    draft_artifact_hash: str | None = None
    #: Written by the approval module when it freezes the snapshot. This module
    #: never sets it: approving is not drafting.
    approved_artifact_hash: str | None = None
    approval_id: str | None = None
    stale_reason: str | None = None
    version: int = 1
    scope: FormScope | None = None
    missing_causes: dict[str, str] = field(default_factory=dict)
    predecessor_form_id: str | None = None

    @property
    def is_approved(self) -> bool:
        """Whether an approval has frozen this form's bindings (§10.7).

        ``APPROVAL_PENDING`` is deliberately absent: nothing is frozen until the
        approval event exists, and a form awaiting one still returns to
        ``UNRESOLVED`` when its inputs move.
        """
        return self.state in _APPROVED_STATES or self.approved_artifact_hash is not None

    @property
    def is_stale(self) -> bool:
        return self.state in {
            GeneratedFormState.STALE_TEMPLATE,
            GeneratedFormState.STALE_AFTER_APPROVAL,
        }


_APPROVED_STATES: frozenset[GeneratedFormState] = frozenset(
    {
        GeneratedFormState.APPROVED,
        GeneratedFormState.EXPORTED,
        GeneratedFormState.SUBMITTED,
        GeneratedFormState.REGISTERED,
        GeneratedFormState.STALE_AFTER_APPROVAL,
    }
)


@dataclass
class GeneratedFormField:
    """One form field and the exact evidence chain behind its value (§9.3).

    ``fact_version`` is stored beside ``fact_id`` rather than being looked up at
    render time: a correction creates a new fact version, and the point of this
    row is to record which version was actually bound, not which one is current.
    """

    id: str
    user_id: str
    matter_id: str
    generated_form_id: str
    field_id: str
    critical: bool
    required: bool
    order: int
    fact_id: str | None = None
    fact_version: int | None = None
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    rendered_value: str | None = None
    unresolved_reason: UnresolvedReason | None = None
    transformation_id: str | None = None
    review_decision_id: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    @property
    def is_populated(self) -> bool:
        return self.rendered_value is not None

    @property
    def is_unresolved(self) -> bool:
        return self.unresolved_reason is not None

    @property
    def is_reviewed(self) -> bool:
        return self.review_decision_id is not None

    @property
    def awaiting_confirmation(self) -> bool:
        """Populated, but no lawyer has decided this field yet (§9.3).

        Both ways a value can arrive need the lawyer's confirmation before
        approval — a canonical fact and an AI prefill alike. Whether the value
        is an *AI suggestion* is a narrower question that needs the confirmed
        fact tier, so `policies.is_ai_suggested` answers it, not this row.
        """
        return self.is_populated and not self.is_reviewed

    def display_value(self) -> str:
        """What the working draft renders — the value, or the §9.4 token."""
        return (
            self.rendered_value
            if self.rendered_value is not None
            else unresolved_token(self.field_id)
        )


__all__ = [
    "UNRESOLVED_TOKEN_PREFIX",
    "UNRESOLVED_TOKEN_SUFFIX",
    "FactCandidate",
    "GeneratedForm",
    "GeneratedFormField",
    "StaleReason",
    "unresolved_token",
]

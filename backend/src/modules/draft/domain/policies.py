"""The generation rules. This file is the correctness core of the module.

Six rules carry the legal safety of drafting (§9.3, §9.4), and each is a named
function here rather than a comment somewhere in the service:

1. **Never invent a value.** A critical field is populated only from a fact
   whose status is ``LAWYER_CONFIRMED`` or ``LOCKED_FOR_FORM``. Anything else
   renders the §9.4 token ``[[UNRESOLVED: <field_id>]]`` and records a reason.
   Blank space and plausible filler are both prohibited, which is why
   `resolve_field` has no branch that returns an empty string.
2. **A non-critical field may prefill from a high-confidence, non-conflicting
   candidate**, badged as AI-suggested. The threshold is not decided here:
   `content_governance.contracts.may_prefill_noncritical` owns it.
3. **A populated critical field carries its fact id, its fact version, and its
   page-level evidence.** A populated critical field with no evidence is a
   domain error, not a quiet downgrade — an unevidenced confirmed fact is a
   defect in the record and must surface where it can be fixed.
4. **Two live conflicting facts leave the field unresolved** with
   ``FACT_CONFLICTED``, and both candidates travel to the UI side by side. No
   source is silently preferred (§10.5).
5. **A negative proposition is never populated because no document mentions the
   issue.** A fact type marked ``negative_requires_search_evidence`` may render a
   negative value only when a dated register search has been confirmed.
6. **Signature, witness appearance, original inspection, and attestation are
   never pre-certified.** Those fields are unresolved at generation and no field
   decision can populate them.

``UnresolvedReason`` is a closed, governed enum of five members and cannot be
extended from here, so ``NO_FACT`` carries every "there is no usable canonical
value behind this field" case: no fact type on the mapping, no fact at all, an
unevidenced negative, a value with no declared rendering, and a withheld
pre-certification. ``FACT_NOT_CONFIRMED``, ``FACT_CONFLICTED``, and
``FACT_SUPERSEDED`` stay exact.
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from src.modules.check.contracts import IssueGateSummary
from src.modules.content_governance.contracts import (
    FormFieldMapping,
    FormTemplateDefinition,
    GeneratedFormState,
    SubtypeDecisionStatus,
    SubtypeDefinition,
    TemplateStatus,
    UnresolvedReason,
    get_fact_type,
    may_prefill_noncritical,
    templates_for_subtype,
)
from src.modules.draft.domain.errors import (
    ApprovedFormImmutableError,
    CriticalFieldEvidenceMissingError,
    CriticalFieldRequiresConfirmedFactError,
    FieldDecisionReasonRequiredError,
    FieldNotPopulatedError,
    FieldValueRequiredError,
    FormGenerationBlockedError,
    LawyerAuthoredTextNotPermittedError,
    PreCertificationNotPermittedError,
    SubtypeNotConfirmedError,
    TemplateNotAvailableForSubtypeError,
)
from src.modules.draft.domain.models import (
    FactCandidate,
    GeneratedForm,
    GeneratedFormField,
    StaleReason,
)
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary

#: The only transformation this module performs. Mirrors the governed
#: vocabulary in `content_governance`'s form registry, which does not re-export
#: the constant; a mapping that did not declare it stays lawyer-entered rather
#: than being populated by a transformation this module invented (§9.3).
TRANSFORM_EXACT_COPY = "EXACT_COPY"

#: §9.4 — a working draft exists for internal review only and says so on every
#: page. The wording itself is product copy owned by the team, so what travels
#: is the translation key.
DRAFT_WATERMARK_KEY = "rta.form.watermark.draft_not_approved"

#: Fact types and field-id markers that record an execution or certification
#: *act* rather than a particular known before it (§9.3 row 5). The notary's
#: name and code are deliberately absent: naming the notary who will attest is
#: ordinary drafting, whereas asserting that the attestation happened is not.
PRE_CERTIFICATION_FACT_TYPE_IDS: frozenset[str] = frozenset({"rta.instrument.attestation_date"})
_PRE_CERTIFICATION_FIELD_MARKERS: tuple[str, ...] = (
    "signature",
    "witness",
    "attestation_date",
    "inspection",
    "execution_date",
    "seal",
)

#: Enum members that assert an absence rather than a positive finding. Neither
#: may populate a form field without a confirmed dated search behind it:
#: ``NO_EVIDENCE_REVIEWED`` asserts nothing at all, and
#: ``NOT_FOUND_IN_CURRENT_SEARCH`` is exactly the negative proposition §6.4
#: refuses to infer from silence.
_NEGATIVE_ASSERTIONS: frozenset[str] = frozenset(
    {"NO_EVIDENCE_REVIEWED", "NOT_FOUND_IN_CURRENT_SEARCH"}
)


# ── Field resolution (§9.3) ──────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldResolution:
    """What the rules decided about one field, before it becomes a row."""

    mapping: FormFieldMapping
    rendered_value: str | None = None
    unresolved_reason: UnresolvedReason | None = None
    fact_id: str | None = None
    fact_version: int | None = None
    evidence_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    transformation_id: str | None = None
    ai_suggested: bool = False
    #: Both sides of a §9.4 conflict, in the order the reader receives them.
    #: Never narrowed to one: choosing between them is the lawyer's act.
    conflicting_candidates: tuple[FactCandidate, ...] = field(default_factory=tuple)


def is_pre_certification(mapping: FormFieldMapping) -> bool:
    """Whether this field records an act that only a human event can create."""
    if mapping.fact_type_id in PRE_CERTIFICATION_FACT_TYPE_IDS:
        return True
    return any(marker in mapping.field_id for marker in _PRE_CERTIFICATION_FIELD_MARKERS)


def render_exact_copy(value: Any) -> str | None:
    """Render a confirmed value as an exact copy, or refuse.

    A boolean is refused on purpose. A lawyer's yes/no conclusion has no
    prescribed rendering in the Gazette forms, and choosing one ("Yes", "ඔව්")
    would be authoring form copy — which is human-owned. The field stays
    unresolved and the lawyer writes what the form actually requires.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, int | float | Decimal):
        return str(value)
    return None


def asserts_negative(value: Any) -> bool:
    """Whether this value states an absence rather than a positive finding."""
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return value.strip().upper() in _NEGATIVE_ASSERTIONS
    return False


def _negative_without_search_evidence(
    mapping: FormFieldMapping, value: Any, *, has_current_search_evidence: bool
) -> bool:
    """Rule 5 — a negative proposition needs a current search behind it (§6.4)."""
    if mapping.fact_type_id is None or has_current_search_evidence:
        return False
    fact_type = get_fact_type(mapping.fact_type_id)
    if fact_type is None or not fact_type.negative_requires_search_evidence:
        return False
    return asserts_negative(value)


def _best_prefill_candidate(candidates: Sequence[FactCandidate]) -> FactCandidate | None:
    """The candidate a §9.3 non-critical prefill may use, if any.

    Highest reported confidence wins, with the fact id as a tie-break so the
    same inputs always produce the same draft. `may_prefill_noncritical` decides
    whether it may be used at all; this only orders the applicants.
    """
    usable = [
        candidate for candidate in candidates if candidate.model_reported_confidence is not None
    ]
    if not usable:
        return None
    return max(usable, key=lambda c: (c.model_reported_confidence or 0.0, c.fact_id))


def _unresolved(
    mapping: FormFieldMapping,
    reason: UnresolvedReason,
    *,
    candidates: tuple[FactCandidate, ...] = (),
) -> FieldResolution:
    return FieldResolution(
        mapping=mapping, unresolved_reason=reason, conflicting_candidates=candidates
    )


def resolve_field(
    mapping: FormFieldMapping,
    *,
    confirmed: ConfirmedFactValue | None,
    candidates: tuple[FactCandidate, ...] = (),
    conflicted: bool = False,
    has_current_search_evidence: bool = False,
) -> FieldResolution:
    """Decide one field's binding. Pure; raises only on an unevidenced critical fact.

    The order of the guards is the order of the rules: nothing that must never
    be pre-certified reaches the fact tier at all, and a conflict is answered
    before any value is chosen — because choosing one would *be* the silent
    preference §10.5 forbids.
    """
    if is_pre_certification(mapping):
        return _unresolved(mapping, UnresolvedReason.NO_FACT)
    if conflicted:
        return _unresolved(mapping, UnresolvedReason.FACT_CONFLICTED, candidates=candidates)
    if (
        mapping.fact_type_id is None
        or TRANSFORM_EXACT_COPY not in mapping.allowed_transformation_ids
    ):
        # No canonical fact behind the field, or no transformation this module
        # is permitted to apply. Either way the value is the lawyer's to enter.
        return _unresolved(mapping, UnresolvedReason.NO_FACT)

    if confirmed is not None:
        return _from_confirmed(
            mapping, confirmed, has_current_search_evidence=has_current_search_evidence
        )
    if mapping.critical:
        # Rule 1. No confidence value, corroboration count, or candidate reaches
        # a critical field — `may_auto_confirm_critical_fact` is False at 1.00.
        return _unresolved(
            mapping,
            UnresolvedReason.FACT_NOT_CONFIRMED if candidates else UnresolvedReason.NO_FACT,
        )
    return _from_candidate(
        mapping, candidates, has_current_search_evidence=has_current_search_evidence
    )


def _from_confirmed(
    mapping: FormFieldMapping,
    confirmed: ConfirmedFactValue,
    *,
    has_current_search_evidence: bool,
) -> FieldResolution:
    if _negative_without_search_evidence(
        mapping, confirmed.value, has_current_search_evidence=has_current_search_evidence
    ):
        return _unresolved(mapping, UnresolvedReason.NO_FACT)
    rendered = render_exact_copy(confirmed.value)
    if rendered is None:
        return _unresolved(mapping, UnresolvedReason.NO_FACT)
    if mapping.critical and not confirmed.evidence_reference_ids:
        # Rule 3. Refusing loudly rather than rendering an unresolved token: an
        # unevidenced confirmed critical fact is a defect in the record, and a
        # token would make it look like ordinary missing evidence.
        raise CriticalFieldEvidenceMissingError(
            fieldId=mapping.field_id,
            factId=confirmed.fact_id,
            factTypeId=confirmed.fact_type_id,
        )
    return FieldResolution(
        mapping=mapping,
        rendered_value=rendered,
        fact_id=confirmed.fact_id,
        fact_version=confirmed.version,
        evidence_reference_ids=confirmed.evidence_reference_ids,
        transformation_id=TRANSFORM_EXACT_COPY,
    )


def _from_candidate(
    mapping: FormFieldMapping,
    candidates: tuple[FactCandidate, ...],
    *,
    has_current_search_evidence: bool,
) -> FieldResolution:
    """Rule 2 — a non-critical administrative field may show a suggestion."""
    candidate = _best_prefill_candidate(candidates)
    if candidate is None:
        return _unresolved(
            mapping,
            UnresolvedReason.FACT_NOT_CONFIRMED if candidates else UnresolvedReason.NO_FACT,
        )
    if _negative_without_search_evidence(
        mapping, candidate.value, has_current_search_evidence=has_current_search_evidence
    ):
        # Rule 5 applies with more force here: a model's reading of silence is
        # not a negative finding at any confidence.
        return _unresolved(mapping, UnresolvedReason.NO_FACT)
    if not may_prefill_noncritical(
        candidate.model_reported_confidence or 0.0,
        conflicting=False,
        clean_ocr=candidate.clean_ocr,
    ):
        return _unresolved(mapping, UnresolvedReason.FACT_NOT_CONFIRMED)
    rendered = render_exact_copy(candidate.value)
    if rendered is None:
        return _unresolved(mapping, UnresolvedReason.FACT_NOT_CONFIRMED)
    return FieldResolution(
        mapping=mapping,
        rendered_value=rendered,
        fact_id=candidate.fact_id,
        fact_version=candidate.version,
        evidence_reference_ids=candidate.evidence_reference_ids,
        transformation_id=TRANSFORM_EXACT_COPY,
        ai_suggested=True,
    )


def resolve_template(
    template: FormTemplateDefinition,
    *,
    facts: FactTierSummary,
    candidates: Iterable[FactCandidate] = (),
) -> tuple[FieldResolution, ...]:
    """Resolve every field of one template against the matter's fact tier."""
    by_type: dict[str, list[FactCandidate]] = {}
    for candidate in candidates:
        by_type.setdefault(candidate.fact_type_id, []).append(candidate)
    conflicted = set(facts.conflicted_fact_type_ids)
    return tuple(
        resolve_field(
            mapping,
            confirmed=facts.confirmed.get(mapping.fact_type_id or ""),
            candidates=tuple(by_type.get(mapping.fact_type_id or "", ())),
            conflicted=mapping.fact_type_id in conflicted,
            has_current_search_evidence=facts.has_current_search_evidence,
        )
        for mapping in sorted(template.field_mappings, key=lambda m: (m.order, m.field_id))
    )


def is_ai_suggested(
    form_field: GeneratedFormField, mapping: FormFieldMapping, facts: FactTierSummary
) -> bool:
    """Whether this value is a §9.3 prefill rather than a confirmed fact.

    A critical field can only ever hold a lawyer-confirmed fact, so it is never
    an AI suggestion. A non-critical field is one when the fact it is bound to
    is not the confirmed tier's value for that fact type — which is exactly the
    case `may_prefill_noncritical` produced. Badging a lawyer-confirmed value
    "AI suggested" would be as misleading as the reverse, so the comparison is
    made against the tier rather than guessed from the row.
    """
    if not form_field.is_populated or form_field.critical or form_field.is_reviewed:
        return False
    if mapping.fact_type_id is None or form_field.fact_id is None:
        return False
    confirmed = facts.confirmed.get(mapping.fact_type_id)
    return confirmed is None or confirmed.fact_id != form_field.fact_id


def guard_populated_critical_field(field_row: GeneratedFormField) -> None:
    """Rule 3, enforced on the row as well as on the resolution.

    Called before a populated critical field is persisted, so a future caller
    that assembles a row by another route still cannot store a critical value
    with no evidence chain behind it.
    """
    if not (field_row.critical and field_row.is_populated):
        return
    if (
        field_row.fact_id is None
        or field_row.fact_version is None
        or not field_row.evidence_reference_ids
    ):
        raise CriticalFieldEvidenceMissingError(
            fieldId=field_row.field_id, formId=field_row.generated_form_id
        )


# ── Template selection and generation gates (§9.1) ───────────────────────────


def permitted_template_ids(subtype: SubtypeDefinition) -> tuple[str, ...]:
    """Every template this confirmed instrument may produce.

    The prescribed instrument itself, plus the operational companions the
    taxonomy links to it — a transfer produces Form 8 and the Ti.Re.31
    title-certificate application. Derived from the rule pack every time, so a
    client-supplied id can only ever select from this set (§9.1).
    """
    return tuple(
        dict.fromkeys(
            (
                *(t.id for t in templates_for_subtype(subtype.id)),
                *subtype.companion_template_ids,
            )
        )
    )


def select_template(subtype: SubtypeDefinition, requested_template_id: str | None) -> str:
    """Choose the template id for this subtype, or refuse.

    With no request, the single prescribed instrument is used; a subtype that
    offers more than one candidate must be told which, because guessing between
    an instrument and its companion application is guessing at the legal act.
    """
    permitted = permitted_template_ids(subtype)
    if not permitted:
        raise TemplateNotAvailableForSubtypeError(
            subtypeId=subtype.id, releaseTier=subtype.release_tier.value
        )
    if requested_template_id is None:
        # The taxonomy's own pointer at the prescribed instrument. A companion
        # application (Ti.Re.31 beside a transfer) is drafted only when asked
        # for by name: which document is the legal instrument is not a guess.
        prescribed = subtype.form_template_id
        if prescribed is not None and prescribed in permitted:
            return prescribed
        if len(permitted) > 1:
            raise TemplateNotAvailableForSubtypeError(
                "This instrument selects more than one form; name the template to draft.",
                subtypeId=subtype.id,
                permittedTemplateIds=list(permitted),
            )
        return permitted[0]
    if requested_template_id not in permitted:
        raise TemplateNotAvailableForSubtypeError(
            subtypeId=subtype.id,
            requestedTemplateId=requested_template_id,
            permittedTemplateIds=list(permitted),
        )
    return requested_template_id


def guard_generation(
    *,
    subtype_id: str | None,
    subtype_decision_status: SubtypeDecisionStatus,
    issue_gates: IssueGateSummary,
) -> str:
    """Refuse to draft from a provisional classification or over a blocker.

    Returns the confirmed subtype id, so no caller downstream has to re-assert
    that it is present.

    A subtype that needs a declared legal basis cannot reach
    ``LAWYER_CONFIRMED`` without one — `matter` refuses the confirmation itself
    — so this gate covers §9.1's "confirmed exact subtype" and §14.6's
    "unconfirmed exact form/template" without widening the matter contract.
    """
    if subtype_id is None or subtype_decision_status is not SubtypeDecisionStatus.LAWYER_CONFIRMED:
        raise SubtypeNotConfirmedError(subtypeDecisionStatus=subtype_decision_status.value)
    if issue_gates.blocks_draft_generation:
        raise FormGenerationBlockedError(
            openBlockingIssueIds=list(issue_gates.open_blocking_issue_ids),
            openStatutoryBlockerIds=list(issue_gates.open_statutory_blocker_ids),
        )
    return subtype_id


# ── Preflight (§9.4, §14.6) ──────────────────────────────────────────────────


class PreflightGate(str, enum.Enum):
    """The earliest gate an item stops. A later gate implies the earlier ones."""

    REVIEW_READY = "REVIEW_READY"
    APPROVAL = "APPROVAL"
    REGISTRATION_READY = "REGISTRATION_READY"


class PreflightCode(str, enum.Enum):
    """Why the form is not ready, in the vocabulary §14.6 uses."""

    UNRESOLVED_REQUIRED_FIELD = "UNRESOLVED_REQUIRED_FIELD"
    FIELD_CONFLICTED = "FIELD_CONFLICTED"
    FORM_STALE = "FORM_STALE"
    OPEN_BLOCKING_ISSUE = "OPEN_BLOCKING_ISSUE"
    OPEN_STATUTORY_BLOCKER = "OPEN_STATUTORY_BLOCKER"
    OPEN_HIGH_RISK_ISSUE = "OPEN_HIGH_RISK_ISSUE"
    CRITICAL_FACT_UNCONFIRMED = "CRITICAL_FACT_UNCONFIRMED"
    CHECKLIST_REQUIREMENT_BLOCKING = "CHECKLIST_REQUIREMENT_BLOCKING"
    UNACKNOWLEDGED_WARNING_ISSUE = "UNACKNOWLEDGED_WARNING_ISSUE"
    TEMPLATE_NOT_VALIDATED = "TEMPLATE_NOT_VALIDATED"
    SOURCE_REVERIFICATION_REQUIRED = "SOURCE_REVERIFICATION_REQUIRED"
    # Warnings — surfaced, never blocking.
    UNRESOLVED_OPTIONAL_FIELD = "UNRESOLVED_OPTIONAL_FIELD"
    FIELD_AWAITING_CONFIRMATION = "FIELD_AWAITING_CONFIRMATION"
    TEMPLATE_SOURCE_DEFECT = "TEMPLATE_SOURCE_DEFECT"


_GATES: dict[PreflightCode, PreflightGate] = {
    PreflightCode.UNRESOLVED_REQUIRED_FIELD: PreflightGate.REVIEW_READY,
    PreflightCode.FIELD_CONFLICTED: PreflightGate.REVIEW_READY,
    PreflightCode.FORM_STALE: PreflightGate.REVIEW_READY,
    PreflightCode.OPEN_BLOCKING_ISSUE: PreflightGate.REVIEW_READY,
    PreflightCode.OPEN_STATUTORY_BLOCKER: PreflightGate.REVIEW_READY,
    PreflightCode.OPEN_HIGH_RISK_ISSUE: PreflightGate.APPROVAL,
    PreflightCode.CRITICAL_FACT_UNCONFIRMED: PreflightGate.APPROVAL,
    PreflightCode.CHECKLIST_REQUIREMENT_BLOCKING: PreflightGate.APPROVAL,
    PreflightCode.UNACKNOWLEDGED_WARNING_ISSUE: PreflightGate.REGISTRATION_READY,
    PreflightCode.TEMPLATE_NOT_VALIDATED: PreflightGate.REGISTRATION_READY,
    PreflightCode.SOURCE_REVERIFICATION_REQUIRED: PreflightGate.REGISTRATION_READY,
}

_WARNING_CODES: frozenset[PreflightCode] = frozenset(
    {
        PreflightCode.UNRESOLVED_OPTIONAL_FIELD,
        PreflightCode.FIELD_AWAITING_CONFIRMATION,
        PreflightCode.TEMPLATE_SOURCE_DEFECT,
    }
)

#: Report order. Fixed here rather than left to insertion order so two runs over
#: the same state produce the same list — §9.4 calls preflight deterministic,
#: and a gate report that reshuffles is one a lawyer cannot diff.
_ORDER: dict[PreflightCode, int] = {code: index for index, code in enumerate(PreflightCode)}


@dataclass(frozen=True)
class PreflightItem:
    code: PreflightCode
    subject_id: str
    explanation_key: str
    gate: PreflightGate
    blocking: bool


@dataclass(frozen=True)
class PreflightResult:
    """A deterministic gate report over all four sources plus template state."""

    form_id: str
    template_id: str
    template_version: str
    rule_pack_version: str
    items: tuple[PreflightItem, ...]
    #: Read from `FormTemplateDefinition.registration_ready_capable`, never
    #: asserted. False for every template in this repository (§9.5).
    template_registration_ready_capable: bool
    evaluated_at: datetime
    watermark_key: str = DRAFT_WATERMARK_KEY

    @property
    def blocking(self) -> tuple[PreflightItem, ...]:
        return tuple(item for item in self.items if item.blocking)

    @property
    def warnings(self) -> tuple[PreflightItem, ...]:
        return tuple(item for item in self.items if not item.blocking)

    def _clear_through(self, gates: frozenset[PreflightGate]) -> bool:
        return not any(item.gate in gates for item in self.blocking)

    @property
    def review_ready(self) -> bool:
        """§10.7 — every required field resolved and nothing standing in the way."""
        return self._clear_through(frozenset({PreflightGate.REVIEW_READY}))

    @property
    def approval_ready(self) -> bool:
        return self._clear_through(frozenset({PreflightGate.REVIEW_READY, PreflightGate.APPROVAL}))

    @property
    def registration_ready(self) -> bool:
        """False today for every form, because no template can back one (§9.5).

        Computed rather than hard-coded so the answer stays true if a lawyer
        approved rendering is ever added — but until one is, `blocking` always
        contains ``TEMPLATE_NOT_VALIDATED``.
        """
        return self.template_registration_ready_capable and not self.blocking


def _item(code: PreflightCode, subject_id: str) -> PreflightItem:
    return PreflightItem(
        code=code,
        subject_id=subject_id,
        explanation_key=f"rta.form.preflight.{code.value.lower()}",
        gate=_GATES.get(code, PreflightGate.REGISTRATION_READY),
        blocking=code not in _WARNING_CODES,
    )


def source_reverification_required(template: FormTemplateDefinition) -> bool:
    """§9.5 — whether the template's own source still needs re-verification.

    True while the record is a transcription, while the official page image is
    not held, or while any known defect of the source text is unresolved. All
    three are true of every template here.
    """
    return (
        template.status is not TemplateStatus.VALIDATED
        or template.official_artifact_source_record_id is None
        or bool(template.known_source_defect_keys)
    )


def preflight(
    *,
    form: GeneratedForm,
    fields: Sequence[GeneratedFormField],
    template: FormTemplateDefinition,
    facts: FactTierSummary,
    issue_gates: IssueGateSummary,
    blocking_requirement_ids: Sequence[str],
    evaluated_at: datetime,
) -> PreflightResult:
    """Assemble the gate report from all four sources plus the template's state.

    All four are consulted every time. A form whose own fields are complete is
    still not ready while a critical fact is unconfirmed, an issue is open, or a
    checklist requirement blocks — §14.6 lists them as separate stop conditions
    and this function does not let any of them be inferred from another.
    """
    items: list[PreflightItem] = []

    # 1. The form's own state.
    for form_field in fields:
        if form_field.unresolved_reason is UnresolvedReason.FACT_CONFLICTED:
            items.append(_item(PreflightCode.FIELD_CONFLICTED, form_field.field_id))
        elif form_field.is_unresolved:
            items.append(
                _item(
                    PreflightCode.UNRESOLVED_REQUIRED_FIELD
                    if form_field.required
                    else PreflightCode.UNRESOLVED_OPTIONAL_FIELD,
                    form_field.field_id,
                )
            )
        if form_field.awaiting_confirmation:
            items.append(_item(PreflightCode.FIELD_AWAITING_CONFIRMATION, form_field.field_id))
    if form.is_stale:
        # Keyed off the state, not off ``stale_reason``: the reason stays on the
        # row after a re-evaluation clears the form, as the record of why it was
        # last re-evaluated, and a resolved form must not keep blocking on it.
        items.append(_item(PreflightCode.FORM_STALE, form.stale_reason or form.id))

    # 2. Unconfirmed critical facts, from verification's own summary.
    items.extend(
        _item(PreflightCode.CRITICAL_FACT_UNCONFIRMED, fact_type_id)
        for fact_type_id in facts.unconfirmed_critical_fact_type_ids
    )

    # 3. Open issues, from check's gates.
    items.extend(
        _item(PreflightCode.OPEN_BLOCKING_ISSUE, issue_id)
        for issue_id in issue_gates.open_blocking_issue_ids
    )
    items.extend(
        _item(PreflightCode.OPEN_STATUTORY_BLOCKER, issue_id)
        for issue_id in issue_gates.open_statutory_blocker_ids
    )
    # The summary carries ids only for the blocking and statutory sets, so the
    # two softer gates are reported against the matter rather than invented ids.
    if issue_gates.blocks_approval and not issue_gates.open_blocking_issue_ids:
        items.append(_item(PreflightCode.OPEN_HIGH_RISK_ISSUE, form.matter_id))
    if issue_gates.blocks_registration_ready_export and not issue_gates.blocks_approval:
        items.append(_item(PreflightCode.UNACKNOWLEDGED_WARNING_ISSUE, form.matter_id))

    # 4. Blocking checklist requirements, from task's own computation.
    items.extend(
        _item(PreflightCode.CHECKLIST_REQUIREMENT_BLOCKING, requirement_id)
        for requirement_id in blocking_requirement_ids
    )

    # 5. Template state. Reported from the definition, never asserted (§9.5).
    if not template.registration_ready_capable:
        items.append(_item(PreflightCode.TEMPLATE_NOT_VALIDATED, template.id))
    if source_reverification_required(template):
        items.append(_item(PreflightCode.SOURCE_REVERIFICATION_REQUIRED, template.id))
    items.extend(
        _item(PreflightCode.TEMPLATE_SOURCE_DEFECT, defect_key)
        for defect_key in template.known_source_defect_keys
    )

    ordered = tuple(sorted(items, key=lambda i: (_ORDER[i.code], i.subject_id)))
    return PreflightResult(
        form_id=form.id,
        template_id=template.id,
        template_version=form.template_version,
        rule_pack_version=form.rule_pack_version,
        items=ordered,
        template_registration_ready_capable=template.registration_ready_capable,
        evaluated_at=evaluated_at,
    )


def derive_state(result: PreflightResult) -> GeneratedFormState:
    """§10.7 — the state a freshly evaluated, unapproved form lands in.

    ``REVIEW_READY`` means the lawyer can start the field-by-field review, not
    that the form may be exported: registration readiness is a separate gate
    that no template in this repository can clear.
    """
    return GeneratedFormState.REVIEW_READY if result.review_ready else GeneratedFormState.UNRESOLVED


# ── Staleness (§9.5, §10.5, §10.7) ───────────────────────────────────────────


def stale_bindings(
    fields: Sequence[GeneratedFormField],
    template: FormTemplateDefinition,
    facts: FactTierSummary,
) -> tuple[tuple[GeneratedFormField, StaleReason], ...]:
    """Populated fields whose binding no longer matches the confirmed tier.

    A correction does not edit a fact: it writes a new version under a new id
    and supersedes the old one (§10.5). So the comparison is against the fact
    *type*'s current confirmed value, not against the bound row — the bound row
    is precisely the thing that has gone.

    A non-critical field bound to a candidate is left alone while the fact type
    has no confirmed value: an AI suggestion is not stale merely because nobody
    has confirmed it yet. Once a confirmed value exists, the suggestion is
    superseded by it and is re-resolved.
    """
    mappings = {mapping.field_id: mapping for mapping in template.field_mappings}
    stale: list[tuple[GeneratedFormField, StaleReason]] = []
    for form_field in fields:
        if not form_field.is_populated or form_field.fact_id is None:
            continue
        mapping = mappings.get(form_field.field_id)
        if mapping is None or mapping.fact_type_id is None:
            continue
        current = facts.confirmed.get(mapping.fact_type_id)
        if current is None:
            if form_field.critical:
                stale.append((form_field, StaleReason.FACT_NO_LONGER_CONFIRMED))
            continue
        if current.fact_id != form_field.fact_id or current.version != form_field.fact_version:
            stale.append((form_field, StaleReason.FACT_SUPERSEDED))
    return tuple(stale)


def detect_staleness(
    *,
    form: GeneratedForm,
    fields: Sequence[GeneratedFormField],
    template: FormTemplateDefinition,
    facts: FactTierSummary,
    rule_pack_version: str,
    declared: StaleReason | None = None,
) -> StaleReason | None:
    """The reason this form no longer matches the record, if any.

    Facts are checked before packaging: if a fact was corrected *and* the
    template moved, the correction is the thing the lawyer must look at, and the
    single ``stale_reason`` column forces one answer. ``declared`` covers the one
    upstream change this module cannot observe — a checklist recompile — and is
    consulted only when nothing observable has already gone stale, so a caller
    can never talk the form out of a fact-level staleness it does have.
    """
    bindings = stale_bindings(fields, template, facts)
    if bindings:
        return bindings[0][1]
    if template.version != form.template_version:
        return StaleReason.TEMPLATE_VERSION_CHANGED
    if rule_pack_version != form.rule_pack_version:
        return StaleReason.RULE_PACK_VERSION_CHANGED
    return declared


def stale_state(form: GeneratedForm, reason: StaleReason) -> GeneratedFormState:
    """Where a stale form lands.

    An approved form becomes ``STALE_AFTER_APPROVAL`` and its snapshot stays
    immutable — amendment is a new form version (§10.7). An unapproved form goes
    back to ``UNRESOLVED``, except for a template or source change, which §9.5
    names ``STALE_TEMPLATE`` so the lawyer can tell "your evidence moved" from
    "the form we drafted against moved".
    """
    if form.is_approved:
        return GeneratedFormState.STALE_AFTER_APPROVAL
    if reason is StaleReason.TEMPLATE_VERSION_CHANGED:
        return GeneratedFormState.STALE_TEMPLATE
    return GeneratedFormState.UNRESOLVED


#: Why a field became unresolved, per staleness reason. A withdrawn
#: confirmation and a corrected value are different things to re-review.
_UNRESOLVED_FOR_STALE: dict[StaleReason, UnresolvedReason] = {
    StaleReason.FACT_SUPERSEDED: UnresolvedReason.FACT_SUPERSEDED,
    StaleReason.FACT_NO_LONGER_CONFIRMED: UnresolvedReason.FACT_NOT_CONFIRMED,
}


def invalidate_binding(form_field: GeneratedFormField, reason: StaleReason) -> None:
    """Return one field to unresolved because the fact behind it moved (§10.5).

    ``fact_id`` and ``fact_version`` are kept: they record which binding went
    stale, which is what the lawyer needs to re-review. The lawyer's review of
    the old value is cleared, because a decision about a superseded value is not
    a decision about the value that replaced it.
    """
    form_field.rendered_value = None
    form_field.unresolved_reason = _UNRESOLVED_FOR_STALE.get(
        reason, UnresolvedReason.FACT_SUPERSEDED
    )
    form_field.transformation_id = None
    form_field.review_decision_id = None
    form_field.reviewed_by = None
    form_field.reviewed_at = None


# ── Field decisions (§9.3, §9.4) ─────────────────────────────────────────────


class FieldDecisionAction(str, enum.Enum):
    """What a lawyer is doing to one field binding."""

    #: Accept the value as bound — the §9.3 "lawyer confirms field" step.
    CONFIRM = "CONFIRM"
    #: Write lawyer-authored text, where the template permits it (§9.4).
    CORRECT = "CORRECT"
    #: Reject a prefilled value and return the field to its unresolved token.
    CLEAR = "CLEAR"


def guard_field_decision(
    *,
    form: GeneratedForm,
    form_field: GeneratedFormField,
    mapping: FormFieldMapping,
    action: FieldDecisionAction,
    value: str | None,
    reason: str | None,
) -> None:
    """Refuse a field decision the snapshot, the template, or §9.3 forbids."""
    if form.is_approved:
        raise ApprovedFormImmutableError(formId=form.id, formVersion=form.form_version)
    if is_pre_certification(mapping):
        raise PreCertificationNotPermittedError(fieldId=mapping.field_id)
    if action is FieldDecisionAction.CONFIRM:
        if not form_field.is_populated:
            raise FieldNotPopulatedError(fieldId=mapping.field_id)
        return
    if not (reason or "").strip():
        raise FieldDecisionReasonRequiredError(fieldId=mapping.field_id, action=action.value)
    if action is FieldDecisionAction.CLEAR:
        return
    if mapping.critical:
        # Rule 1 again, at the one place a user would otherwise route around it:
        # a critical particular is confirmed as a *fact*, with its evidence, and
        # is never typed onto the form.
        raise CriticalFieldRequiresConfirmedFactError(
            fieldId=mapping.field_id, factTypeId=mapping.fact_type_id
        )
    if not mapping.lawyer_authored_allowed:
        raise LawyerAuthoredTextNotPermittedError(fieldId=mapping.field_id)
    if not (value or "").strip():
        raise FieldValueRequiredError(fieldId=mapping.field_id)


# ── Artifact hash (§9.6) ─────────────────────────────────────────────────────


def draft_artifact_hash(
    *,
    template_id: str,
    template_version: str,
    rule_pack_version: str,
    subtype_id: str,
    fields: Iterable[GeneratedFormField],
    scope: dict[str, Any] | None = None,
) -> str:
    """A digest over the binding record, not over a rendered file.

    §9.6 requires an approval to pin "form version/hash" and the list of
    confirmed critical facts. Hashing the bindings makes that pin meaningful
    without keeping every rendered artifact: two forms with the same hash bound
    the same fact versions of the same template.
    """
    payload: dict[str, Any] = {
        "templateId": template_id,
        "templateVersion": template_version,
        "rulePackVersion": rule_pack_version,
        "subtypeId": subtype_id,
        "fields": [
            {
                "fieldId": form_field.field_id,
                "factId": form_field.fact_id,
                "factVersion": form_field.fact_version,
                "evidenceReferenceIds": list(form_field.evidence_reference_ids),
                "renderedValue": form_field.rendered_value,
                "unresolvedReason": (
                    form_field.unresolved_reason.value if form_field.unresolved_reason else None
                ),
                "transformationId": form_field.transformation_id,
            }
            for form_field in sorted(fields, key=lambda f: (f.order, f.field_id))
        ],
    }
    if scope is not None:
        payload["scope"] = scope
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

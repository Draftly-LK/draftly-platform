"""The checklist compiler.

```text
Base matter administration
+ regime and title-status module
+ exact-instrument module
+ condition-triggered scenario modules
+ jurisdiction/office policy modules
+ matter-specific lawyer additions
= versioned matter checklist snapshot
```

Two properties are load-bearing (§5.1):

*Deterministic.* The same inputs and the same rule versions produce byte-identical
output, including item order. ``fingerprint`` makes that testable and makes the
compile endpoint idempotent over unchanged inputs.

*Non-destructive.* When facts change, the compiler produces a new snapshot and a
delta. A requirement that stops being triggered but has already been reviewed is
carried forward as ``NOT_APPLICABLE`` and reported, never dropped — "it never
silently removes a previously reviewed requirement".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from enum import Enum

from src.modules.content_governance.domain.enums import (
    ApplicabilityStatus,
    BlockerKind,
    IssueSeverity,
    MandatoryBasis,
    RequirementGroup,
)
from src.modules.content_governance.domain.rta.checklist import (
    CHECKLIST_VERSION,
    RequirementDefinition,
    get_module,
    get_requirement,
    requirements_for_module,
)
from src.modules.content_governance.domain.rta.taxonomy import (
    TAXONOMY_VERSION,
    get_conditional_module,
    get_subtype,
)

COMPILER_VERSION = "1.0.0"

#: Always compiled, whatever the subtype (§5.1 "base matter administration").
BASE_MODULE_IDS: tuple[str, ...] = ("C00_MATTER_ADMIN",)

#: The regime and title-status module. Present even when the title status is
#: still unknown, because establishing it is the first gate (§Executive 1).
REGIME_MODULE_IDS: tuple[str, ...] = ("C02_RTA_TITLE",)


class InclusionReason(str, Enum):
    """Why this requirement is on this matter's checklist.

    Shown on every item: a lawyer must be able to see whether a requirement
    came from the statute, from the instrument, from a fact about the parties,
    from office policy, or from their own instruction (§5.1, §11.1).
    """

    BASE = "BASE"
    REGIME = "REGIME"
    EXACT_INSTRUMENT = "EXACT_INSTRUMENT"
    CONDITIONAL_MODULE = "CONDITIONAL_MODULE"
    OFFICE_POLICY = "OFFICE_POLICY"
    LOCAL_AUTHORITY_POLICY = "LOCAL_AUTHORITY_POLICY"
    LAWYER_ADDED = "LAWYER_ADDED"
    RETAINED_AFTER_REVIEW = "RETAINED_AFTER_REVIEW"


@dataclass(frozen=True)
class LawyerAddedItem:
    """§5.7 — a matter-specific requirement the responsible lawyer added."""

    id: str
    label: str
    explanation: str
    is_blocker: bool
    requested_document_class_ids: tuple[str, ...] = ()
    assigned_to: str | None = None
    due_at: str | None = None
    linked_issue_id: str | None = None


@dataclass(frozen=True)
class ReviewedItemMemo:
    """The minimum the compiler needs to know about a prior snapshot's item.

    Only enough to decide whether dropping it would erase review work; the
    full item state stays in the runtime record owned by `task`.
    """

    requirement_definition_id: str
    was_reviewed: bool


@dataclass(frozen=True)
class CompilerInput:
    """Everything the compilation depends on. Nothing else may influence it."""

    subtype_id: str | None = None
    activated_conditional_module_ids: frozenset[str] = field(default_factory=frozenset)
    office_policy_module_ids: frozenset[str] = field(default_factory=frozenset)
    local_authority_id: str | None = None
    lawyer_added_items: tuple[LawyerAddedItem, ...] = ()
    #: Conditional modules the lawyer switched off. Removing a rule-triggered
    #: module requires a recorded reason, which the caller enforces and audits;
    #: the compiler only honours the decision (§3.5).
    suppressed_conditional_module_ids: frozenset[str] = field(default_factory=frozenset)
    #: Items from the previous snapshot, so review work survives a recompile.
    previous_items: tuple[ReviewedItemMemo, ...] = ()


@dataclass(frozen=True)
class CompiledItem:
    """One requirement placed on one matter, with its provenance."""

    requirement_definition_id: str
    module_definition_id: str
    inclusion_reason: InclusionReason
    inclusion_trigger_id: str | None
    label_key: str
    explanation_key: str
    mandatory_basis: MandatoryBasis
    group: RequirementGroup
    applicability: ApplicabilityStatus
    source_record_ids: tuple[str, ...]
    accepted_document_class_ids: tuple[str, ...]
    may_be_satisfied_by_combined_document: bool
    physical_original_policy: str
    currency_max_age_days: int | None
    unsatisfied_severity: IssueSeverity
    unsatisfied_blocker_kind: BlockerKind
    waivable: bool
    local_authority_id: str | None
    order: int


@dataclass(frozen=True)
class CompiledChecklist:
    """A snapshot's content plus every rule version it was compiled against."""

    items: tuple[CompiledItem, ...]
    module_definition_ids: tuple[str, ...]
    compiler_version: str
    taxonomy_version: str
    checklist_version: str
    fingerprint: str

    def item_ids(self) -> tuple[str, ...]:
        return tuple(i.requirement_definition_id for i in self.items)


@dataclass(frozen=True)
class ChangedItem:
    requirement_definition_id: str
    field_name: str
    before: str
    after: str


@dataclass(frozen=True)
class ChecklistDelta:
    """What a recompile changed, in the words the UI shows (§5.1)."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[ChangedItem, ...]
    #: No longer triggered, but retained because a human had already worked it.
    retained_after_review: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed or self.retained_after_review)


def _selected_modules(data: CompilerInput) -> list[tuple[str, InclusionReason, str | None]]:
    """Resolve the module set, preserving why each module was selected."""
    selected: list[tuple[str, InclusionReason, str | None]] = []
    seen: set[str] = set()

    def add(module_id: str, reason: InclusionReason, trigger: str | None) -> None:
        if module_id in seen or get_module(module_id) is None:
            return
        seen.add(module_id)
        selected.append((module_id, reason, trigger))

    for module_id in BASE_MODULE_IDS:
        add(module_id, InclusionReason.BASE, None)
    for module_id in REGIME_MODULE_IDS:
        add(module_id, InclusionReason.REGIME, None)

    subtype = get_subtype(data.subtype_id) if data.subtype_id else None
    if subtype is not None:
        for module_id in subtype.default_module_definition_ids:
            add(module_id, InclusionReason.EXACT_INSTRUMENT, subtype.id)

    for conditional_id in sorted(data.activated_conditional_module_ids):
        if conditional_id in data.suppressed_conditional_module_ids:
            continue
        conditional = get_conditional_module(conditional_id)
        if conditional is None:
            continue
        for module_id in conditional.checklist_module_ids:
            add(module_id, InclusionReason.CONDITIONAL_MODULE, conditional_id)

    for module_id in sorted(data.office_policy_module_ids):
        add(module_id, InclusionReason.OFFICE_POLICY, None)

    return selected


def _applicability_for(
    requirement: RequirementDefinition,
    reason: InclusionReason,
) -> ApplicabilityStatus:
    """A conditionally triggered requirement is provisional until confirmed.

    The distinction matters: ``REQUIRED`` says the rule set is certain, while
    ``PROVISIONAL_REQUIRED`` says a fact still under review put it here.
    """
    if requirement.default_applicability is not ApplicabilityStatus.REQUIRED:
        return requirement.default_applicability
    if reason in {InclusionReason.CONDITIONAL_MODULE, InclusionReason.OFFICE_POLICY}:
        return ApplicabilityStatus.PROVISIONAL_REQUIRED
    return ApplicabilityStatus.REQUIRED


def _to_item(
    requirement: RequirementDefinition,
    reason: InclusionReason,
    trigger: str | None,
    local_authority_id: str | None,
) -> CompiledItem:
    return CompiledItem(
        requirement_definition_id=requirement.id,
        module_definition_id=requirement.module_id,
        inclusion_reason=reason,
        inclusion_trigger_id=trigger,
        label_key=requirement.label_key,
        explanation_key=requirement.explanation_key,
        mandatory_basis=requirement.mandatory_basis,
        group=requirement.group,
        applicability=_applicability_for(requirement, reason),
        source_record_ids=tuple(c.source_record_id for c in requirement.sources),
        accepted_document_class_ids=requirement.accepted_document_class_ids,
        may_be_satisfied_by_combined_document=requirement.may_be_satisfied_by_combined_document,
        physical_original_policy=requirement.physical_original_policy.value,
        currency_max_age_days=requirement.currency_max_age_days,
        unsatisfied_severity=requirement.unsatisfied_severity,
        unsatisfied_blocker_kind=requirement.unsatisfied_blocker_kind,
        waivable=requirement.waivable,
        # A local rule for one council must not activate globally (§13.2.8).
        local_authority_id=local_authority_id if requirement.local_authority_scoped else None,
        order=requirement.order,
    )


def _module_order(module_id: str) -> int:
    module = get_module(module_id)
    return module.order if module is not None else 0


def _fingerprint(data: CompilerInput, item_ids: tuple[str, ...]) -> str:
    """Stable hash over the inputs and the resulting item set.

    Two compiles with the same fingerprint are the same snapshot, which is what
    makes ``POST /checklist/compile`` idempotent over unchanged inputs
    (§12.4).
    """
    canonical = json.dumps(
        {
            "compiler": COMPILER_VERSION,
            "taxonomy": TAXONOMY_VERSION,
            "checklist": CHECKLIST_VERSION,
            "subtype": data.subtype_id,
            "conditional": sorted(data.activated_conditional_module_ids),
            "suppressed": sorted(data.suppressed_conditional_module_ids),
            "office": sorted(data.office_policy_module_ids),
            "local_authority": data.local_authority_id,
            "lawyer_added": sorted(i.id for i in data.lawyer_added_items),
            "items": list(item_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def compile_checklist(data: CompilerInput) -> CompiledChecklist:
    """Produce the snapshot content for one matter. Pure and total."""
    selected = _selected_modules(data)
    items: list[CompiledItem] = []
    seen_requirements: set[str] = set()

    for module_id, reason, trigger in selected:
        for requirement in requirements_for_module(module_id):
            if requirement.id in seen_requirements:
                # A requirement reachable through two modules keeps the first
                # (more fundamental) inclusion reason rather than duplicating.
                continue
            seen_requirements.add(requirement.id)
            items.append(_to_item(requirement, reason, trigger, data.local_authority_id))

    # Carry forward previously reviewed requirements that the new rule set no
    # longer triggers. They become NOT_APPLICABLE, stay visible, and report in
    # the delta so nobody's review silently disappears.
    for memo in data.previous_items:
        if memo.requirement_definition_id in seen_requirements or not memo.was_reviewed:
            continue
        retained_requirement = get_requirement(memo.requirement_definition_id)
        if retained_requirement is None:
            continue
        seen_requirements.add(retained_requirement.id)
        retained = _to_item(
            retained_requirement,
            InclusionReason.RETAINED_AFTER_REVIEW,
            None,
            data.local_authority_id,
        )
        items.append(replace(retained, applicability=ApplicabilityStatus.NOT_APPLICABLE))

    items.sort(
        key=lambda i: (_module_order(i.module_definition_id), i.order, i.requirement_definition_id)
    )
    item_ids = tuple(i.requirement_definition_id for i in items)
    return CompiledChecklist(
        items=tuple(items),
        module_definition_ids=tuple(module_id for module_id, _, _ in selected),
        compiler_version=COMPILER_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        checklist_version=CHECKLIST_VERSION,
        fingerprint=_fingerprint(data, item_ids),
    )


_DELTA_TRACKED_FIELDS = (
    "applicability",
    "mandatory_basis",
    "inclusion_reason",
    "unsatisfied_severity",
    "unsatisfied_blocker_kind",
)


def diff_checklists(before: CompiledChecklist, after: CompiledChecklist) -> ChecklistDelta:
    """Report the change in the terms §5.1 requires: added, removed, changed."""
    before_by_id = {i.requirement_definition_id: i for i in before.items}
    after_by_id = {i.requirement_definition_id: i for i in after.items}

    added = tuple(sorted(set(after_by_id) - set(before_by_id)))
    removed = tuple(sorted(set(before_by_id) - set(after_by_id)))
    retained = tuple(
        sorted(
            item_id
            for item_id, item in after_by_id.items()
            if item.inclusion_reason is InclusionReason.RETAINED_AFTER_REVIEW
            and before_by_id.get(item_id) is not None
            and before_by_id[item_id].inclusion_reason is not InclusionReason.RETAINED_AFTER_REVIEW
        )
    )

    changed: list[ChangedItem] = []
    for item_id in sorted(set(before_by_id) & set(after_by_id)):
        old, new = before_by_id[item_id], after_by_id[item_id]
        for name in _DELTA_TRACKED_FIELDS:
            old_value, new_value = getattr(old, name), getattr(new, name)
            if old_value != new_value:
                changed.append(
                    ChangedItem(
                        requirement_definition_id=item_id,
                        field_name=name,
                        before=str(getattr(old_value, "value", old_value)),
                        after=str(getattr(new_value, "value", new_value)),
                    )
                )

    return ChecklistDelta(
        added=added,
        removed=removed,
        changed=tuple(changed),
        retained_after_review=retained,
    )

"""Select eligible values by explicit Form 8 scope, never by matter-wide order."""

from dataclasses import replace

from src.modules.content_governance.contracts import FormFieldMapping, FormTemplateDefinition
from src.modules.draft.contracts import FormScope
from src.modules.draft.domain.policies import FieldResolution, is_pre_certification, resolve_field
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary


def field_scope(
    mapping: FormFieldMapping, scope: FormScope
) -> tuple[str | None, tuple[str, ...], bool]:
    fact_type = mapping.fact_type_id or ""
    for role in ("transferor", "transferee"):
        prefix = f"rta.party.{role}_"
        if fact_type.startswith(prefix):
            subject = getattr(scope, f"{role}_subject_id")
            suffix = fact_type.removeprefix(prefix)
            alias = {
                "name": "holder_name_en",
                "nic": "holder_nic",
                "address": "holder_address",
            }.get(suffix)
            return (
                subject,
                (fact_type, f"rta.party.{alias}") if alias else (fact_type,),
                subject is None,
            )
    if fact_type.startswith(("rta.parcel.", "rta.title.")):
        return scope.parcel_subject_id, (fact_type,), scope.parcel_subject_id is None
    if fact_type.startswith("rta.party."):
        return None, (fact_type,), True
    return None, (fact_type,), False


def select_scoped_fact(
    mapping: FormFieldMapping, scope: FormScope, facts: FactTierSummary
) -> tuple[ConfirmedFactValue | None, str | None]:
    subject, types, unassigned = field_scope(mapping, scope)
    if not mapping.fact_type_id or is_pre_certification(mapping):
        return None, "unsupported"
    if unassigned:
        return None, "unassigned"
    if any((scope.transaction_id, subject, key) in facts.scoped_conflicts for key in types):
        return None, "conflict"
    matches = [
        value
        for value in facts.scoped_confirmed
        if value.transaction_id == scope.transaction_id
        and value.subject_id == subject
        and value.fact_type_id in types
    ]
    # Even agreeing observations with different vocabulary need a deliberate
    # canonical choice; no silent preference between role and holder facts.
    if len(matches) > 1:
        return None, "conflict"
    if matches:
        return matches[0], None
    causes = [
        cause
        for transaction, owner, key, cause in facts.scoped_gaps
        if transaction == scope.transaction_id and owner == subject and key in types
    ]
    return None, next(
        (cause for cause in ("stale", "unassigned", "unreviewed") if cause in causes), "absent"
    )


def scoped_projection(
    template: FormTemplateDefinition, scope: FormScope, facts: FactTierSummary
) -> FactTierSummary:
    confirmed = {}
    for mapping in template.field_mappings:
        value, _ = select_scoped_fact(mapping, scope, facts)
        if value and mapping.fact_type_id:
            confirmed[mapping.fact_type_id] = value
    return replace(facts, confirmed=confirmed)


def resolve_scoped_template(
    template: FormTemplateDefinition, scope: FormScope, facts: FactTierSummary
) -> tuple[tuple[FieldResolution, ...], dict[str, str]]:
    resolutions = []
    gaps = {}
    for mapping in template.field_mappings:
        value, cause = select_scoped_fact(mapping, scope, facts)
        subject, _, _ = field_scope(mapping, scope)
        search = any(
            item.fact_type_id == "rta.title.register_search_datetime"
            and item.transaction_id == scope.transaction_id
            and item.subject_id == subject
            for item in facts.scoped_confirmed
        )
        resolution = resolve_field(
            mapping,
            confirmed=value,
            conflicted=cause == "conflict",
            has_current_search_evidence=search,
        )
        resolutions.append(resolution)
        if resolution.unresolved_reason:
            gaps[mapping.field_id] = cause or "unsupported"
    return tuple(resolutions), gaps

"""Drafting application service — generate, review, preflight, re-evaluate.

Two decisions in this file are product decisions, not implementation details.

**Generation is a snapshot, not a subscription.** A form records the template
version, the rule pack version, and the exact fact version behind every field at
the moment it was drafted. Nothing later rewrites it: §9.5 forbids auto-updating
a live matter when a template changes, and §10.5 makes a fact correction produce
a *new* version rather than an edit. When an input moves, `mark_stale` says so;
it does not quietly re-render the draft under the lawyer.

**Preflight reads all four sources every time.** The form's own unresolved
fields, verification's unconfirmed critical facts, check's open issues, and
task's blocking checklist requirements are four separate §14.6 stop conditions,
and none of them may be inferred from another. A form whose fields are all
populated is still not ready while an issue is open, and this service has no
path that lets it look ready anyway.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime

import structlog

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.check.contracts import IssueGatePort, IssueGateSummary
from src.modules.content_governance.contracts import (
    RULE_PACK_VERSION,
    FormFieldMapping,
    FormTemplateDefinition,
    GeneratedFormState,
    MatterState,
    SubtypeDecisionStatus,
    UnresolvedReason,
    get_subtype,
    require_template,
)
from src.modules.draft.contracts import BoundFact, FormScope, FormSnapshot
from src.modules.draft.domain.errors import (
    GeneratedFormFieldNotFoundError,
    GeneratedFormNotFoundError,
    TemplateNotAvailableForSubtypeError,
)
from src.modules.draft.domain.models import (
    FactCandidate,
    GeneratedForm,
    GeneratedFormField,
    StaleReason,
)
from src.modules.draft.domain.policies import (
    FieldDecisionAction,
    FieldResolution,
    PreflightResult,
    derive_state,
    detect_staleness,
    draft_artifact_hash,
    guard_field_decision,
    guard_generation,
    guard_populated_critical_field,
    invalidate_binding,
    is_ai_suggested,
    preflight,
    resolve_template,
    select_template,
    stale_bindings,
    stale_state,
)
from src.modules.draft.domain.scoped import resolve_scoped_template, scoped_projection
from src.modules.draft.ports import (
    CandidateFactReadPort,
    GeneratedFormRepository,
    MatterWorkflowCommandPort,
)
from src.modules.matter.contracts import MatterMutationLockPort, MatterScopeReadPort
from src.modules.task.contracts import ChecklistBlockerPort
from src.modules.verification.contracts import ConfirmedFactReadPort, FactTierSummary
from src.platform import ids
from src.platform.errors import DomainRuleError, NotFoundError, PreconditionFailedError

log = structlog.get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


#: Clearing a rejected prefill leaves the field with no canonical value behind
#: it, which is exactly what ``NO_FACT`` means in this module (see
#: `domain/policies.py` on the closed `UnresolvedReason` vocabulary).
_CLEARED_REASON = UnresolvedReason.NO_FACT
_CONFLICTED = UnresolvedReason.FACT_CONFLICTED


@dataclass(frozen=True)
class FormFieldView:
    """One field plus what the template says about it and what the UI renders."""

    field: GeneratedFormField
    mapping: FormFieldMapping
    #: The value, or the §9.4 ``[[UNRESOLVED: <field_id>]]`` token.
    display_value: str
    #: §9.3 — a prefill from a candidate, not a lawyer-confirmed fact. Computed
    #: against the fact tier rather than derived from the row, so the badge is
    #: never put on a value the lawyer confirmed.
    ai_suggested: bool = False
    #: Both sides of a §9.4 conflict, never narrowed to one.
    conflicting_candidates: tuple[FactCandidate, ...] = ()


@dataclass(frozen=True)
class FormView:
    form: GeneratedForm
    template: FormTemplateDefinition
    fields: tuple[FormFieldView, ...]
    preflight: PreflightResult


class DraftService:
    """Owns generated forms, their field bindings, and the preflight gate."""

    def __init__(
        self,
        *,
        repository: GeneratedFormRepository,
        facts: ConfirmedFactReadPort,
        issues: IssueGatePort,
        checklist: ChecklistBlockerPort,
        audit: AuditPort,
        candidates: CandidateFactReadPort | None = None,
        clock: Callable[[], datetime] = _utc_now,
        matter_workflow: MatterWorkflowCommandPort | None = None,
        matter_lock: MatterMutationLockPort | None = None,
        scopes: MatterScopeReadPort | None = None,
    ) -> None:
        self._repo = repository
        self._scopes = scopes
        self._matter_workflow = matter_workflow
        self._matter_lock = matter_lock
        self._facts = facts
        self._issues = issues
        self._checklist = checklist
        self._audit = audit
        # Optional: with no candidate reader every non-critical field simply
        # stays unresolved. That is the honest degradation — the alternative
        # would be inventing a prefill nobody extracted (§9.3).
        self._candidates = candidates
        self._clock = clock

    # ── Generation (§9.2) ────────────────────────────────────────────────────

    async def generate_form(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        subtype_id: str | None,
        subtype_decision_status: SubtypeDecisionStatus,
        template_id: str | None = None,
        scope: FormScope | None = None,
        predecessor_form_id: str | None = None,
    ) -> FormView:
        """Draft one working form from the confirmed subtype and the fact tier.

        A 201 from this method means a draft was recorded, not that it may be
        executed: every template in this repository is a transcription, so the
        returned preflight always reports ``registration_ready`` false (§9.5).
        """
        if self._matter_lock:
            await self._matter_lock.lock(user_id, matter_id)
        gates = await self._issues.gates(user_id, matter_id)
        confirmed_subtype_id = guard_generation(
            subtype_id=subtype_id,
            subtype_decision_status=subtype_decision_status,
            issue_gates=gates,
        )
        subtype = get_subtype(confirmed_subtype_id)
        if subtype is None:
            raise TemplateNotAvailableForSubtypeError(subtypeId=confirmed_subtype_id)
        template = require_template(select_template(subtype, template_id))

        facts = await self._facts.summarise(user_id, matter_id)
        candidates = await self._read_candidates(user_id, matter_id)
        missing_causes: dict[str, str] = {}
        if scope is not None:
            if template.id != "reg_2022_form_08":
                raise DomainRuleError("Explicit form scope is supported for Form 8 only.")
            await self._validate_scope(user_id, matter_id, scope)
            resolutions, missing_causes = resolve_scoped_template(template, scope, facts)
        else:
            resolutions = resolve_template(template, facts=facts, candidates=candidates)
        if predecessor_form_id:
            previous = await self._repo.get_form(user_id, predecessor_form_id)
            if previous is None or previous.matter_id != matter_id:
                raise GeneratedFormNotFoundError()
            if previous.template_id != template.id:
                raise DomainRuleError("A successor must use the same form template.")

        now = self._clock()
        form_id = ids.new_id(ids.GENERATED_FORM)
        fields = [
            self._to_field(resolution, form_id=form_id, user_id=user_id, matter_id=matter_id)
            for resolution in resolutions
        ]
        for form_field in fields:
            guard_populated_critical_field(form_field)

        form = GeneratedForm(
            id=form_id,
            user_id=user_id,
            matter_id=matter_id,
            template_id=template.id,
            template_version=template.version,
            form_version=await self._repo.next_form_version(user_id, matter_id, template.id),
            state=GeneratedFormState.GENERATED_DRAFT,
            subtype_id=subtype.id,
            rule_pack_version=RULE_PACK_VERSION,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            draft_artifact_hash=self._hash(template, subtype.id, fields, scope),
            scope=scope,
            missing_causes=missing_causes,
            predecessor_form_id=predecessor_form_id,
        )
        result = await self._preflight(form, fields, template, facts=facts, gates=gates)
        form.state = derive_state(result)

        saved_form = await self._repo.create_form(form)
        saved_fields = await self._repo.create_fields(fields)
        await self._record(
            form=saved_form,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_FORM_GENERATED,
            after_ref=(
                f"{saved_form.template_id}@{saved_form.template_version}"
                f"#{saved_form.form_version}:{saved_form.state.value}"
            ),
        )
        # §10.1 READY_TO_DRAFT -> DRAFTING: form created.
        await self._advance_matter(
            user_id, saved_form.matter_id, MatterState.DRAFTING, AuditAction.RTA_FORM_GENERATED
        )
        return self._view(saved_form, saved_fields, template, result, candidates, facts)

    def _to_field(
        self, resolution: FieldResolution, *, form_id: str, user_id: str, matter_id: str
    ) -> GeneratedFormField:
        mapping = resolution.mapping
        return GeneratedFormField(
            id=ids.new_id(ids.GENERATED_FORM_FIELD),
            user_id=user_id,
            matter_id=matter_id,
            generated_form_id=form_id,
            field_id=mapping.field_id,
            critical=mapping.critical,
            required=mapping.required,
            order=mapping.order,
            fact_id=resolution.fact_id,
            fact_version=resolution.fact_version,
            evidence_reference_ids=resolution.evidence_reference_ids,
            rendered_value=resolution.rendered_value,
            unresolved_reason=resolution.unresolved_reason,
            transformation_id=resolution.transformation_id,
        )

    # ── Reads ────────────────────────────────────────────────────────────────

    async def get_form(self, *, user_id: str, form_id: str) -> FormView:
        form = await self._repo.get_form(user_id, form_id)
        if form is None:
            raise GeneratedFormNotFoundError()
        template = require_template(form.template_id)
        fields = await self._repo.list_fields(user_id, form.id)
        facts = await self._facts.summarise(user_id, form.matter_id)
        gates = await self._issues.gates(user_id, form.matter_id)
        candidates = await self._read_candidates(user_id, form.matter_id)
        result = await self._preflight(form, fields, template, facts=facts, gates=gates)
        return self._view(form, fields, template, result, candidates, facts)

    async def list_forms(
        self, *, user_id: str, matter_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[GeneratedForm], str | None]:
        """Bare forms, newest first. Superseded versions stay readable (§9.5)."""
        return await self._repo.list_forms(user_id, matter_id, limit=limit, cursor=cursor)

    async def get_form_snapshot(self, user_id: str, form_id: str) -> FormSnapshot | None:
        """Implements `draft.contracts.GeneratedFormReadPort` for approval."""
        form = await self._repo.get_form(user_id, form_id)
        if form is None:
            return None
        fields = await self._repo.list_fields(user_id, form.id)
        scope_current = await self._scope_current(form)
        if form.scope:
            current = await self._facts.summarise(user_id, form.matter_id)
            projected = scoped_projection(require_template(form.template_id), form.scope, current)
            scope_current = scope_current and not stale_bindings(
                fields, require_template(form.template_id), projected, strict_confirmed=True
            )
        return FormSnapshot(
            form_id=form.id,
            scope=form.scope,
            scope_current=scope_current,
            unreviewed_field_ids=tuple(
                f.field_id for f in fields if (f.required or f.critical) and f.awaiting_confirmation
            ),
            user_id=form.user_id,
            matter_id=form.matter_id,
            state=form.state,
            template_id=form.template_id,
            template_version=form.template_version,
            form_version=form.form_version,
            subtype_id=form.subtype_id,
            rule_pack_version=form.rule_pack_version,
            draft_artifact_hash=form.draft_artifact_hash,
            approved_artifact_hash=form.approved_artifact_hash,
            approval_id=form.approval_id,
            stale_reason=form.stale_reason,
            version=form.version,
            critical_fact_bindings=tuple(
                BoundFact(
                    field_id=form_field.field_id,
                    fact_id=form_field.fact_id,
                    version=form_field.fact_version,
                    evidence_reference_ids=form_field.evidence_reference_ids,
                )
                for form_field in fields
                if form_field.critical
                and form_field.is_populated
                and form_field.fact_id is not None
                and form_field.fact_version is not None
            ),
            unresolved_field_ids=tuple(
                form_field.field_id for form_field in fields if form_field.is_unresolved
            ),
        )

    # ── Field review (§9.3, §9.4) ────────────────────────────────────────────

    async def decide_field(
        self,
        *,
        user_id: str,
        form_id: str,
        field_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        action: FieldDecisionAction,
        value: str | None = None,
        reason: str | None = None,
    ) -> FormView:
        """Record one lawyer decision about one field binding.

        The reviewer is the authenticated actor, never the body: a field
        confirmation is a named legal act (§9.3 "reviewer and decision").
        """
        form, template, fields = await self._load(user_id, form_id)
        mappings = {mapping.field_id: mapping for mapping in template.field_mappings}
        form_field = next((f for f in fields if f.field_id == field_id), None)
        mapping = mappings.get(field_id)
        if form_field is None or mapping is None:
            raise GeneratedFormFieldNotFoundError(fieldId=field_id, formId=form_id)

        current_facts = await self._facts.summarise(user_id, form.matter_id)
        projected = (
            scoped_projection(template, form.scope, current_facts) if form.scope else current_facts
        )
        if not await self._scope_current(form) or stale_bindings(
            fields, template, projected, strict_confirmed=form.scope is not None
        ):
            raise DomainRuleError("The draft inputs have changed. Create a successor draft.")
        guard_field_decision(
            form=form,
            form_field=form_field,
            mapping=mapping,
            action=action,
            value=value,
            reason=reason,
        )

        before = f"{form_field.fact_id or 'unbound'}@{form_field.fact_version or 0}"
        decision_id = ids.new_id(ids.REVIEW_DECISION)
        now = self._clock()
        self._apply_decision(form_field, action, value=value, actor_id=actor_id, now=now)
        form_field.review_decision_id = decision_id
        form_field.reviewed_by = actor_id
        form_field.reviewed_at = now
        guard_populated_critical_field(form_field)
        saved_field = await self._repo.update_field(form_field)
        fields = [saved_field if f.id == saved_field.id else f for f in fields]

        form.draft_artifact_hash = self._hash(template, form.subtype_id, fields, form.scope)
        facts = await self._facts.summarise(user_id, form.matter_id)
        gates = await self._issues.gates(user_id, form.matter_id)
        result = await self._preflight(form, fields, template, facts=facts, gates=gates)
        form.state = derive_state(result)
        saved_form = await self._repo.update_form(form, expected_version)
        await self._record(
            form=saved_form,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_FORM_FIELD_DECIDED,
            before_ref=f"{field_id}:{before}",
            # The decision has no row of its own in this module: the audit event
            # *is* the record of it, and this links the two.
            after_ref=f"{field_id}:{action.value}@{decision_id}",
            reason=reason,
        )
        if saved_form.state is GeneratedFormState.APPROVAL_PENDING:
            # §10.1 DRAFTING -> APPROVAL_PENDING: the derived state says preflight passes.
            await self._advance_matter(
                user_id,
                saved_form.matter_id,
                MatterState.APPROVAL_PENDING,
                AuditAction.RTA_FORM_FIELD_DECIDED,
            )
        candidates = await self._read_candidates(user_id, form.matter_id)
        return self._view(saved_form, fields, template, result, candidates, facts)

    @staticmethod
    def _apply_decision(
        form_field: GeneratedFormField,
        action: FieldDecisionAction,
        *,
        value: str | None,
        actor_id: str,
        now: datetime,
    ) -> None:
        if action is FieldDecisionAction.CONFIRM:
            # The binding is accepted as it stands; nothing about the value or
            # its evidence changes, which is the point of confirming it.
            return
        if action is FieldDecisionAction.CORRECT:
            form_field.rendered_value = (value or "").strip()
            form_field.unresolved_reason = None
            # Lawyer-authored text has no canonical fact behind it and must not
            # borrow the evidence of the value it replaced (§9.4).
            form_field.fact_id = None
            form_field.fact_version = None
            form_field.evidence_reference_ids = ()
            form_field.transformation_id = None
            return
        form_field.rendered_value = None
        form_field.unresolved_reason = _CLEARED_REASON
        form_field.fact_id = None
        form_field.fact_version = None
        form_field.evidence_reference_ids = ()
        form_field.transformation_id = None

    # ── Preflight and staleness ──────────────────────────────────────────────

    async def _advance_matter(
        self, user_id: str, matter_id: str, state: MatterState, reason: AuditAction
    ) -> None:
        """Name the state a drafting write implies; the matter refuses any move it does not allow."""
        if self._matter_workflow is not None:
            await self._matter_workflow.advance_state(
                user_id=user_id, matter_id=matter_id, state=state, reason=reason.value
            )

    async def run_preflight(
        self, *, user_id: str, form_id: str, actor_id: str, correlation_id: str
    ) -> FormView:
        """Report the gates. Read-only: a report never advances a state.

        The form's state is derived on every write that could change it, so a
        preflight that also wrote would either duplicate that or let a read
        endpoint move a legal state.
        """
        view = await self.get_form(user_id=user_id, form_id=form_id)
        await self._record(
            form=view.form,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_FORM_PREFLIGHT_RUN,
            after_ref=_preflight_fingerprint(view.preflight),
        )
        return view

    async def mark_stale(
        self,
        *,
        user_id: str,
        form_id: str,
        actor_id: str,
        correlation_id: str,
        expected_version: int,
        declared: StaleReason | None = None,
    ) -> FormView:
        """Re-evaluate one form against its current inputs (§9.5, §10.5, §10.7).

        An approved form is never rewritten: its state records that it went
        stale and its bindings stay exactly as they were approved. Amending it
        is a new form version. An unapproved form has its moved bindings
        returned to unresolved tokens, because a superseded value must not keep
        rendering as if it were current.
        """
        form, template, fields = await self._load(user_id, form_id)
        facts = await self._facts.summarise(user_id, form.matter_id)
        gates = await self._issues.gates(user_id, form.matter_id)
        facts = scoped_projection(template, form.scope, facts) if form.scope else facts
        if not await self._scope_current(form):
            declared = StaleReason.FACT_SUPERSEDED
        reason = detect_staleness(
            form=form,
            fields=fields,
            template=template,
            facts=facts,
            rule_pack_version=RULE_PACK_VERSION,
            declared=declared,
        )
        if reason is None:
            result = await self._preflight(form, fields, template, facts=facts, gates=gates)
            candidates = await self._read_candidates(user_id, form.matter_id)
            return self._view(form, fields, template, result, candidates, facts)

        if not form.is_approved:
            for form_field, field_reason in stale_bindings(
                fields, template, facts, strict_confirmed=form.scope is not None
            ):
                invalidate_binding(form_field, field_reason)
                await self._repo.update_field(form_field)
            form.draft_artifact_hash = self._hash(template, form.subtype_id, fields, form.scope)

        previous = form.state
        form.stale_reason = reason.value
        form.state = stale_state(form, reason)
        result = await self._preflight(form, fields, template, facts=facts, gates=gates)
        if not form.is_approved and reason is not StaleReason.TEMPLATE_VERSION_CHANGED:
            # §10.7 names both landing states for a pre-approval change. A form
            # whose remaining bindings all still hold goes back to REVIEW_READY
            # rather than being parked as unresolved with nothing unresolved.
            form.state = derive_state(result)
        saved_form = await self._repo.update_form(form, expected_version)
        await self._record(
            form=saved_form,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_FORM_MARKED_STALE,
            before_ref=previous.value,
            after_ref=f"{saved_form.state.value}@{reason.value}",
        )
        return self._view(
            saved_form,
            fields,
            template,
            result,
            await self._read_candidates(user_id, form.matter_id),
            facts,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _load(
        self, user_id: str, form_id: str
    ) -> tuple[GeneratedForm, FormTemplateDefinition, list[GeneratedFormField]]:
        form = await self._repo.get_form(user_id, form_id)
        if form is not None and self._matter_lock:
            await self._matter_lock.lock(user_id, form.matter_id)
            form = await self._repo.get_form(user_id, form_id)
        if form is None:
            raise GeneratedFormNotFoundError()
        return (
            form,
            require_template(form.template_id),
            await self._repo.list_fields(user_id, form.id),
        )

    async def _read_candidates(self, user_id: str, matter_id: str) -> tuple[FactCandidate, ...]:
        if self._candidates is None:
            return ()
        return await self._candidates.candidates(user_id, matter_id)

    async def _preflight(
        self,
        form: GeneratedForm,
        fields: Sequence[GeneratedFormField],
        template: FormTemplateDefinition,
        *,
        facts: FactTierSummary,
        gates: IssueGateSummary,
    ) -> PreflightResult:
        projected = scoped_projection(template, form.scope, facts) if form.scope else facts
        reason = detect_staleness(
            form=form,
            fields=fields,
            template=template,
            facts=projected,
            rule_pack_version=RULE_PACK_VERSION,
        )
        if not await self._scope_current(form):
            reason = StaleReason.FACT_SUPERSEDED
        if reason is not None:
            form = replace(
                form,
                state=GeneratedFormState.STALE_AFTER_APPROVAL
                if form.is_approved
                else GeneratedFormState.STALE_TEMPLATE,
                stale_reason=reason.value,
            )
        return preflight(
            form=form,
            fields=fields,
            template=template,
            facts=facts,
            issue_gates=gates,
            blocking_requirement_ids=await self._checklist.blocking_requirement_ids(
                user_id=form.user_id, matter_id=form.matter_id
            ),
            evaluated_at=self._clock(),
        )

    @staticmethod
    def _hash(
        template: FormTemplateDefinition,
        subtype_id: str,
        fields: Sequence[GeneratedFormField],
        scope: FormScope | None = None,
    ) -> str:
        return draft_artifact_hash(
            template_id=template.id,
            template_version=template.version,
            rule_pack_version=RULE_PACK_VERSION,
            subtype_id=subtype_id,
            fields=fields,
            scope=asdict(scope) if scope else None,
        )

    @staticmethod
    def _view(
        form: GeneratedForm,
        fields: Sequence[GeneratedFormField],
        template: FormTemplateDefinition,
        result: PreflightResult,
        candidates: Sequence[FactCandidate],
        facts: FactTierSummary,
    ) -> FormView:
        if form.scope:
            facts = scoped_projection(template, form.scope, facts)
            candidates = ()
        mappings = {mapping.field_id: mapping for mapping in template.field_mappings}
        by_type: dict[str, list[FactCandidate]] = {}
        for candidate in candidates:
            by_type.setdefault(candidate.fact_type_id, []).append(candidate)
        views: list[FormFieldView] = []
        for form_field in sorted(fields, key=lambda f: (f.order, f.field_id)):
            mapping = mappings.get(form_field.field_id)
            if mapping is None:
                # A field the template no longer declares stays visible rather
                # than being hidden: it is part of what was drafted.
                log.warning(
                    "draft.field_mapping_retired",
                    field_id=form_field.field_id,
                    template_id=template.id,
                )
                continue
            if form.scope and form_field.fact_id:
                current = facts.confirmed.get(mapping.fact_type_id or "")
                if (
                    current is None
                    or current.fact_id != form_field.fact_id
                    or current.version != form_field.fact_version
                ):
                    form = replace(
                        form, missing_causes={**form.missing_causes, form_field.field_id: "stale"}
                    )
            views.append(
                FormFieldView(
                    field=form_field,
                    mapping=mapping,
                    display_value=form_field.display_value(),
                    ai_suggested=is_ai_suggested(form_field, mapping, facts),
                    conflicting_candidates=(
                        tuple(by_type.get(mapping.fact_type_id or "", ()))
                        if form_field.unresolved_reason is _CONFLICTED
                        else ()
                    ),
                )
            )
        if form.scope and any(item.code.value == "FORM_STALE" for item in result.blocking):
            form = replace(
                form,
                missing_causes={
                    **form.missing_causes,
                    **{f.field_id: "stale" for f in fields if f.is_populated},
                },
            )
        return FormView(form=form, template=template, fields=tuple(views), preflight=result)

    async def _validate_scope(self, user_id: str, matter_id: str, scope: FormScope) -> None:
        if self._scopes is None:
            raise DomainRuleError("Scope validation is unavailable.")
        transaction = await self._scopes.transaction(user_id, matter_id, scope.transaction_id)
        if transaction is None:
            raise NotFoundError()
        if transaction.version != scope.association_version:
            raise PreconditionFailedError(currentVersion=transaction.version)
        for subject_id, kind, role in (
            (scope.parcel_subject_id, "parcel", None),
            (scope.transferor_subject_id, "party", "transferor"),
            (scope.transferee_subject_id, "party", "transferee"),
        ):
            if subject_id is None:
                continue
            subject = await self._scopes.subject(user_id, matter_id, subject_id)
            if subject is None:
                raise NotFoundError()
            if (
                subject.kind != kind
                or (role is None and subject_id not in transaction.parcel_subject_ids)
                or (
                    role is not None
                    and not any(
                        item.subject_id == subject_id and item.role == role
                        for item in transaction.party_roles
                    )
                )
            ):
                raise DomainRuleError(
                    "The selected subject is not associated in this transaction role."
                )

    async def _scope_current(self, form: GeneratedForm) -> bool:
        if form.scope is None:
            return True
        try:
            await self._validate_scope(form.user_id, form.matter_id, form.scope)
        except (DomainRuleError, NotFoundError, PreconditionFailedError):
            return False
        return True

    async def _record(
        self,
        *,
        form: GeneratedForm,
        actor_id: str,
        correlation_id: str,
        action: AuditAction,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=form.user_id,
                matter_id=form.matter_id,
                actor=actor_id,
                action=action.value,
                target_type=AuditTargetType.GENERATED_FORM.value,
                target_id=form.id,
                before_ref=before_ref,
                after_ref=after_ref,
                reason=reason,
                correlation_id=correlation_id,
            )
        )


def _preflight_fingerprint(result: PreflightResult) -> str:
    """Compact ``CODE:subject`` list, so the audit row shows what the gate said."""
    blocking = ";".join(f"{item.code.value}:{item.subject_id}" for item in result.blocking)
    return f"registrationReady={str(result.registration_ready).lower()}|{blocking}"


__all__ = ["DraftService", "FormFieldView", "FormView"]

"""Matter application service — intake, routing, and scope decisions.

The order of operations in `route` is the product decision this file exists to
enforce:

```text
read live answers -> derive routing -> read confirmed facts
  -> evaluate eligibility -> set automation scope -> record why -> audit
```

Nothing here concludes anything legal. It decides how much Draftly is allowed
to do, records the reasons, and leaves every piece of evidence and every
checklist decision in place when the answer is "not much" (§2.3).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

import structlog

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import (
    CAP_CHECKLIST_COMPILE,
    CAP_MATTER_CONFIRM_SUBTYPE,
    CAP_MATTER_ROUTE,
    RULE_PACK_VERSION,
    AnswerStatus,
    AutomationScope,
    CompiledChecklist,
    CompilerInput,
    DispositionScope,
    DisputeStage,
    EligibilityDecision,
    MatterState,
    ParcelKind,
    ReviewedItemMemo,
    SubtypeDecisionStatus,
    TitleStatus,
    evaluate,
    get_question,
    get_subtype,
    migrate_legacy_matter_type,
)
from src.modules.matter.contracts import MatterAccessSummary, require_rta_capability
from src.modules.matter.domain.errors import (
    IllegalMatterTransitionError,
    InvalidAnswerValueError,
    LegalBasisRequiredError,
    MatterNotFoundError,
    UnknownLegacyMatterTypeError,
    UnknownQuestionError,
    UnknownSubtypeError,
)
from src.modules.matter.domain.models import (
    InstrumentLanguage,
    IntakeAnswer,
    Matter,
    MatterLifecycleStatus,
    is_transition_allowed,
)
from src.modules.matter.domain.routing import (
    LiveAnswer,
    MatterFactSnapshot,
    RoutingDerivation,
    build_eligibility_input,
    derive_routing,
)
from src.modules.matter.ports import (
    ChecklistCommandPort,
    IntakeAnswerRepository,
    MatterFactPort,
    MatterRepository,
)
from src.platform import ids
from src.platform.request_context import RequestContext

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CreateMatterInput:
    reference: str
    client_reference: str | None = None
    instrument_language: InstrumentLanguage = InstrumentLanguage.EN
    responsible_lawyer_id: str | None = None
    local_authority_id: str | None = None
    #: Set only when importing a record from the retired M2 vocabulary.
    legacy_matter_type: str | None = None


@dataclass(frozen=True)
class RoutingResult:
    matter: Matter
    derivation: RoutingDerivation
    decision: EligibilityDecision
    #: Resolution questions the answers so far have opened (§4.1 step 3).
    next_question_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChecklistCompileResult:
    snapshot_id: str
    checklist: CompiledChecklist
    matter: Matter


class MatterService:
    """Owns matter identity, intake answers, routing, and automation scope."""

    def __init__(
        self,
        *,
        matters: MatterRepository,
        answers: IntakeAnswerRepository,
        facts: MatterFactPort,
        checklist: ChecklistCommandPort,
        audit: AuditPort,
    ) -> None:
        self._matters = matters
        self._answers = answers
        self._facts = facts
        self._checklist = checklist
        self._audit = audit

    # ── Reads ────────────────────────────────────────────────────────────────

    async def get_matter(self, ctx: RequestContext, matter_id: str) -> Matter:
        matter = await self._matters.get(ctx.actor_id, matter_id)
        if matter is None:
            raise MatterNotFoundError()
        return matter

    async def list_matters(
        self, ctx: RequestContext, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[Matter], str | None]:
        return await self._matters.list_for_user(ctx.actor_id, limit=limit, cursor=cursor)

    async def get_access_summary(self, user_id: str, matter_id: str) -> MatterAccessSummary | None:
        matter = await self._matters.get(user_id, matter_id)
        return _to_summary(matter) if matter is not None else None

    async def list_answers(
        self, ctx: RequestContext, matter_id: str, *, include_superseded: bool = False
    ) -> list[IntakeAnswer]:
        """Superseded answers stay retrievable — history is part of the record."""
        await self.get_matter(ctx, matter_id)
        if include_superseded:
            return await self._answers.list_all(ctx.actor_id, matter_id)
        return await self._answers.list_live(ctx.actor_id, matter_id)

    # ── Creation ─────────────────────────────────────────────────────────────

    async def create_matter(self, ctx: RequestContext, data: CreateMatterInput) -> Matter:
        """Create an intake draft. Never defaults the exact subtype (§12.4)."""
        now = datetime.now(tz=UTC)
        legacy_subtype_id: str | None = None
        legacy_modules: frozenset[str] = frozenset()
        if data.legacy_matter_type is not None:
            try:
                migration = migrate_legacy_matter_type(data.legacy_matter_type)
            except KeyError as exc:
                raise UnknownLegacyMatterTypeError(
                    f"No migration target for legacy matter type '{data.legacy_matter_type}'."
                ) from exc
            legacy_subtype_id = migration.subtype_id
            legacy_modules = frozenset(migration.activated_conditional_module_ids)

        matter = Matter(
            id=ids.new_id(ids.MATTER),
            user_id=ctx.actor_id,
            reference=data.reference,
            client_reference=data.client_reference,
            responsible_lawyer_id=data.responsible_lawyer_id or ctx.actor_id,
            regime_id="lk.rta",
            lifecycle_status=MatterLifecycleStatus.INQUIRY,
            rta_state=MatterState.INTAKE_DRAFT,
            automation_scope=AutomationScope.ASSESSING,
            # A migration is not a lawyer's confirmation, and neither is a
            # freshly created matter (§3.6).
            subtype_decision_status=SubtypeDecisionStatus.PROVISIONAL,
            title_status=TitleStatus.UNKNOWN,
            parcel_kind=ParcelKind.UNKNOWN,
            disposition_scope=DispositionScope.UNKNOWN,
            dispute_stage=DisputeStage.NO_INDICIA_FOUND,
            instrument_language=data.instrument_language,
            local_authority_id=data.local_authority_id,
            subtype_id=legacy_subtype_id,
            legacy_matter_type=data.legacy_matter_type,
            activated_conditional_module_ids=legacy_modules,
            created_at=now,
            updated_at=now,
        )
        created = await self._matters.create(matter)
        await self._matters.append_classification(
            created,
            version=1,
            rule_pack_version=RULE_PACK_VERSION,
            changed_by=ctx.actor_id,
            reason=None,
        )
        await self._record(
            ctx,
            created,
            AuditAction.MATTER_CREATED,
            AuditTargetType.MATTER,
            created.id,
            after_ref=f"v{created.version}",
        )
        if data.legacy_matter_type is not None:
            await self._record(
                ctx,
                created,
                AuditAction.RTA_MATTER_LEGACY_MIGRATED,
                AuditTargetType.MATTER,
                created.id,
                before_ref=data.legacy_matter_type,
                after_ref=legacy_subtype_id,
                reason="Legacy M2 matter type migrated; exact subtype remains provisional.",
            )
        return created

    # ── Intake ───────────────────────────────────────────────────────────────

    async def save_answer(
        self,
        ctx: RequestContext,
        matter_id: str,
        question_id: str,
        *,
        value: object,
        lawyer_confirmed: bool,
        reason: str | None = None,
        inferred_from_fact_ids: tuple[str, ...] = (),
    ) -> IntakeAnswer:
        """Record an answer, superseding any previous one for that question."""
        matter = await self.get_matter(ctx, matter_id)
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=_to_summary(matter),
            capability=CAP_MATTER_ROUTE,
        )
        question = get_question(question_id)
        if question is None:
            raise UnknownQuestionError(f"Unknown intake question '{question_id}'.")
        _validate_answer_value(question_id, value)

        superseded_id = await self._answers.supersede(ctx.actor_id, matter_id, question_id)
        if superseded_id is not None:
            await self._record(
                ctx,
                matter,
                AuditAction.RTA_INTAKE_ANSWER_SUPERSEDED,
                AuditTargetType.INTAKE_ANSWER,
                superseded_id,
            )

        status = (
            AnswerStatus.LAWYER_CONFIRMED
            if lawyer_confirmed
            else (AnswerStatus.INFERRED if inferred_from_fact_ids else AnswerStatus.PROVISIONAL)
        )
        answer = await self._answers.create(
            IntakeAnswer(
                id=ids.new_id(ids.INTAKE_ANSWER),
                user_id=ctx.actor_id,
                matter_id=matter_id,
                question_definition_id=question_id,
                value=value,
                status=status,
                inferred_from_fact_ids=inferred_from_fact_ids,
                answered_by=ctx.actor_id,
                answer_reason=reason,
                supersedes_id=superseded_id,
                created_at=datetime.now(tz=UTC),
            )
        )
        await self._record(
            ctx,
            matter,
            AuditAction.RTA_INTAKE_ANSWER_RECORDED,
            AuditTargetType.INTAKE_ANSWER,
            answer.id,
            after_ref=question_id,
            reason=reason,
        )
        return answer

    async def confirm_subtype(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        subtype_id: str,
        declared_legal_basis: str | None = None,
        expected_version: int,
    ) -> Matter:
        """Only the responsible lawyer confirms the exact prescribed instrument.

        Everyone else can propose one; the confirmation is what unlocks
        drafting, so it is a legal act with a named author (§Executive 6).
        """
        matter = await self.get_matter(ctx, matter_id)
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=_to_summary(matter),
            capability=CAP_MATTER_CONFIRM_SUBTYPE,
        )
        subtype = get_subtype(subtype_id)
        if subtype is None:
            raise UnknownSubtypeError(f"Unknown RTA subtype '{subtype_id}'.")
        if subtype.requires_declared_legal_basis and not (declared_legal_basis or "").strip():
            raise LegalBasisRequiredError()

        updated = replace(
            matter,
            subtype_id=subtype.id,
            family_id=subtype.family_id,
            subtype_decision_status=SubtypeDecisionStatus.LAWYER_CONFIRMED,
            declared_legal_basis=declared_legal_basis,
        )
        saved = await self._matters.update(updated, expected_version)
        await self._matters.append_classification(
            saved,
            version=await self._matters.next_classification_version(saved.id),
            rule_pack_version=RULE_PACK_VERSION,
            changed_by=ctx.actor_id,
            reason="Exact instrument confirmed by the responsible lawyer.",
        )
        await self._record(
            ctx,
            saved,
            AuditAction.RTA_MATTER_SUBTYPE_CONFIRMED,
            AuditTargetType.MATTER,
            saved.id,
            before_ref=matter.subtype_id,
            after_ref=subtype.id,
        )
        return saved

    # ── Routing ──────────────────────────────────────────────────────────────

    async def route(
        self, ctx: RequestContext, matter_id: str, *, expected_version: int
    ) -> RoutingResult:
        """Re-evaluate regime, subtype, and automation scope from current state."""
        matter = await self.get_matter(ctx, matter_id)
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=_to_summary(matter),
            capability=CAP_MATTER_ROUTE,
        )
        derivation, decision = await self._evaluate(ctx, matter)

        target_state = _target_state(matter.rta_state, decision)
        updated = replace(
            matter,
            title_status=derivation.title_status,
            parcel_kind=derivation.parcel_kind,
            disposition_scope=derivation.disposition_scope,
            dispute_stage=derivation.dispute_stage,
            party_contexts=derivation.party_contexts,
            activated_conditional_module_ids=derivation.activated_conditional_module_ids,
            subtype_id=matter.subtype_id or derivation.subtype_id,
            family_id=matter.family_id or derivation.family_id,
            automation_scope=decision.automation_scope,
            automation_exclusion_reason_keys=tuple(
                gate.reason_key for gate in decision.gates if not gate.satisfied
            ),
            rta_state=target_state,
        )
        saved = await self._matters.update(updated, expected_version)

        await self._record(
            ctx,
            saved,
            AuditAction.RTA_MATTER_ROUTED,
            AuditTargetType.MATTER,
            saved.id,
            before_ref=matter.automation_scope.value,
            after_ref=saved.automation_scope.value,
        )
        if matter.automation_scope is not saved.automation_scope:
            await self._record(
                ctx,
                saved,
                AuditAction.RTA_MATTER_AUTOMATION_SCOPE_CHANGED,
                AuditTargetType.MATTER,
                saved.id,
                before_ref=matter.automation_scope.value,
                after_ref=saved.automation_scope.value,
                reason="; ".join(decision.unmet_gate_ids) or None,
            )
        if matter.rta_state is not saved.rta_state:
            await self._record(
                ctx,
                saved,
                AuditAction.RTA_MATTER_STATE_CHANGED,
                AuditTargetType.MATTER,
                saved.id,
                before_ref=matter.rta_state.value,
                after_ref=saved.rta_state.value,
            )
        return RoutingResult(
            matter=saved,
            derivation=derivation,
            decision=decision,
            next_question_ids=derivation.triggered_question_ids,
        )

    async def preview_routing(
        self, ctx: RequestContext, matter_id: str
    ) -> tuple[RoutingDerivation, EligibilityDecision]:
        """Evaluate without writing — used by the checklist preview screen."""
        matter = await self.get_matter(ctx, matter_id)
        return await self._evaluate(ctx, matter)

    async def _evaluate(
        self, ctx: RequestContext, matter: Matter
    ) -> tuple[RoutingDerivation, EligibilityDecision]:
        live = await self._answers.list_live(ctx.actor_id, matter.id)
        answer_map = {
            answer.question_definition_id: LiveAnswer(
                value=answer.value,
                lawyer_confirmed=answer.status is AnswerStatus.LAWYER_CONFIRMED,
            )
            for answer in live
        }
        derivation = derive_routing(answer_map)
        if matter.subtype_id and derivation.subtype_id is None:
            # A confirmed subtype outranks an unanswered Q02.
            subtype = get_subtype(matter.subtype_id)
            if subtype is not None:
                derivation = replace(derivation, subtype_id=subtype.id, family_id=subtype.family_id)

        facts: MatterFactSnapshot = await self._facts.snapshot(ctx.actor_id, matter.id)
        decision = evaluate(
            build_eligibility_input(
                derivation,
                facts,
                regime_id=matter.regime_id,
                subtype_decision_status=matter.subtype_decision_status,
                # No template in this repository is a lawyer-approved
                # production rendering, and no official source has been
                # re-verified, so both gates are false by construction (§9.5).
                template_verified=False,
                source_reverification_required=True,
                answers=answer_map,
            )
        )
        return derivation, decision

    # ── Checklist ────────────────────────────────────────────────────────────

    async def compile_checklist(
        self, ctx: RequestContext, matter_id: str, *, expected_version: int
    ) -> ChecklistCompileResult:
        """Compile a new snapshot from the current answers and confirmed facts."""
        matter = await self.get_matter(ctx, matter_id)
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=_to_summary(matter),
            capability=CAP_CHECKLIST_COMPILE,
        )
        derivation, _ = await self._evaluate(ctx, matter)
        compiler_input = CompilerInput(
            subtype_id=matter.subtype_id or derivation.subtype_id,
            activated_conditional_module_ids=derivation.activated_conditional_module_ids,
            suppressed_conditional_module_ids=matter.suppressed_conditional_module_ids,
            local_authority_id=matter.local_authority_id,
            previous_items=await self._previous_items(ctx, matter),
        )
        snapshot_id, compiled = await self._checklist.compile_snapshot(
            user_id=ctx.actor_id,
            matter_id=matter.id,
            compiler_input=compiler_input,
            actor_id=ctx.actor_id,
            correlation_id=ctx.correlation_id,
        )
        target_state = (
            MatterState.EVIDENCE_COLLECTION
            if is_transition_allowed(matter.rta_state, MatterState.EVIDENCE_COLLECTION)
            else matter.rta_state
        )
        saved = await self._matters.update(
            replace(matter, active_checklist_snapshot_id=snapshot_id, rta_state=target_state),
            expected_version,
        )
        await self._record(
            ctx,
            saved,
            AuditAction.RTA_CHECKLIST_COMPILED,
            AuditTargetType.CHECKLIST_SNAPSHOT,
            snapshot_id,
            before_ref=matter.active_checklist_snapshot_id,
            after_ref=compiled.fingerprint,
        )
        return ChecklistCompileResult(snapshot_id=snapshot_id, checklist=compiled, matter=saved)

    async def _previous_items(
        self, ctx: RequestContext, matter: Matter
    ) -> tuple[ReviewedItemMemo, ...]:
        # The task module owns item review state; until its read port exists the
        # compiler is told there is nothing to preserve, which is safe: the
        # retention rule only ever *adds* items back.
        _ = (ctx, matter)
        return ()

    # ── Transitions ──────────────────────────────────────────────────────────

    async def transition(
        self,
        ctx: RequestContext,
        matter_id: str,
        *,
        target: MatterState,
        expected_version: int,
        reason: str | None = None,
    ) -> Matter:
        matter = await self.get_matter(ctx, matter_id)
        if not is_transition_allowed(matter.rta_state, target):
            raise IllegalMatterTransitionError(
                f"Cannot move a matter from {matter.rta_state.value} to {target.value}.",
                fromState=matter.rta_state.value,
                toState=target.value,
            )
        saved = await self._matters.update(replace(matter, rta_state=target), expected_version)
        await self._record(
            ctx,
            saved,
            AuditAction.RTA_MATTER_STATE_CHANGED,
            AuditTargetType.MATTER,
            saved.id,
            before_ref=matter.rta_state.value,
            after_ref=target.value,
            reason=reason,
        )
        return saved

    # ── Audit ────────────────────────────────────────────────────────────────

    async def _record(
        self,
        ctx: RequestContext,
        matter: Matter,
        action: AuditAction,
        target_type: AuditTargetType,
        target_id: str,
        *,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=matter.id,
                actor=ctx.actor_id,
                action=action.value,
                target_type=target_type.value,
                target_id=target_id,
                before_ref=before_ref,
                after_ref=after_ref,
                reason=reason,
                correlation_id=ctx.correlation_id,
            )
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_summary(matter: Matter) -> MatterAccessSummary:
    return MatterAccessSummary(
        id=matter.id,
        user_id=matter.user_id,
        responsible_lawyer_id=matter.responsible_lawyer_id,
        regime_id=matter.regime_id,
        subtype_id=matter.subtype_id,
        subtype_decision_status=matter.subtype_decision_status,
        rta_state=matter.rta_state,
        automation_scope=matter.automation_scope,
        active_checklist_snapshot_id=matter.active_checklist_snapshot_id,
        version=matter.version,
    )


def _target_state(current: MatterState, decision: EligibilityDecision) -> MatterState:
    """Routing may move a matter forward to ROUTED or into an exception state.

    It never moves a matter backwards out of evidence work: a matter that has
    already collected documents stays where it is, with a changed automation
    scope, because losing that context is exactly what §2.3 forbids.
    """
    if decision.exception_state is not None and is_transition_allowed(
        current, decision.exception_state
    ):
        return decision.exception_state
    if current is MatterState.INTAKE_DRAFT:
        return MatterState.ROUTED
    return current


def _validate_answer_value(question_id: str, value: object) -> None:
    question = get_question(question_id)
    if question is None:
        raise UnknownQuestionError(f"Unknown intake question '{question_id}'.")
    kind = question.value_kind.value
    if kind == "TRI_STATE" and str(value) not in {"YES", "NO", "UNKNOWN", "NOT_APPLICABLE"}:
        raise InvalidAnswerValueError(
            f"{question_id} accepts YES, NO, UNKNOWN, or NOT_APPLICABLE.",
            questionId=question_id,
        )
    if kind == "SINGLE_CHOICE" and question.options:
        allowed = {option.value for option in question.options}
        if str(value) not in allowed:
            raise InvalidAnswerValueError(
                f"{question_id} does not accept that option.",
                questionId=question_id,
                allowed=sorted(allowed),
            )
    if kind == "MULTI_CHOICE" and question.options:
        allowed = {option.value for option in question.options}
        supplied = value if isinstance(value, list) else [value]
        unknown = [str(item) for item in supplied if str(item) not in allowed]
        if unknown:
            raise InvalidAnswerValueError(
                f"{question_id} does not accept those options.",
                questionId=question_id,
                unknown=unknown,
            )


__all__ = [
    "ChecklistCompileResult",
    "CreateMatterInput",
    "MatterService",
    "RoutingResult",
]

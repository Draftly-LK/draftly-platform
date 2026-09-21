"""MatterService: creation, intake answers, subtype confirmation, routing, transitions."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.modules.audit.domain.models import AuditAction
from src.modules.auth.domain.models import Role
from src.modules.content_governance.contracts import (
    RULE_PACK_VERSION,
    TRANSFER_SALE_SUBTYPE_ID,
    AnswerStatus,
    AutomationScope,
    DispositionScope,
    DisputeStage,
    MatterFamily,
    MatterState,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
)
from src.modules.matter.application.matter_service import (
    CreateMatterInput,
    MatterService,
    _target_state,
)
from src.modules.matter.domain.errors import (
    IllegalMatterTransitionError,
    InvalidAnswerValueError,
    LegalBasisRequiredError,
    MatterNotFoundError,
    MatterStaleError,
    UnknownLegacyMatterTypeError,
    UnknownQuestionError,
    UnknownSubtypeError,
)
from src.modules.matter.domain.models import InstrumentLanguage, MatterLifecycleStatus
from src.modules.matter.domain.routing import MODULE_COMPANY, MODULE_MORTGAGE
from src.modules.matter.tests.fakes import (
    CORRELATION,
    LAWYER_ID,
    OTHER_USER_ID,
    FakeChecklistPort,
    FakeFactPort,
    InMemoryAnswerRepository,
    InMemoryMatterRepository,
    RecordingAudit,
    ctx,
)
from src.platform.errors import CapabilityDeniedError, NotFoundError

OTHER_DECLARED = "lk.rta.instrument.other_declared_instrument"


@dataclass
class Harness:
    matters: InMemoryMatterRepository = field(default_factory=InMemoryMatterRepository)
    answers: InMemoryAnswerRepository = field(default_factory=InMemoryAnswerRepository)
    facts: FakeFactPort = field(default_factory=FakeFactPort)
    checklist: FakeChecklistPort = field(default_factory=FakeChecklistPort)
    audit: RecordingAudit = field(default_factory=RecordingAudit)

    @property
    def service(self) -> MatterService:
        return MatterService(
            matters=self.matters,
            answers=self.answers,
            facts=self.facts,
            checklist=self.checklist,
            audit=self.audit,
        )


@pytest.fixture
def h() -> Harness:
    return Harness()


async def _new_matter(h: Harness, **overrides: object) -> str:
    data = CreateMatterInput(reference="SYN/2026/001", **overrides)  # type: ignore[arg-type]
    return (await h.service.create_matter(ctx(), data)).id


# ── Creation ────────────────────────────────────────────────────────────────


async def test_new_matter_starts_as_an_unclassified_intake_draft(h: Harness) -> None:
    matter = await h.service.create_matter(
        ctx(),
        CreateMatterInput(reference="SYN/2026/001", instrument_language=InstrumentLanguage.SI),
    )

    assert matter.id.startswith("mat")
    assert matter.user_id == LAWYER_ID
    assert matter.responsible_lawyer_id == LAWYER_ID
    assert matter.lifecycle_status is MatterLifecycleStatus.INQUIRY
    assert matter.rta_state is MatterState.INTAKE_DRAFT
    assert matter.automation_scope is AutomationScope.ASSESSING
    # §12.4: the exact subtype is never defaulted.
    assert matter.subtype_id is None
    assert matter.subtype_decision_status is SubtypeDecisionStatus.PROVISIONAL
    assert matter.title_status is TitleStatus.UNKNOWN
    assert matter.instrument_language is InstrumentLanguage.SI
    assert matter.version == 1


async def test_creation_records_classification_v1_and_one_audit_event(h: Harness) -> None:
    matter_id = await _new_matter(h)

    assert h.matters.classifications == [
        {
            "matter_id": matter_id,
            "version": 1,
            "subtype_id": None,
            "rule_pack_version": RULE_PACK_VERSION,
            "changed_by": LAWYER_ID,
            "reason": None,
        }
    ]
    assert h.audit.actions() == [AuditAction.MATTER_CREATED.value]
    event = h.audit.events[0]
    assert (event.matter_id, event.target_id, event.after_ref) == (matter_id, matter_id, "v1")
    assert event.correlation_id == CORRELATION


async def test_explicit_responsible_lawyer_is_kept(h: Harness) -> None:
    matter_id = await _new_matter(h, responsible_lawyer_id="usr_partner")
    assert h.matters.matters[matter_id].responsible_lawyer_id == "usr_partner"


async def test_legacy_migration_proposes_a_subtype_but_never_confirms_it(h: Harness) -> None:
    matter = await h.service.create_matter(
        ctx(), CreateMatterInput(reference="SYN/LEGACY/1", legacy_matter_type="gift")
    )

    assert matter.subtype_id == "lk.rta.instrument.gift"
    assert matter.legacy_matter_type == "gift"
    assert matter.subtype_decision_status is SubtypeDecisionStatus.PROVISIONAL
    assert matter.activated_conditional_module_ids == frozenset({"lk.rta.module.life_interest"})
    assert h.audit.actions() == [
        AuditAction.MATTER_CREATED.value,
        AuditAction.RTA_MATTER_LEGACY_MIGRATED.value,
    ]
    migrated = h.audit.events[1]
    assert (migrated.before_ref, migrated.after_ref) == ("gift", "lk.rta.instrument.gift")


async def test_unmapped_legacy_type_is_reported_not_guessed(h: Harness) -> None:
    with pytest.raises(UnknownLegacyMatterTypeError) as excinfo:
        await h.service.create_matter(
            ctx(), CreateMatterInput(reference="SYN/LEGACY/2", legacy_matter_type="timeshare")
        )
    assert excinfo.value.code == "rta_legacy_type_unknown"
    assert h.matters.matters == {}
    assert h.audit.events == []


# ── Reads and tenancy ───────────────────────────────────────────────────────


async def test_another_users_matter_is_indistinguishable_from_a_missing_one(h: Harness) -> None:
    matter_id = await _new_matter(h)

    with pytest.raises(MatterNotFoundError) as foreign:
        await h.service.get_matter(ctx(OTHER_USER_ID), matter_id)
    with pytest.raises(MatterNotFoundError) as missing:
        await h.service.get_matter(ctx(), "mat_missing")

    assert foreign.value.http_status == missing.value.http_status == 404
    assert foreign.value.message == missing.value.message


async def test_list_matters_returns_only_the_callers(h: Harness) -> None:
    mine = await _new_matter(h)
    await h.service.create_matter(ctx(OTHER_USER_ID), CreateMatterInput(reference="SYN/X"))

    matters, cursor = await h.service.list_matters(ctx())

    assert [m.id for m in matters] == [mine]
    assert cursor is None


async def test_access_summary_mirrors_the_matter_and_is_tenant_scoped(h: Harness) -> None:
    matter_id = await _new_matter(h)

    summary = await h.service.get_access_summary(LAWYER_ID, matter_id)

    assert summary is not None
    assert (summary.id, summary.user_id, summary.version) == (matter_id, LAWYER_ID, 1)
    assert summary.rta_state is MatterState.INTAKE_DRAFT
    assert await h.service.get_access_summary(OTHER_USER_ID, matter_id) is None


# ── Intake answers ──────────────────────────────────────────────────────────


async def test_answer_status_reflects_how_the_answer_was_reached(h: Harness) -> None:
    matter_id = await _new_matter(h)
    save = h.service.save_answer

    confirmed = await save(ctx(), matter_id, "Q01_REGIME", value="YES", lawyer_confirmed=True)
    provisional = await save(ctx(), matter_id, "Q06_DISPUTE", value="NO", lawyer_confirmed=False)
    inferred = await save(
        ctx(),
        matter_id,
        "Q10_MORTGAGE",
        value="YES",
        lawyer_confirmed=False,
        inferred_from_fact_ids=("fct_1",),
    )

    assert confirmed.status is AnswerStatus.LAWYER_CONFIRMED
    assert provisional.status is AnswerStatus.PROVISIONAL
    assert inferred.status is AnswerStatus.INFERRED
    assert inferred.inferred_from_fact_ids == ("fct_1",)
    assert confirmed.answered_by == LAWYER_ID


async def test_a_new_answer_supersedes_the_old_one_and_keeps_it_in_history(h: Harness) -> None:
    matter_id = await _new_matter(h)
    first = await h.service.save_answer(
        ctx(), matter_id, "Q01_REGIME", value="UNKNOWN", lawyer_confirmed=False
    )
    second = await h.service.save_answer(
        ctx(), matter_id, "Q01_REGIME", value="YES", lawyer_confirmed=True, reason="TC sighted"
    )

    live = await h.service.list_answers(ctx(), matter_id)
    history = await h.service.list_answers(ctx(), matter_id, include_superseded=True)

    assert [a.id for a in live] == [second.id]
    assert [a.id for a in history] == [first.id, second.id]
    assert history[0].status is AnswerStatus.SUPERSEDED
    assert history[0].value == "UNKNOWN"
    assert second.supersedes_id == first.id
    assert h.audit.actions()[-2:] == [
        AuditAction.RTA_INTAKE_ANSWER_SUPERSEDED.value,
        AuditAction.RTA_INTAKE_ANSWER_RECORDED.value,
    ]
    assert h.audit.events[-1].reason == "TC sighted"


async def test_unknown_question_is_refused(h: Harness) -> None:
    matter_id = await _new_matter(h)
    with pytest.raises(UnknownQuestionError):
        await h.service.save_answer(
            ctx(), matter_id, "Q99_NOPE", value="YES", lawyer_confirmed=True
        )
    assert h.answers.answers == []


@pytest.mark.parametrize(
    ("question_id", "value", "detail_key"),
    [
        ("Q01_REGIME", "MAYBE", None),
        ("Q04_PARCEL_KIND", "HOUSEBOAT", "allowed"),
        ("Q05_PARTY_CONTEXT", ["COMPANY", "ALIENS"], "unknown"),
        ("Q05_PARTY_CONTEXT", "ALIENS", "unknown"),
    ],
)
async def test_values_outside_the_question_vocabulary_are_refused(
    h: Harness, question_id: str, value: object, detail_key: str | None
) -> None:
    matter_id = await _new_matter(h)

    with pytest.raises(InvalidAnswerValueError) as excinfo:
        await h.service.save_answer(
            ctx(), matter_id, question_id, value=value, lawyer_confirmed=True
        )

    assert excinfo.value.http_status == 422
    assert excinfo.value.details["questionId"] == question_id
    if detail_key == "unknown":
        assert excinfo.value.details["unknown"] == ["ALIENS"]
    if detail_key == "allowed":
        assert "ORDINARY" in excinfo.value.details["allowed"]
    assert h.answers.answers == []


async def test_valid_multi_choice_answer_is_stored_as_given(h: Harness) -> None:
    matter_id = await _new_matter(h)
    answer = await h.service.save_answer(
        ctx(),
        matter_id,
        "Q05_PARTY_CONTEXT",
        value=["COMPANY", "NATURAL_PERSONS_ONLY"],
        lawyer_confirmed=True,
    )
    assert answer.value == ["COMPANY", "NATURAL_PERSONS_ONLY"]


async def test_case_assistant_may_not_record_routing_answers(h: Harness) -> None:
    matter_id = await h.service.create_matter(
        ctx(role=Role.REVIEWER), CreateMatterInput(reference="SYN/R")
    )
    with pytest.raises(CapabilityDeniedError) as excinfo:
        await h.service.save_answer(
            ctx(role=Role.REVIEWER), matter_id.id, "Q01_REGIME", value="YES", lawyer_confirmed=True
        )
    assert excinfo.value.details["capability"] == "rta.matter.route"
    assert excinfo.value.details["workflowRole"] == "CASE_ASSISTANT"


async def test_answers_on_another_users_matter_are_not_found(h: Harness) -> None:
    matter_id = await _new_matter(h)
    with pytest.raises(NotFoundError):
        await h.service.save_answer(
            ctx(OTHER_USER_ID), matter_id, "Q01_REGIME", value="YES", lawyer_confirmed=True
        )
    with pytest.raises(NotFoundError):
        await h.service.list_answers(ctx(OTHER_USER_ID), matter_id)


# ── Subtype confirmation ────────────────────────────────────────────────────


async def test_responsible_lawyer_confirms_the_exact_instrument(h: Harness) -> None:
    matter_id = await _new_matter(h)

    saved = await h.service.confirm_subtype(
        ctx(), matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=1
    )

    assert saved.subtype_id == TRANSFER_SALE_SUBTYPE_ID
    assert saved.family_id is MatterFamily.OWNERSHIP_CHANGE
    assert saved.subtype_decision_status is SubtypeDecisionStatus.LAWYER_CONFIRMED
    assert saved.version == 2
    assert [c["version"] for c in h.matters.classifications] == [1, 2]
    assert h.matters.classifications[-1]["subtype_id"] == TRANSFER_SALE_SUBTYPE_ID
    event = h.audit.events[-1]
    assert event.action == AuditAction.RTA_MATTER_SUBTYPE_CONFIRMED.value
    assert (event.before_ref, event.after_ref) == (None, TRANSFER_SALE_SUBTYPE_ID)


async def test_a_member_who_is_not_the_responsible_lawyer_cannot_confirm(h: Harness) -> None:
    matter_id = await _new_matter(h, responsible_lawyer_id="usr_partner")

    with pytest.raises(CapabilityDeniedError) as excinfo:
        await h.service.confirm_subtype(
            ctx(), matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=1
        )

    assert excinfo.value.details["capability"] == "rta.matter.confirm-subtype"
    assert excinfo.value.details["workflowRole"] == "LAWYER_REVIEWER"
    assert h.matters.matters[matter_id].subtype_id is None


async def test_unknown_subtype_is_refused(h: Harness) -> None:
    matter_id = await _new_matter(h)
    with pytest.raises(UnknownSubtypeError):
        await h.service.confirm_subtype(
            ctx(), matter_id, subtype_id="lk.rta.instrument.nope", expected_version=1
        )


@pytest.mark.parametrize("basis", [None, "", "   "])
async def test_controlled_fallback_instrument_needs_a_declared_legal_basis(
    h: Harness, basis: str | None
) -> None:
    matter_id = await _new_matter(h)
    with pytest.raises(LegalBasisRequiredError) as excinfo:
        await h.service.confirm_subtype(
            ctx(),
            matter_id,
            subtype_id=OTHER_DECLARED,
            declared_legal_basis=basis,
            expected_version=1,
        )
    assert excinfo.value.code == "rta_legal_basis_required"
    assert h.matters.matters[matter_id].version == 1


async def test_controlled_fallback_instrument_is_accepted_with_a_basis(h: Harness) -> None:
    matter_id = await _new_matter(h)
    saved = await h.service.confirm_subtype(
        ctx(),
        matter_id,
        subtype_id=OTHER_DECLARED,
        declared_legal_basis="Synthetic s. 0 of a synthetic Act",
        expected_version=1,
    )
    assert saved.subtype_id == OTHER_DECLARED
    assert saved.declared_legal_basis == "Synthetic s. 0 of a synthetic Act"


async def test_stale_version_is_a_conflict_and_changes_nothing(h: Harness) -> None:
    matter_id = await _new_matter(h)
    events_before = len(h.audit.events)

    with pytest.raises(MatterStaleError) as excinfo:
        await h.service.confirm_subtype(
            ctx(), matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=7
        )

    assert excinfo.value.http_status == 409
    assert h.matters.matters[matter_id].subtype_id is None
    assert len(h.audit.events) == events_before


# ── Routing ─────────────────────────────────────────────────────────────────


async def test_routing_writes_the_derivation_and_moves_the_draft_forward(h: Harness) -> None:
    matter_id = await _new_matter(h)
    for question_id, value in [
        ("Q01_REGIME", "YES"),
        ("Q03_SCOPE", "WHOLE_REGISTERED_PARCEL"),
        ("Q04_PARCEL_KIND", "ORDINARY"),
        ("Q05_PARTY_CONTEXT", ["COMPANY"]),
        ("Q06_DISPUTE", "NO"),
    ]:
        await h.service.save_answer(
            ctx(), matter_id, question_id, value=value, lawyer_confirmed=True
        )

    result = await h.service.route(ctx(), matter_id, expected_version=1)

    matter = result.matter
    assert matter.title_status is TitleStatus.RTA_REGISTERED
    assert matter.parcel_kind is ParcelKind.ORDINARY
    assert matter.disposition_scope is DispositionScope.WHOLE_REGISTERED_PARCEL
    assert matter.party_contexts == frozenset({PartyContext.COMPANY})
    assert matter.dispute_stage is DisputeStage.NO_INDICIA_FOUND
    assert MODULE_COMPANY in matter.activated_conditional_module_ids
    # An unanswered mortgage question is UNKNOWN, and UNKNOWN is never "no".
    assert MODULE_MORTGAGE in matter.activated_conditional_module_ids
    assert matter.version == 2
    assert matter.rta_state is not MatterState.INTAKE_DRAFT
    assert "Q21_COMPANY_AUTH" in result.next_question_ids
    assert h.facts.calls == [(LAWYER_ID, matter_id)]


async def test_routing_never_grants_full_automation_without_a_verified_template(
    h: Harness,
) -> None:
    """Both template gates are false by construction (§9.5), whatever the answers say."""
    matter_id = await _new_matter(h)
    await h.service.confirm_subtype(
        ctx(), matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=1
    )

    result = await h.service.route(ctx(), matter_id, expected_version=2)

    assert result.decision.automation_scope is AutomationScope.MANUAL_SUPPORTED
    assert result.matter.automation_scope is result.decision.automation_scope
    unmet = tuple(g.reason_key for g in result.decision.gates if not g.satisfied)
    assert unmet
    assert result.matter.automation_exclusion_reason_keys == unmet
    scope_event = next(
        e
        for e in h.audit.events
        if e.action == AuditAction.RTA_MATTER_AUTOMATION_SCOPE_CHANGED.value
    )
    assert (scope_event.before_ref, scope_event.after_ref) == ("ASSESSING", "MANUAL_SUPPORTED")
    assert scope_event.reason == "; ".join(result.decision.unmet_gate_ids)


async def test_routing_audits_the_route_and_each_change_it_caused(h: Harness) -> None:
    matter_id = await _new_matter(h)
    before = len(h.audit.events)

    result = await h.service.route(ctx(), matter_id, expected_version=1)

    actions = h.audit.actions()[before:]
    assert actions[0] == AuditAction.RTA_MATTER_ROUTED.value
    assert AuditAction.RTA_MATTER_STATE_CHANGED.value in actions
    # Nothing is known yet, so the scope is still ASSESSING and no change is claimed.
    assert result.matter.automation_scope is AutomationScope.ASSESSING
    assert AuditAction.RTA_MATTER_AUTOMATION_SCOPE_CHANGED.value not in actions
    state_event = next(
        e for e in h.audit.events if e.action == AuditAction.RTA_MATTER_STATE_CHANGED.value
    )
    assert state_event.before_ref == "INTAKE_DRAFT"
    assert state_event.after_ref == result.matter.rta_state.value


async def test_a_confirmed_subtype_outranks_an_unanswered_intent_question(h: Harness) -> None:
    matter_id = await _new_matter(h)
    await h.service.confirm_subtype(
        ctx(), matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=1
    )

    derivation, _ = await h.service.preview_routing(ctx(), matter_id)

    assert derivation.subtype_id == TRANSFER_SALE_SUBTYPE_ID
    assert derivation.family_id is MatterFamily.OWNERSHIP_CHANGE


async def test_preview_writes_nothing(h: Harness) -> None:
    matter_id = await _new_matter(h)
    events_before = len(h.audit.events)

    await h.service.preview_routing(ctx(), matter_id)

    assert h.matters.matters[matter_id].version == 1
    assert h.matters.matters[matter_id].rta_state is MatterState.INTAKE_DRAFT
    assert len(h.audit.events) == events_before


async def test_routing_requires_the_route_capability_and_a_fresh_version(h: Harness) -> None:
    created = await h.service.create_matter(
        ctx(role=Role.REVIEWER), CreateMatterInput(reference="SYN/R")
    )
    with pytest.raises(CapabilityDeniedError):
        await h.service.route(ctx(role=Role.REVIEWER), created.id, expected_version=1)

    matter_id = await _new_matter(h)
    with pytest.raises(MatterStaleError):
        await h.service.route(ctx(), matter_id, expected_version=9)
    assert h.matters.matters[matter_id].rta_state is MatterState.INTAKE_DRAFT


def test_routing_never_moves_a_matter_backwards_out_of_evidence_work() -> None:
    from src.modules.content_governance.contracts import EligibilityDecision

    proceed = EligibilityDecision(
        automation_scope=AutomationScope.MANUAL_SUPPORTED, gates=(), exception_state=None
    )
    hold = EligibilityDecision(
        automation_scope=AutomationScope.LITIGATION_HOLD,
        gates=(),
        exception_state=MatterState.LITIGATION_HOLD,
    )

    assert _target_state(MatterState.INTAKE_DRAFT, proceed) is MatterState.ROUTED
    assert (
        _target_state(MatterState.EVIDENCE_COLLECTION, proceed) is MatterState.EVIDENCE_COLLECTION
    )
    assert _target_state(MatterState.EVIDENCE_COLLECTION, hold) is MatterState.LITIGATION_HOLD
    # INTAKE_DRAFT cannot jump straight to a hold; it is routed first.
    assert _target_state(MatterState.INTAKE_DRAFT, hold) is MatterState.ROUTED
    assert _target_state(MatterState.CLOSED, hold) is MatterState.CLOSED


# ── Checklist ───────────────────────────────────────────────────────────────


async def test_compiling_a_checklist_activates_the_snapshot_and_starts_evidence_work(
    h: Harness,
) -> None:
    matter_id = await _new_matter(h)
    await h.service.confirm_subtype(
        ctx(), matter_id, subtype_id=TRANSFER_SALE_SUBTYPE_ID, expected_version=1
    )
    await h.service.route(ctx(), matter_id, expected_version=2)
    assert h.matters.matters[matter_id].rta_state is MatterState.ROUTED

    result = await h.service.compile_checklist(ctx(), matter_id, expected_version=3)

    assert result.snapshot_id == "snp_1"
    assert result.checklist.items
    assert result.matter.active_checklist_snapshot_id == "snp_1"
    assert result.matter.version == 4
    assert result.matter.rta_state is MatterState.EVIDENCE_COLLECTION
    sent = h.checklist.inputs[0]
    assert sent.subtype_id == TRANSFER_SALE_SUBTYPE_ID
    assert sent.previous_items == ()
    event = h.audit.events[-1]
    assert event.action == AuditAction.RTA_CHECKLIST_COMPILED.value
    assert (event.target_id, event.after_ref) == ("snp_1", result.checklist.fingerprint)


async def test_compiling_from_an_intake_draft_does_not_skip_routing(h: Harness) -> None:
    matter_id = await _new_matter(h)
    result = await h.service.compile_checklist(ctx(), matter_id, expected_version=1)
    assert result.matter.rta_state is MatterState.INTAKE_DRAFT


async def test_office_admin_cannot_compile_a_checklist(h: Harness) -> None:
    created = await h.service.create_matter(
        ctx(role=Role.ADMINISTRATOR), CreateMatterInput(reference="SYN/A")
    )
    with pytest.raises(CapabilityDeniedError):
        await h.service.compile_checklist(
            ctx(role=Role.ADMINISTRATOR), created.id, expected_version=1
        )
    assert h.checklist.inputs == []


# ── Transitions ─────────────────────────────────────────────────────────────


async def test_legal_transition_is_saved_and_audited_with_its_reason(h: Harness) -> None:
    matter_id = await _new_matter(h)

    saved = await h.service.transition(
        ctx(),
        matter_id,
        target=MatterState.CANCELLED,
        expected_version=1,
        reason="Client withdrew.",
    )

    assert saved.rta_state is MatterState.CANCELLED
    assert saved.version == 2
    event = h.audit.events[-1]
    assert (event.before_ref, event.after_ref, event.reason) == (
        "INTAKE_DRAFT",
        "CANCELLED",
        "Client withdrew.",
    )


async def test_a_draft_cannot_jump_to_approved(h: Harness) -> None:
    matter_id = await _new_matter(h)
    events_before = len(h.audit.events)

    with pytest.raises(IllegalMatterTransitionError) as excinfo:
        await h.service.transition(
            ctx(), matter_id, target=MatterState.APPROVED, expected_version=1
        )

    assert excinfo.value.http_status == 422
    assert excinfo.value.details == {"fromState": "INTAKE_DRAFT", "toState": "APPROVED"}
    assert h.matters.matters[matter_id].rta_state is MatterState.INTAKE_DRAFT
    assert len(h.audit.events) == events_before


async def test_a_cancelled_matter_cannot_be_reopened(h: Harness) -> None:
    matter_id = await _new_matter(h)
    await h.service.transition(ctx(), matter_id, target=MatterState.CANCELLED, expected_version=1)
    with pytest.raises(IllegalMatterTransitionError):
        await h.service.transition(ctx(), matter_id, target=MatterState.ROUTED, expected_version=2)

"""Matter repositories, the fact-tier adapter, and the workflow command adapter.

No database: the session is scripted (tests/fixtures/scripted_session.py), and
the statements it records are checked for the tenancy predicate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    AnswerStatus,
    AutomationScope,
    DispositionScope,
    DisputeStage,
    EncumbranceStatus,
    MatterFamily,
    MatterState,
    NoticeStatus,
    OccupationStatus,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
    TriState,
)
from src.modules.matter.domain.errors import MatterStaleError
from src.modules.matter.domain.models import (
    InstrumentLanguage,
    IntakeAnswer,
    Matter,
    MatterLifecycleStatus,
    allowed_transitions,
    is_transition_allowed,
)
from src.modules.matter.infrastructure import fact_snapshot as fs
from src.modules.matter.infrastructure.orm import (
    IntakeAnswerRow,
    MatterClassificationRow,
    MatterRow,
)
from src.modules.matter.infrastructure.repository import (
    SqlIntakeAnswerRepository,
    SqlMatterRepository,
    _decode_cursor,
    _encode_cursor,
)
from src.modules.matter.infrastructure.workflow_commands import (
    DemoMatterWorkflowCommandAdapter,
    SqlMatterWorkflowCommandAdapter,
)
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary
from src.platform.errors import ConflictError
from src.platform.pagination import InvalidCursorError
from tests.fixtures.scripted_session import FakeSession

NOW = datetime(2026, 2, 3, 10, 0, tzinfo=UTC)


def _matter(**overrides: Any) -> Matter:
    values: dict[str, Any] = {
        "id": "mat_1",
        "user_id": "usr_1",
        "reference": "SYN/2026/001",
        "responsible_lawyer_id": "usr_1",
        "regime_id": "lk.rta",
        "lifecycle_status": MatterLifecycleStatus.ACTIVE,
        "rta_state": MatterState.ROUTED,
        "automation_scope": AutomationScope.MANUAL_SUPPORTED,
        "subtype_decision_status": SubtypeDecisionStatus.LAWYER_CONFIRMED,
        "title_status": TitleStatus.RTA_REGISTERED,
        "parcel_kind": ParcelKind.ORDINARY,
        "disposition_scope": DispositionScope.WHOLE_REGISTERED_PARCEL,
        "dispute_stage": DisputeStage.NO_INDICIA_FOUND,
        "created_at": NOW,
        "updated_at": NOW,
        "version": 3,
        "family_id": MatterFamily.OWNERSHIP_CHANGE,
        "subtype_id": "lk.rta.instrument.transfer_sale",
        "instrument_language": InstrumentLanguage.TA,
        "party_contexts": frozenset({PartyContext.COMPANY, PartyContext.PUBLIC_BODY}),
        "activated_conditional_module_ids": frozenset({"m.b", "m.a"}),
        "automation_exclusion_reason_keys": ("gate.one", "gate.two"),
    }
    values.update(overrides)
    return Matter(**values)


async def _stored_row(matter: Matter) -> MatterRow:
    """The row ``create`` writes for a matter, captured from the scripted session."""
    session = FakeSession()
    await SqlMatterRepository(cast(AsyncSession, session)).create(matter)
    return cast(MatterRow, session.added[0])


# ── State machine ───────────────────────────────────────────────────────────


def test_approval_is_only_reachable_from_approval_pending() -> None:
    sources = {s for s in MatterState if is_transition_allowed(s, MatterState.APPROVED)}
    assert sources == {MatterState.APPROVAL_PENDING, MatterState.APPROVED}


def test_terminal_states_have_no_exit() -> None:
    assert allowed_transitions(MatterState.CLOSED) == ()
    assert allowed_transitions(MatterState.CANCELLED) == ()


def test_a_same_state_transition_is_a_no_op_and_allowed() -> None:
    assert all(is_transition_allowed(state, state) for state in MatterState)


def test_export_is_not_registration() -> None:
    assert not is_transition_allowed(MatterState.EXPORTED, MatterState.REGISTERED)
    assert is_transition_allowed(MatterState.SUBMITTED, MatterState.REGISTERED)


def test_exception_states_can_return_to_evidence_work() -> None:
    for state in (MatterState.MANUAL_SUPPORTED, MatterState.LITIGATION_HOLD):
        assert MatterState.EVIDENCE_COLLECTION in allowed_transitions(state)


def test_allowed_transitions_are_sorted_for_stable_api_output() -> None:
    values = [s.value for s in allowed_transitions(MatterState.ROUTED)]
    assert values == sorted(values)


def test_closed_and_archived_matters_are_immutable() -> None:
    assert _matter(lifecycle_status=MatterLifecycleStatus.INQUIRY).is_mutable
    assert _matter(lifecycle_status=MatterLifecycleStatus.ACTIVE).is_mutable
    assert not _matter(lifecycle_status=MatterLifecycleStatus.CLOSED).is_mutable
    assert not _matter(lifecycle_status=MatterLifecycleStatus.ARCHIVED).is_mutable


# ── Matter repository ───────────────────────────────────────────────────────


async def test_create_round_trips_every_field_and_stores_sets_sorted() -> None:
    session = FakeSession()
    matter = _matter()

    stored = await SqlMatterRepository(cast(AsyncSession, session)).create(matter)

    assert stored == matter
    row = session.added[0]
    assert row.party_contexts == ["COMPANY", "PUBLIC_BODY"]
    assert row.activated_conditional_module_ids == ["m.a", "m.b"]
    assert row.rta_state == "ROUTED"
    assert row.instrument_language == "ta"


async def test_duplicate_reference_is_a_conflict_not_a_500() -> None:
    session = FakeSession()
    session.flush_error = IntegrityError(
        "INSERT", {}, Exception('violates unique constraint "uq_matters_user_reference"')
    )
    with pytest.raises(ConflictError, match="SYN/2026/001") as excinfo:
        await SqlMatterRepository(cast(AsyncSession, session)).create(_matter())
    assert excinfo.value.http_status == 409


async def test_other_integrity_errors_are_not_disguised_as_duplicates() -> None:
    session = FakeSession()
    session.flush_error = IntegrityError("INSERT", {}, Exception("fk_matters_user"))
    with pytest.raises(IntegrityError):
        await SqlMatterRepository(cast(AsyncSession, session)).create(_matter())


async def test_get_filters_on_the_tenant_before_the_id() -> None:
    session = FakeSession()
    session.queue()
    assert await SqlMatterRepository(cast(AsyncSession, session)).get("usr_2", "mat_1") is None
    where = session.where_clause()
    assert "matters.user_id = 'usr_2'" in where
    assert "matters.id = 'mat_1'" in where


async def test_list_returns_a_cursor_only_when_more_rows_exist() -> None:
    rows = [await _stored_row(_matter(id=f"mat_{n}", reference=f"R{n}")) for n in (3, 2, 1)]
    session = FakeSession()
    session.queue(*rows)
    session.queue(*rows[:2])
    repo = SqlMatterRepository(cast(AsyncSession, session))

    page, cursor = await repo.list_for_user("usr_1", limit=2, cursor=None)
    last_page, last_cursor = await repo.list_for_user("usr_1", limit=2, cursor=cursor)

    assert [m.id for m in page] == ["mat_3", "mat_2"]
    assert cursor is not None
    assert _decode_cursor(cursor) == (NOW, "mat_2")
    assert [m.id for m in last_page] == ["mat_3", "mat_2"]
    assert last_cursor is None
    assert "matters.user_id = 'usr_1'" in session.where_clause(0)
    # The second query is a keyset continuation, still tenant-scoped.
    assert "matters.user_id = 'usr_1'" in session.where_clause(1)
    assert "matters.id < 'mat_2'" in session.where_clause(1)


def test_a_tampered_cursor_is_rejected_rather_than_trusted() -> None:
    with pytest.raises(InvalidCursorError):
        _decode_cursor("not-base64-json")
    assert _decode_cursor(_encode_cursor(NOW, "mat_9")) == (NOW, "mat_9")


async def test_update_bumps_the_version_only_when_the_expected_version_matches() -> None:
    row = await _stored_row(_matter())
    session = FakeSession()
    session.queue("mat_1")
    session.queue(row)
    changed = _matter(rta_state=MatterState.EVIDENCE_COLLECTION)

    saved = await SqlMatterRepository(cast(AsyncSession, session)).update(changed, 3)

    assert saved.rta_state is MatterState.EVIDENCE_COLLECTION
    assert saved.updated_at > NOW
    statement = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "version=4" in statement.replace(" ", "")
    assert "matters.version = 3" in statement
    assert "matters.user_id = 'usr_1'" in statement


async def test_update_with_a_stale_version_raises_and_writes_nothing() -> None:
    session = FakeSession()
    session.queue()
    with pytest.raises(MatterStaleError) as excinfo:
        await SqlMatterRepository(cast(AsyncSession, session)).update(_matter(), 2)
    assert excinfo.value.details == {"expected_version": 2}
    assert session.flushes == 0


async def test_update_raises_stale_if_the_row_vanishes_mid_write() -> None:
    session = FakeSession()
    session.queue("mat_1")
    session.queue()
    with pytest.raises(MatterStaleError):
        await SqlMatterRepository(cast(AsyncSession, session)).update(_matter(), 3)


async def test_classification_versions_count_up_from_one() -> None:
    session = FakeSession()
    session.queue()
    session.queue(6)
    repo = SqlMatterRepository(cast(AsyncSession, session))
    assert await repo.next_classification_version("mat_1") == 1
    assert await repo.next_classification_version("mat_1") == 7


async def test_classification_snapshot_records_who_why_and_under_which_rule_pack() -> None:
    session = FakeSession()
    await SqlMatterRepository(cast(AsyncSession, session)).append_classification(
        _matter(local_authority_id="la_1"),
        version=2,
        rule_pack_version="rp-test",
        changed_by="usr_1",
        reason="Exact instrument confirmed.",
    )
    row = session.added[0]
    assert isinstance(row, MatterClassificationRow)
    assert (row.version, row.rule_pack_version, row.changed_by) == (2, "rp-test", "usr_1")
    assert row.reason == "Exact instrument confirmed."
    assert row.subtype_decision_status == "LAWYER_CONFIRMED"
    assert row.property_characteristics == {
        "partyContexts": ["COMPANY", "PUBLIC_BODY"],
        "conditionalModules": ["m.a", "m.b"],
        "localAuthorityId": "la_1",
    }
    assert row.execution_circumstances == {"instrumentLanguage": "ta"}


# ── Intake answer repository ────────────────────────────────────────────────


def _answer(**overrides: Any) -> IntakeAnswer:
    values: dict[str, Any] = {
        "id": "ans_1",
        "user_id": "usr_1",
        "matter_id": "mat_1",
        "question_definition_id": "Q01_REGIME",
        "value": "YES",
        "status": AnswerStatus.LAWYER_CONFIRMED,
        "created_at": NOW,
        "inferred_from_fact_ids": ("fct_1",),
        "answered_by": "usr_1",
        "answer_reason": "TC sighted",
    }
    values.update(overrides)
    return IntakeAnswer(**values)


@pytest.mark.parametrize(
    ("status", "flag"),
    [(AnswerStatus.LAWYER_CONFIRMED, True), (AnswerStatus.PROVISIONAL, False)],
)
async def test_answer_create_round_trips_and_derives_the_confirmed_flag(
    status: AnswerStatus, flag: bool
) -> None:
    session = FakeSession()
    answer = _answer(status=status)

    stored = await SqlIntakeAnswerRepository(cast(AsyncSession, session)).create(answer)

    assert stored == answer
    row = session.added[0]
    assert isinstance(row, IntakeAnswerRow)
    assert row.lawyer_confirmed is flag
    assert row.inferred_from_fact_ids == ["fct_1"]


async def test_supersede_marks_the_live_answer_and_returns_its_id() -> None:
    session = FakeSession()
    repo = SqlIntakeAnswerRepository(cast(AsyncSession, session))
    await repo.create(_answer())
    row = session.added[0]
    session.queue(row)

    assert await repo.supersede("usr_1", "mat_1", "Q01_REGIME") == "ans_1"

    assert row.status == "SUPERSEDED"
    assert row.value == "YES"
    where = session.where_clause()
    assert "intake_answers.user_id = 'usr_1'" in where
    assert "intake_answers.status != 'SUPERSEDED'" in where


async def test_supersede_with_no_live_answer_returns_none() -> None:
    session = FakeSession()
    session.queue()
    repo = SqlIntakeAnswerRepository(cast(AsyncSession, session))
    assert await repo.supersede("usr_1", "mat_1", "Q01_REGIME") is None
    assert session.flushes == 0


async def test_live_listing_excludes_superseded_answers_and_history_keeps_them() -> None:
    session = FakeSession()
    repo = SqlIntakeAnswerRepository(cast(AsyncSession, session))
    await repo.create(_answer())
    row = session.added[0]
    session.queue(row)
    session.queue(row)

    live = await repo.list_live("usr_1", "mat_1")
    history = await repo.list_all("usr_1", "mat_1")

    assert live == history == [_answer()]
    assert "status != 'SUPERSEDED'" in session.where_clause(0)
    assert "status" not in session.where_clause(1).split("ORDER BY")[0]
    for index in (0, 1):
        assert "intake_answers.user_id = 'usr_1'" in session.where_clause(index)
        assert "intake_answers.matter_id = 'mat_1'" in session.where_clause(index)


# ── Fact-tier adapter ───────────────────────────────────────────────────────


def _summary(conflicted: tuple[str, ...] = (), **values: Any) -> FactTierSummary:
    confirmed = {
        fact_type_id: ConfirmedFactValue(
            fact_id=f"fct_{n}", fact_type_id=fact_type_id, value=value, version=1
        )
        for n, (fact_type_id, value) in enumerate(values.items())
    }
    return FactTierSummary(confirmed=confirmed, conflicted_fact_type_ids=conflicted)


def test_nothing_confirmed_projects_to_not_reviewed_never_to_no() -> None:
    snapshot = fs.to_matter_fact_snapshot(
        FactTierSummary(unconfirmed_critical_fact_type_ids=("rta.instrument.consideration",))
    )
    assert snapshot.transferor_is_registered_owner is TriState.UNKNOWN
    assert snapshot.title_certificate_available is TriState.UNKNOWN
    assert snapshot.mortgage_status is EncumbranceStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.lease_status is EncumbranceStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.occupation_status is OccupationStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.notice_status is NoticeStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.active_court_proceeding is TriState.UNKNOWN
    assert snapshot.discharge_evidence_sufficient is TriState.UNKNOWN
    assert snapshot.identifier_conflict_present is False
    assert snapshot.identified_mortgage_reference is False
    assert snapshot.unconfirmed_critical_fact_type_ids == ("rta.instrument.consideration",)


def test_confirmed_facts_are_projected_onto_the_gate_vocabulary() -> None:
    snapshot = fs.to_matter_fact_snapshot(
        _summary(
            **{
                fs.FACT_TRANSFEROR_IS_OWNER: True,
                fs.FACT_COOWNERS: False,
                fs.FACT_LIFE_INTEREST: "no",
                fs.FACT_TITLE_CERTIFICATE: "TC-0000",
                fs.FACT_MORTGAGE_STATUS: "APPARENTLY_UNCANCELLED",
                fs.FACT_LEASE_STATUS: "NOT_FOUND_IN_CURRENT_SEARCH",
                fs.FACT_OCCUPATION_STATUS: "OWNER_OCCUPIED",
                fs.FACT_NOTICE_STATUS: "PRESENT_UNRESOLVED",
                fs.FACT_COURT_PROCEEDING: "DC/SYN/1",
                fs.FACT_MORTGAGE_REFERENCE: "M-1",
                fs.FACT_MORTGAGEE_AUTHORITY: "YES",
            }
        )
    )
    assert snapshot.transferor_is_registered_owner is TriState.YES
    assert snapshot.coowners_present is TriState.NO
    assert snapshot.life_interest_present is TriState.NO
    assert snapshot.title_certificate_available is TriState.YES
    assert snapshot.mortgage_status is EncumbranceStatus.APPARENTLY_UNCANCELLED
    assert snapshot.lease_status is EncumbranceStatus.NOT_FOUND_IN_CURRENT_SEARCH
    assert snapshot.occupation_status is OccupationStatus.OWNER_OCCUPIED
    assert snapshot.notice_status is NoticeStatus.PRESENT_UNRESOLVED
    assert snapshot.active_court_proceeding is TriState.YES
    assert snapshot.identified_mortgage_reference is True
    assert snapshot.mortgagee_authority_confirmed is TriState.YES


def test_unrecognised_confirmed_values_become_review_work_not_a_no() -> None:
    snapshot = fs.to_matter_fact_snapshot(
        _summary(
            **{
                fs.FACT_TRANSFEROR_IS_OWNER: "probably",
                fs.FACT_MORTGAGE_STATUS: "PAID_OFF_I_THINK",
                fs.FACT_OCCUPATION_STATUS: "SQUATTERS",
                fs.FACT_NOTICE_STATUS: "??",
            }
        )
    )
    assert snapshot.transferor_is_registered_owner is TriState.UNKNOWN
    assert snapshot.mortgage_status is EncumbranceStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.occupation_status is OccupationStatus.NO_EVIDENCE_REVIEWED
    assert snapshot.notice_status is NoticeStatus.NO_EVIDENCE_REVIEWED


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("NONE", TriState.NO),
        ("payment_receipt_only", TriState.NO),
        ("REGISTERED_CANCELLATION", TriState.YES),
    ],
)
def test_a_payment_receipt_alone_is_not_sufficient_discharge_evidence(
    kind: str, expected: TriState
) -> None:
    snapshot = fs.to_matter_fact_snapshot(_summary(**{fs.FACT_DISCHARGE_EVIDENCE: kind}))
    assert snapshot.discharge_evidence_sufficient is expected


def test_any_conflicted_fact_is_an_identifier_conflict() -> None:
    snapshot = fs.to_matter_fact_snapshot(_summary(conflicted=("rta.parcel.extent",)))
    assert snapshot.identifier_conflict_present is True


def test_the_cancellation_route_is_never_established_by_extraction() -> None:
    snapshot = fs.to_matter_fact_snapshot(
        _summary(**{fs.FACT_MORTGAGE_STATUS: "CANCELLATION_REGISTERED"})
    )
    assert snapshot.cancellation_route_confirmed is TriState.UNKNOWN


async def test_adapter_reads_through_the_verification_port() -> None:
    calls: list[tuple[str, str]] = []

    class Reader:
        async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
            calls.append((user_id, matter_id))
            return _summary(**{fs.FACT_COOWNERS: True})

    adapter = fs.SqlMatterFactAdapter(cast(AsyncSession, object()), reader=Reader())
    snapshot = await adapter.snapshot("usr_1", "mat_1")

    assert calls == [("usr_1", "mat_1")]
    assert snapshot.coowners_present is TriState.YES


# ── Workflow command adapter ────────────────────────────────────────────────


async def test_a_recorded_act_advances_the_matter_when_the_state_machine_allows() -> None:
    row = await _stored_row(_matter(rta_state=MatterState.APPROVAL_PENDING))
    session = FakeSession()
    session.queue(row)
    session.queue("mat_1")
    session.queue(row)

    await SqlMatterWorkflowCommandAdapter(cast(AsyncSession, session)).advance_state(
        user_id="usr_1", matter_id="mat_1", state=MatterState.APPROVED, reason="approval recorded"
    )

    assert row.rta_state == "APPROVED"
    assert len(session.statements) == 3


async def test_a_matter_on_litigation_hold_is_not_jumped_to_approved() -> None:
    row = await _stored_row(_matter(rta_state=MatterState.LITIGATION_HOLD))
    session = FakeSession()
    session.queue(row)

    with structlog.testing.capture_logs() as logs:
        await SqlMatterWorkflowCommandAdapter(cast(AsyncSession, session)).advance_state(
            user_id="usr_1", matter_id="mat_1", state=MatterState.APPROVED, reason="approval"
        )

    assert row.rta_state == "LITIGATION_HOLD"
    assert len(session.statements) == 1
    assert [entry["event"] for entry in logs] == ["matter.advance_state.refused"]
    assert (logs[0]["from_state"], logs[0]["to_state"]) == ("LITIGATION_HOLD", "APPROVED")


async def test_advancing_to_the_current_state_writes_nothing() -> None:
    row = await _stored_row(_matter(rta_state=MatterState.APPROVED))
    session = FakeSession()
    session.queue(row)
    await SqlMatterWorkflowCommandAdapter(cast(AsyncSession, session)).advance_state(
        user_id="usr_1", matter_id="mat_1", state=MatterState.APPROVED, reason="again"
    )
    assert len(session.statements) == 1


async def test_a_missing_matter_is_logged_and_skipped() -> None:
    session = FakeSession()
    session.queue()
    with structlog.testing.capture_logs() as logs:
        await SqlMatterWorkflowCommandAdapter(cast(AsyncSession, session)).advance_state(
            user_id="usr_1", matter_id="mat_gone", state=MatterState.APPROVED, reason="approval"
        )
    assert [entry["event"] for entry in logs] == ["matter.advance_state.matter_missing"]
    assert len(session.statements) == 1


# ── Demo workflow adapter (DEMO_RELAXED_GATES) ──────────────────────────────


async def test_demo_adapter_takes_every_step_from_review_to_drafting() -> None:
    row = await _stored_row(_matter(rta_state=MatterState.LEGAL_REVIEW))
    session = FakeSession()
    session.queue(row)  # where the matter stands
    for _ in range(2):  # READY_TO_DRAFT, then DRAFTING: read, write, re-read
        session.queue(row)
        session.queue("mat_1")
        session.queue(row)

    with structlog.testing.capture_logs() as logs:
        await DemoMatterWorkflowCommandAdapter(cast(AsyncSession, session)).advance_state(
            user_id="usr_1", matter_id="mat_1", state=MatterState.DRAFTING, reason="form"
        )

    assert row.rta_state == "DRAFTING"
    assert len(session.statements) == 7
    assert logs == []


async def test_demo_adapter_leaves_moves_off_the_drafting_path_to_the_base_rules() -> None:
    row = await _stored_row(_matter(rta_state=MatterState.LITIGATION_HOLD))
    session = FakeSession()
    session.queue(row)
    session.queue(row)

    with structlog.testing.capture_logs() as logs:
        await DemoMatterWorkflowCommandAdapter(cast(AsyncSession, session)).advance_state(
            user_id="usr_1", matter_id="mat_1", state=MatterState.APPROVED, reason="approval"
        )

    assert row.rta_state == "LITIGATION_HOLD"
    assert [entry["event"] for entry in logs] == ["matter.advance_state.refused"]

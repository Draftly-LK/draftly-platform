"""Fact-tier repositories and read adapters over a scripted session (no database)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    CRITICAL_FACT_TYPE_IDS,
    EvidenceRegionType,
    FactStatus,
    ReviewTargetType,
)
from src.modules.verification.domain.models import (
    BoundingBox,
    EvidenceReference,
    ExtractedFact,
    ReviewDecision,
)
from src.modules.verification.infrastructure.orm import (
    EvidenceReferenceRow,
    ExtractedFactRow,
    ReviewDecisionRow,
)
from src.modules.verification.infrastructure.repository import (
    SEARCH_EVIDENCE_FACT_TYPE_ID,
    SqlConfirmedFactReader,
    SqlEvidenceReader,
    SqlVerificationRepository,
    as_json,
    utc_now,
)
from tests.fixtures.scripted_session import FakeSession

NOW = datetime(2026, 1, 5, 9, 30, tzinfo=UTC)
CRITICAL = "rta.instrument.consideration"
NON_CRITICAL = "rta.parcel.village"


def _repo(session: FakeSession) -> SqlVerificationRepository:
    return SqlVerificationRepository(cast(AsyncSession, session))


def _fact_row(
    fact_id: str, fact_type_id: str, status: FactStatus, **overrides: Any
) -> ExtractedFactRow:
    values: dict[str, Any] = {
        "id": fact_id,
        "user_id": "usr_1",
        "matter_id": "mat_1",
        "fact_type_id": fact_type_id,
        "subject_id": None,
        "value": "v",
        "normalized_value": None,
        "status": status.value,
        "model_reported_confidence": None,
        "evidence_reference_ids": ["evr_1"],
        "derivation_kind": None,
        "derivation_input_fact_ids": [],
        "derivation_formula_version": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "review_decision_id": None,
        "supersedes_fact_id": None,
        "superseded_by_fact_id": None,
        "locked_by_form_id": None,
        "version": 1,
        "created_at": NOW,
    }
    values.update(overrides)
    return ExtractedFactRow(**values)


def _evidence_row(evidence_id: str, page: int, **overrides: Any) -> EvidenceReferenceRow:
    values: dict[str, Any] = {
        "id": evidence_id,
        "user_id": "usr_1",
        "matter_id": "mat_1",
        "source_file_id": f"src_{evidence_id}",
        "detected_document_id": None,
        "page_number": page,
        "source_sha256": "a" * 64,
        "bounding_box": None,
        "text_span": None,
        "region_type": None,
        "extraction_run_id": None,
        "created_at": NOW,
    }
    values.update(overrides)
    return EvidenceReferenceRow(**values)


# ── Domain model properties ─────────────────────────────────────────────────


def _fact(status: FactStatus, **overrides: Any) -> ExtractedFact:
    return ExtractedFact(
        id="fct_1",
        user_id="usr_1",
        matter_id="mat_1",
        fact_type_id=CRITICAL,
        value="1000000",
        status=status,
        created_at=NOW,
        **overrides,
    )


def test_only_a_human_confirmed_or_form_locked_fact_counts_as_confirmed() -> None:
    confirmed = {status for status in FactStatus if _fact(status).is_confirmed}
    assert confirmed == {FactStatus.LAWYER_CONFIRMED, FactStatus.LOCKED_FOR_FORM}


def test_a_superseded_fact_is_not_live() -> None:
    assert _fact(FactStatus.LAWYER_CONFIRMED).is_live is True
    assert _fact(FactStatus.SUPERSEDED).is_live is False
    assert _fact(FactStatus.LAWYER_CONFIRMED, superseded_by_fact_id="fct_2").is_live is False


# ── Evidence ────────────────────────────────────────────────────────────────


async def test_create_evidence_round_trips_the_bounding_box_and_hash() -> None:
    session = FakeSession()
    evidence = EvidenceReference(
        id="evr_1",
        user_id="usr_1",
        matter_id="mat_1",
        source_file_id="src_1",
        page_number=3,
        source_sha256="b" * 64,
        created_at=NOW,
        bounding_box=BoundingBox(
            x=1.5, y=2.0, width=30.0, height=4.0, coordinate_space="px@200dpi"
        ),
        text_span="Rs. 1,000,000",
        region_type=EvidenceRegionType.HANDWRITING,
        extraction_run_id="run_1",
        detected_document_id="doc_1",
    )

    stored = await _repo(session).create_evidence(evidence)

    assert stored == evidence
    assert session.flushes == 1
    row = session.added[0]
    assert isinstance(row, EvidenceReferenceRow)
    assert row.bounding_box == {
        "x": 1.5,
        "y": 2.0,
        "width": 30.0,
        "height": 4.0,
        "coordinateSpace": "px@200dpi",
    }
    assert row.region_type == "HANDWRITING"
    assert row.source_sha256 == "b" * 64


async def test_create_evidence_without_a_box_stores_none() -> None:
    session = FakeSession()
    evidence = EvidenceReference(
        id="evr_2",
        user_id="usr_1",
        matter_id="mat_1",
        source_file_id="src_1",
        page_number=1,
        source_sha256="c" * 64,
        created_at=NOW,
    )
    stored = await _repo(session).create_evidence(evidence)
    assert session.added[0].bounding_box is None
    assert session.added[0].region_type is None
    assert stored.bounding_box is None
    assert stored.region_type is None


async def test_list_evidence_with_no_ids_does_not_query() -> None:
    session = FakeSession()
    assert await _repo(session).list_evidence("usr_1", ()) == []
    assert session.statements == []


async def test_list_evidence_preserves_requested_order_and_drops_missing() -> None:
    session = FakeSession()
    session.queue(_evidence_row("evr_a", 1), _evidence_row("evr_b", 2))

    found = await _repo(session).list_evidence("usr_1", ("evr_b", "evr_missing", "evr_a"))

    assert [ref.id for ref in found] == ["evr_b", "evr_a"]
    where = session.where_clause()
    assert "evidence_references.user_id = 'usr_1'" in where
    assert "'evr_missing'" in where


async def test_evidence_reader_returns_source_file_and_page_pairs() -> None:
    session = FakeSession()
    session.queue(_evidence_row("evr_a", 4), _evidence_row("evr_b", 9))

    pages = await SqlEvidenceReader(cast(AsyncSession, session)).source_pages(
        "usr_1", ("evr_b", "evr_a")
    )

    assert pages == (("src_evr_b", 9), ("src_evr_a", 4))


# ── Facts ───────────────────────────────────────────────────────────────────


async def test_create_fact_persists_status_value_and_lineage() -> None:
    session = FakeSession()
    fact = ExtractedFact(
        id="fct_2",
        user_id="usr_1",
        matter_id="mat_1",
        fact_type_id=CRITICAL,
        value="1000000",
        normalized_value=1000000,
        status=FactStatus.LAWYER_CONFIRMED,
        created_at=NOW,
        version=2,
        model_reported_confidence=0.91,
        evidence_reference_ids=("evr_1", "evr_2"),
        derivation_input_fact_ids=("fct_0",),
        reviewed_by="usr_1",
        reviewed_at=NOW,
        review_decision_id="rvd_1",
        supersedes_fact_id="fct_1",
    )

    stored = await _repo(session).create_fact(fact)

    row = session.added[0]
    assert isinstance(row, ExtractedFactRow)
    assert row.status == "LAWYER_CONFIRMED"
    assert row.evidence_reference_ids == ["evr_1", "evr_2"]
    assert row.supersedes_fact_id == "fct_1"
    # A new version is never born already superseded.
    assert row.superseded_by_fact_id is None
    assert stored == fact


async def test_get_fact_is_scoped_to_the_owner_and_hides_a_miss() -> None:
    session = FakeSession()
    session.queue()
    assert await _repo(session).get_fact("usr_other", "fct_1") is None
    where = session.where_clause()
    assert "extracted_facts.user_id = 'usr_other'" in where
    assert "extracted_facts.id = 'fct_1'" in where


async def test_get_fact_maps_the_row() -> None:
    session = FakeSession()
    session.queue(_fact_row("fct_1", CRITICAL, FactStatus.REVIEW_REQUIRED, version=3))
    fact = await _repo(session).get_fact("usr_1", "fct_1")
    assert fact is not None
    assert fact.status is FactStatus.REVIEW_REQUIRED
    assert fact.version == 3
    assert fact.evidence_reference_ids == ("evr_1",)


async def test_mark_superseded_keeps_the_original_value() -> None:
    session = FakeSession()
    row = _fact_row("fct_1", CRITICAL, FactStatus.LAWYER_CONFIRMED, value="original")
    session.queue(row)

    await _repo(session).mark_superseded("usr_1", "fct_1", superseded_by_fact_id="fct_2")

    assert row.status == "SUPERSEDED"
    assert row.superseded_by_fact_id == "fct_2"
    assert row.value == "original"
    assert session.flushes == 1


async def test_mark_superseded_on_another_tenants_fact_changes_nothing() -> None:
    session = FakeSession()
    session.queue()
    await _repo(session).mark_superseded("usr_other", "fct_1", superseded_by_fact_id="fct_2")
    assert session.flushes == 0


async def test_lock_for_form_records_the_form_and_status() -> None:
    session = FakeSession()
    row = _fact_row("fct_1", CRITICAL, FactStatus.LAWYER_CONFIRMED)
    session.queue(row)

    await _repo(session).lock_for_form("usr_1", "fct_1", form_id="frm_1")

    assert row.status == "LOCKED_FOR_FORM"
    assert row.locked_by_form_id == "frm_1"


async def test_lock_for_form_on_a_missing_fact_changes_nothing() -> None:
    session = FakeSession()
    session.queue()
    await _repo(session).lock_for_form("usr_1", "fct_none", form_id="frm_1")
    assert session.flushes == 0


async def test_live_facts_exclude_superseded_versions_but_history_does_not() -> None:
    session = FakeSession()
    session.queue(_fact_row("fct_1", CRITICAL, FactStatus.LAWYER_CONFIRMED))
    session.queue(_fact_row("fct_1", CRITICAL, FactStatus.LAWYER_CONFIRMED))
    repo = _repo(session)

    live = await repo.list_live_facts("usr_1", "mat_1")
    history = await repo.list_all_facts("usr_1", "mat_1")

    assert [f.id for f in live] == [f.id for f in history] == ["fct_1"]
    live_where, history_where = session.where_clause(0), session.where_clause(1)
    assert "superseded_by_fact_id IS NULL" in live_where
    assert "superseded_by_fact_id" not in history_where
    for where in (live_where, history_where):
        assert "extracted_facts.user_id = 'usr_1'" in where
        assert "extracted_facts.matter_id = 'mat_1'" in where


async def test_next_version_starts_at_one_and_increments() -> None:
    session = FakeSession()
    session.queue()
    session.queue(4)
    repo = _repo(session)
    assert await repo.next_version("usr_1", "mat_1", CRITICAL) == 1
    assert await repo.next_version("usr_1", "mat_1", CRITICAL) == 5


# ── Review decisions ────────────────────────────────────────────────────────


def _decision() -> ReviewDecision:
    return ReviewDecision(
        id="rvd_1",
        user_id="usr_1",
        matter_id="mat_1",
        target_type=ReviewTargetType.FACT,
        target_id="fct_1",
        decision="CORRECTED",
        reviewer_id="usr_1",
        reviewer_role="approver",
        created_at=NOW,
        previous_value="100000",
        new_value="1000000",
        reason="Transposed digit on page 2.",
    )


async def test_decisions_are_recorded_as_human_unless_stated_otherwise() -> None:
    session = FakeSession()
    repo = _repo(session)

    returned = await repo.create_decision(_decision())
    await repo.create_decision(_decision(), human=False)

    assert returned == _decision()
    human_row, machine_row = session.added
    assert isinstance(human_row, ReviewDecisionRow)
    assert human_row.human_decision is True
    assert machine_row.human_decision is False
    assert human_row.target_type == "FACT"
    assert (human_row.previous_value, human_row.new_value) == ("100000", "1000000")


async def test_list_decisions_maps_rows_and_filters_by_target_type() -> None:
    session = FakeSession()
    row = ReviewDecisionRow(
        id="rvd_1",
        user_id="usr_1",
        matter_id="mat_1",
        target_type="FACT",
        target_id="fct_1",
        decision="CORRECTED",
        previous_value="100000",
        new_value="1000000",
        reason="Transposed digit on page 2.",
        reviewer_id="usr_1",
        reviewer_role="approver",
        human_decision=True,
        created_at=NOW,
    )
    session.queue(row)
    session.queue(row)
    repo = _repo(session)

    unfiltered = await repo.list_decisions("usr_1", "mat_1")
    filtered = await repo.list_decisions("usr_1", "mat_1", target_type=ReviewTargetType.FACT)

    assert unfiltered == filtered == [_decision()]
    assert "target_type" not in session.where_clause(0)
    assert "review_decisions.target_type = 'FACT'" in session.where_clause(1)
    assert "review_decisions.user_id = 'usr_1'" in session.where_clause(1)


# ── Confirmed-fact reader (the eligibility gates' view) ─────────────────────


async def _summarise(*rows: ExtractedFactRow) -> Any:
    session = FakeSession()
    session.queue(*rows)
    return await SqlConfirmedFactReader(cast(AsyncSession, session)).summarise("usr_1", "mat_1")


async def test_empty_matter_reports_every_critical_fact_as_unconfirmed() -> None:
    summary = await _summarise()
    assert summary.confirmed == {}
    assert set(summary.unconfirmed_critical_fact_type_ids) == set(CRITICAL_FACT_TYPE_IDS)
    assert list(summary.unconfirmed_critical_fact_type_ids) == sorted(CRITICAL_FACT_TYPE_IDS)
    assert summary.conflicted_fact_type_ids == ()
    assert summary.has_current_search_evidence is False


async def test_unreviewed_candidates_never_appear_as_confirmed() -> None:
    summary = await _summarise(
        _fact_row("fct_1", CRITICAL, FactStatus.EXTRACTED_CANDIDATE, model_reported_confidence=1.0),
        _fact_row("fct_2", NON_CRITICAL, FactStatus.CORROBORATED),
        _fact_row("fct_3", NON_CRITICAL, FactStatus.REVIEW_REQUIRED),
    )
    assert summary.confirmed == {}
    assert CRITICAL in summary.unconfirmed_critical_fact_type_ids


async def test_confirmed_and_locked_facts_are_reported_with_their_version() -> None:
    summary = await _summarise(
        _fact_row("fct_1", CRITICAL, FactStatus.LAWYER_CONFIRMED, value="1000000", version=2),
        _fact_row("fct_2", NON_CRITICAL, FactStatus.LOCKED_FOR_FORM, value="Kandy"),
    )
    assert set(summary.confirmed) == {CRITICAL, NON_CRITICAL}
    confirmed = summary.confirmed[CRITICAL]
    assert (confirmed.fact_id, confirmed.value, confirmed.version) == ("fct_1", "1000000", 2)
    assert confirmed.evidence_reference_ids == ("evr_1",)
    assert CRITICAL not in summary.unconfirmed_critical_fact_type_ids
    assert len(summary.unconfirmed_critical_fact_type_ids) == len(CRITICAL_FACT_TYPE_IDS) - 1


async def test_the_later_confirmed_version_wins_regardless_of_row_order() -> None:
    summary = await _summarise(
        _fact_row("fct_new", CRITICAL, FactStatus.LAWYER_CONFIRMED, value="new", version=3),
        _fact_row("fct_old", CRITICAL, FactStatus.LAWYER_CONFIRMED, value="old", version=1),
    )
    assert summary.confirmed[CRITICAL].fact_id == "fct_new"
    assert summary.confirmed[CRITICAL].value == "new"


async def test_conflicts_are_reported_once_each_and_sorted() -> None:
    summary = await _summarise(
        _fact_row("fct_1", NON_CRITICAL, FactStatus.CONFLICTED),
        _fact_row("fct_2", NON_CRITICAL, FactStatus.CONFLICTED),
        _fact_row("fct_3", CRITICAL, FactStatus.CONFLICTED),
    )
    assert summary.conflicted_fact_type_ids == tuple(sorted({CRITICAL, NON_CRITICAL}))
    assert summary.confirmed == {}


async def test_search_evidence_requires_a_confirmed_register_search() -> None:
    candidate = await _summarise(
        _fact_row("fct_1", SEARCH_EVIDENCE_FACT_TYPE_ID, FactStatus.REVIEW_REQUIRED)
    )
    confirmed = await _summarise(
        _fact_row("fct_1", SEARCH_EVIDENCE_FACT_TYPE_ID, FactStatus.LAWYER_CONFIRMED)
    )
    assert candidate.has_current_search_evidence is False
    assert confirmed.has_current_search_evidence is True


# ── Helpers ─────────────────────────────────────────────────────────────────


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().tzinfo is UTC


def test_as_json_unwraps_enums_and_passes_plain_values_through() -> None:
    class Colour(Enum):
        RED = "red"

    assert as_json(Colour.RED) == "red"
    assert as_json(FactStatus.CONFLICTED) == "CONFLICTED"
    assert as_json({"a": 1}) == {"a": 1}
    assert as_json(None) is None

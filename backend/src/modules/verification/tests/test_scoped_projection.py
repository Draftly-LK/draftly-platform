"""Regressions for subject collapse and silent conflict selection."""

from src.modules.content_governance.contracts import FactStatus
from src.modules.verification.tests.test_repository import _fact_row, _summarise

TYPE = "rta.parcel.village"


async def test_two_subjects_keep_values_and_withhold_legacy_binding() -> None:
    result = await _summarise(
        _fact_row(
            "f_a", TYPE, FactStatus.LAWYER_CONFIRMED, subject_id="sub_a", value="Synthetic A"
        ),
        _fact_row(
            "f_b",
            TYPE,
            FactStatus.LAWYER_CONFIRMED,
            subject_id="sub_b",
            value="Synthetic B",
            version=2,
        ),
    )
    assert TYPE not in result.confirmed
    assert {(f.subject_id, f.value) for f in result.scoped_confirmed} == {
        ("sub_a", "Synthetic A"),
        ("sub_b", "Synthetic B"),
    }


async def test_competing_values_in_one_scope_never_choose_latest() -> None:
    result = await _summarise(
        _fact_row(
            "f_a", TYPE, FactStatus.LAWYER_CONFIRMED, subject_id="sub_a", value="Synthetic A"
        ),
        _fact_row(
            "f_b",
            TYPE,
            FactStatus.LAWYER_CONFIRMED,
            subject_id="sub_a",
            value="Synthetic B",
            version=2,
        ),
    )
    assert TYPE not in result.confirmed
    assert result.scoped_confirmed == ()
    assert result.conflicted_fact_type_ids == (TYPE,)


async def test_transactions_keep_the_same_subject_separate() -> None:
    result = await _summarise(
        _fact_row(
            "f_a", TYPE, FactStatus.LAWYER_CONFIRMED, subject_id="sub_a", transaction_id="txn_a"
        ),
        _fact_row(
            "f_b", TYPE, FactStatus.LAWYER_CONFIRMED, subject_id="sub_a", transaction_id="txn_b"
        ),
    )
    assert TYPE not in result.confirmed
    assert {f.transaction_id for f in result.scoped_confirmed} == {"txn_a", "txn_b"}


async def test_stale_or_explicitly_unassigned_facts_are_ineligible() -> None:
    for fields in ({"evidence_stale": True}, {"scope_status": "unassigned"}):
        result = await _summarise(_fact_row("f_a", TYPE, FactStatus.LAWYER_CONFIRMED, **fields))
        assert result.confirmed == {}
        assert result.scoped_confirmed == ()


async def test_competing_unreviewed_value_blocks_confirmed_scope() -> None:
    result = await _summarise(
        _fact_row(
            "f_a", TYPE, FactStatus.LAWYER_CONFIRMED, subject_id="sub_a", value="Synthetic A"
        ),
        _fact_row(
            "f_b", TYPE, FactStatus.EXTRACTED_CANDIDATE, subject_id="sub_a", value="Synthetic B"
        ),
    )
    assert TYPE not in result.confirmed
    assert result.conflicted_fact_type_ids == (TYPE,)

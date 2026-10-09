"""Regressions for subject collapse and silent conflict selection."""

from src.modules.content_governance.contracts import FORM_TEMPLATES, FactStatus
from src.modules.draft.domain.policies import resolve_template
from src.modules.verification.tests.test_repository import _fact_row, _summarise

TYPE = "rta.parcel.village"


async def test_different_types_cannot_form_a_composite_from_different_scopes() -> None:
    for transaction, subject in (("txn_b", "sub_a"), ("txn_a", "sub_b"), (None, None)):
        result = await _summarise(
            _fact_row(
                "number_a",
                "rta.parcel.parcel_number",
                FactStatus.LAWYER_CONFIRMED,
                transaction_id="txn_a",
                subject_id="sub_a",
                value="SYNTHETIC A",
            ),
            _fact_row(
                "extent_b",
                "rta.parcel.extent",
                FactStatus.LAWYER_CONFIRMED,
                transaction_id=transaction,
                subject_id=subject,
                value="1.23",
            ),
        )
        assert {f.fact_id for f in result.scoped_confirmed} == {"number_a", "extent_b"}
        assert result.confirmed == {}
        form = next(t for t in FORM_TEMPLATES if t.id == "rta.reg.2022.form.08")
        assert not any(f.fact_id for f in resolve_template(form, facts=result))


async def test_coherent_single_scope_keeps_compatibility_bindings() -> None:
    result = await _summarise(
        *(
            _fact_row(
                identity,
                kind,
                FactStatus.LAWYER_CONFIRMED,
                transaction_id="txn_a",
                subject_id="sub_a",
                value=value,
            )
            for identity, kind, value in (
                ("number", "rta.parcel.parcel_number", "SYNTHETIC A"),
                ("extent", "rta.parcel.extent", "1.23"),
            )
        )
    )
    assert len(result.confirmed) == 2


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


async def test_independent_unassigned_observations_are_gaps_not_scope_conflicts() -> None:
    result = await _summarise(
        _fact_row(
            "first",
            TYPE,
            FactStatus.LAWYER_CONFIRMED,
            value="Synthetic A",
            scope_status="unassigned",
        ),
        _fact_row(
            "second",
            TYPE,
            FactStatus.LAWYER_CONFIRMED,
            value="Synthetic B",
            scope_status="unassigned",
        ),
    )
    assert result.confirmed == {} and result.scoped_confirmed == ()
    assert result.conflicted_fact_type_ids == ()
    assert result.scoped_conflicts == ()
    assert all(gap[3] == "unassigned" for gap in result.scoped_gaps)
    assert len(result.scoped_gaps) == 2


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

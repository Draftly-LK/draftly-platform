"""Exact reviewed scopes remain separate through checks and association corrections."""

import pytest

from src.bootstrap import build_check_service, build_matter_scope_service
from src.modules.check.tests.fakes import FakeFactReader
from src.modules.content_governance.contracts import CheckOutcome
from src.modules.verification.contracts import ConfirmedFactValue, FactTierSummary
from src.platform.errors import NotFoundError, PreconditionFailedError
from tests.db.test_document_interpretations import reviewed_candidate
from tests.db.test_scoped_fact_review import matter as matter


async def scopes(session, matter):
    ctx, _, _, _ = await reviewed_candidate(session, matter)
    service = build_matter_scope_service(session)
    tx = (await service.list_transactions(ctx, matter.matter_id))[0]
    first = tx.parcel_subject_ids[0]
    second = await service.create_subject(ctx, matter.matter_id, kind="parcel", key="second-parcel")
    tx = await service.create_transaction(
        ctx,
        matter.matter_id,
        transaction_id=tx.id,
        expected_version=tx.version,
        parcel_subject_ids=(first, second.id),
        party_roles=tx.party_roles,
        key="two-parcels",
    )
    return ctx, tx, first, second.id


async def test_checks_select_exact_scope_and_never_borrow_a_search(db_session, matter):
    ctx, tx, first, second = await scopes(db_session, matter)
    service = build_check_service(db_session)
    mortgage = ConfirmedFactValue(
        "fact_mortgage",
        "rta.interest.mortgage_status",
        "NOT_FOUND_IN_CURRENT_SEARCH",
        7,
        ("evr_mortgage",),
        tx.id,
        first,
        "associated",
    )
    search = ConfirmedFactValue(
        "fact_search",
        "rta.title.register_search_datetime",
        "2026-10-01",
        4,
        ("evr_search",),
        tx.id,
        second,
        "associated",
    )
    # Reader contract is lossless; deliberately tempting compatibility map must not be consumed.
    service._facts = FakeFactReader(
        FactTierSummary(
            confirmed={mortgage.fact_type_id: mortgage, search.fact_type_id: search},
            scoped_confirmed=(mortgage, search),
            has_current_search_evidence=True,
        )
    )
    run = await service.run_checks(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-check",
        transaction_id=tx.id,
        subject_id=first,
        association_version=tx.version,
    )
    result = next(row for row in run.results if row.check_definition_id == "CHK_MORTGAGE_STATUS")
    assert result.outcome is CheckOutcome.INCONCLUSIVE
    assert result.transaction_id == tx.id and result.subject_id == first
    assert result.association_version == tx.version
    assert all(
        pin.fact_id != search.fact_id for row in run.results for pin in row.input_fact_versions
    )
    second_run = await service.run_checks(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-second-check",
        transaction_id=tx.id,
        subject_id=second,
        association_version=tx.version,
    )
    issues, _ = await service.list_issues(
        user_id=ctx.actor_id, matter_id=matter.matter_id, limit=100
    )
    mortgage_issues = [
        row for row in issues if row.issue_type_id == "rta.issue.mortgage_unresolved"
    ]
    assert {row.subject_id for row in mortgage_issues} == {first, second}
    assert second_run.run_id != run.run_id
    changed = await build_matter_scope_service(db_session).create_transaction(
        ctx,
        matter.matter_id,
        transaction_id=tx.id,
        expected_version=tx.version,
        parcel_subject_ids=(second,),
        party_roles=tx.party_roles,
        key="remove-first",
    )
    gates = await service.gates(ctx.actor_id, matter.matter_id)
    assert gates.stale_check_ids and gates.blocks_approval
    historical, _ = await service.list_results(
        user_id=ctx.actor_id, matter_id=matter.matter_id, limit=100
    )
    assert any(row.id == result.id and row.association_version == tx.version for row in historical)
    with pytest.raises(PreconditionFailedError):
        await service.run_checks(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            actor_id=ctx.actor_id,
            correlation_id="synthetic-stale-scope",
            transaction_id=tx.id,
            subject_id=second,
            association_version=tx.version,
        )
    assert changed.version == tx.version + 1


async def test_checks_refuse_foreign_transaction(db_session, matter):
    ctx, tx, first, _ = await scopes(db_session, matter)
    with pytest.raises(NotFoundError):
        await build_check_service(db_session).run_checks(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            actor_id=ctx.actor_id,
            correlation_id="foreign-scope",
            transaction_id="transaction_foreign",
            subject_id=first,
            association_version=tx.version,
        )


@pytest.mark.parametrize("change", ["correct", "competing", "association"])
async def test_review_changes_invalidate_exact_check_and_approved_form_pins(
    db_session, matter, change
):
    from sqlalchemy import select

    from src.bootstrap import build_fact_review_service
    from src.modules.check.infrastructure.orm import CrossDocumentCheckRow
    from src.modules.draft.infrastructure.orm import GeneratedFormFieldRow, GeneratedFormRow
    from src.modules.verification.application.review_service import ManualFactInput, ReviewFactInput
    from src.platform.ids import new_id

    ctx, _, fact, _ = await reviewed_candidate(db_session, matter)
    scope_service = build_matter_scope_service(db_session)
    tx = await scope_service.get_transaction(ctx, matter.matter_id, fact.transaction_id)
    check = CrossDocumentCheckRow(
        id=new_id("check"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        check_definition_id="CHK_SYNTHETIC",
        check_definition_version="1",
        run_id=new_id("run"),
        transaction_id=tx.id,
        subject_id=fact.subject_id,
        association_version=tx.version,
        outcome="PASS",
        default_severity="HIGH_RISK",
        explanation_key="synthetic.pass",
        input_fact_versions=[{"factId": fact.id, "version": fact.version}],
    )
    unrelated = CrossDocumentCheckRow(
        id=new_id("check"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        check_definition_id="CHK_OTHER",
        check_definition_version="1",
        run_id=new_id("run"),
        transaction_id="synthetic-other",
        subject_id="synthetic-other",
        association_version=1,
        outcome="PASS",
        default_severity="HIGH_RISK",
        explanation_key="synthetic.pass",
        input_fact_versions=[{"factId": "synthetic-other", "version": 1}],
    )
    form = GeneratedFormRow(
        id=new_id("form"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        template_id="synthetic-template",
        template_version="1",
        form_version=1,
        state="APPROVED",
        subtype_id="rta.subtype.transfer_sale",
        approved_artifact_hash="synthetic-hash",
        rule_pack_version="1",
        created_by=ctx.actor_id,
    )
    db_session.add_all([check, unrelated, form])
    await db_session.flush()
    field = GeneratedFormFieldRow(
        id=new_id("field"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        generated_form_id=form.id,
        field_id="synthetic-field",
        fact_id=fact.id,
        fact_version=fact.version,
        rendered_value="SYNTHETIC VALUE",
        critical=True,
        required=True,
        order=1,
        evidence_reference_ids=list(fact.evidence_reference_ids),
    )
    db_session.add(field)
    await db_session.flush()
    review = build_fact_review_service(db_session)
    if change == "correct":
        view = await review.get_view(ctx, matter.matter_id, fact.id)
        await review.decide(
            ctx,
            matter.matter_id,
            fact.id,
            ReviewFactInput(
                "correct",
                fact.version,
                value="SYNTHETIC CORRECTED",
                reason="Synthetic correction",
                expected_scope_token=view.scope_token,
            ),
            key="correct-pin",
        )
    elif change == "competing":
        await review.add_manual(
            ctx,
            matter.matter_id,
            ManualFactInput(
                fact.fact_type_id,
                "SYNTHETIC COMPETING",
                "Synthetic conflict",
                transaction_id=tx.id,
                subject_id=fact.subject_id,
            ),
            key="competing-pin",
        )
    else:
        await scope_service.create_transaction(
            ctx,
            matter.matter_id,
            transaction_id=tx.id,
            expected_version=tx.version,
            parcel_subject_ids=tx.parcel_subject_ids,
            party_roles=(),
            key="association-pin",
        )
    await db_session.refresh(form)
    assert form.state == "STALE_AFTER_APPROVAL"
    assert form.approved_artifact_hash == "synthetic-hash"
    assert field.rendered_value == "SYNTHETIC VALUE" and field.fact_id == fact.id
    rows = list(
        (
            await db_session.execute(
                select(CrossDocumentCheckRow).where(
                    CrossDocumentCheckRow.matter_id == matter.matter_id
                )
            )
        ).scalars()
    )
    stale = [row for row in rows if row.explanation_key == "rta.check.input_changed"]
    assert len(stale) == 1 and stale[0].input_fact_versions == check.input_fact_versions
    assert stale[0].association_version == tx.version
    assert unrelated.outcome == "PASS" and check.outcome == "PASS"


async def seed_blocking_issue(checks, run):
    from dataclasses import replace

    from src.modules.content_governance.contracts import IssueSeverity
    from src.platform.ids import new_id

    await checks._repo.create_issue(
        replace(run.raised_issues[0], id=new_id("issue"), severity=IssueSeverity.BLOCKING)
    )


@pytest.mark.parametrize(
    "scope_state", ["detached", "attached", "role", "missing", "unavailable", "transaction"]
)
async def test_current_stale_gates_preserve_history_and_issues(db_session, matter, scope_state):
    from unittest.mock import AsyncMock

    from src.modules.matter.contracts import TransactionPartyRole

    ctx, tx, first, second = await scopes(db_session, matter)
    scope_service = build_matter_scope_service(db_session)
    if scope_state == "role":
        party = await scope_service.create_subject(
            ctx, matter.matter_id, kind="party", key="synthetic-role-party"
        )
        tx = await scope_service.create_transaction(
            ctx,
            matter.matter_id,
            transaction_id=tx.id,
            expected_version=tx.version,
            parcel_subject_ids=tx.parcel_subject_ids,
            party_roles=(TransactionPartyRole(party.id, "owner"),),
            key="synthetic-initial-role",
        )
    checks = build_check_service(db_session)
    args = {
        "user_id": ctx.actor_id,
        "matter_id": matter.matter_id,
        "actor_id": ctx.actor_id,
        "correlation_id": "synthetic-currentness",
        "transaction_id": tx.id,
        "subject_id": (
            None
            if scope_state == "transaction"
            else tx.party_roles[0].subject_id
            if scope_state == "role"
            else first
        ),
    }
    run = await checks.run_checks(**args, association_version=tx.version)
    await seed_blocking_issue(checks, run)
    prior_issues, _ = await checks.list_issues(
        user_id=ctx.actor_id, matter_id=matter.matter_id, limit=100
    )
    changed = await scope_service.create_transaction(
        ctx,
        matter.matter_id,
        transaction_id=tx.id,
        expected_version=tx.version,
        parcel_subject_ids=(first, second) if scope_state == "attached" else (second,),
        party_roles=(TransactionPartyRole(tx.party_roles[0].subject_id, "other"),)
        if scope_state == "role"
        else (),
        key="synthetic-currentness-change",
    )
    if scope_state in {"missing", "unavailable"}:
        checks._scopes.transaction = AsyncMock(
            return_value=None,
            side_effect=RuntimeError("Synthetic scope outage")
            if scope_state == "unavailable"
            else None,
        )
    gates = await checks.gates(ctx.actor_id, matter.matter_id)
    history, _ = await checks.list_results(
        user_id=ctx.actor_id, matter_id=matter.matter_id, limit=100
    )
    markers = {row.id for row in history if row.explanation_key == "rta.check.input_changed"}
    assert markers and {row.id for row in run.results} <= {row.id for row in history}
    assert all(row.association_version == tx.version for row in history)
    after_issues, _ = await checks.list_issues(
        user_id=ctx.actor_id, matter_id=matter.matter_id, limit=100
    )
    assert after_issues == prior_issues
    assert gates.open_blocking_issue_ids and gates.blocks_approval and gates.blocks_draft_generation
    if scope_state == "detached":
        assert not gates.stale_check_ids
        reattached = await scope_service.create_transaction(
            ctx,
            matter.matter_id,
            transaction_id=tx.id,
            expected_version=changed.version,
            parcel_subject_ids=(first, second),
            party_roles=(),
            key="synthetic-reattach",
        )
        assert set((await checks.gates(ctx.actor_id, matter.matter_id)).stale_check_ids) == markers
        await checks.run_checks(**args, association_version=reattached.version)
        fresh_gates = await checks.gates(ctx.actor_id, matter.matter_id)
        assert not fresh_gates.stale_check_ids and fresh_gates.open_blocking_issue_ids
        history, _ = await checks.list_results(
            user_id=ctx.actor_id, matter_id=matter.matter_id, limit=100
        )
        assert markers <= {row.id for row in history}
    else:
        assert set(gates.stale_check_ids) == markers

"""Synthetic interpretation corrections on migrated PostgreSQL; no provider calls."""

import pytest
from sqlalchemy import select, update

from src.bootstrap import (
    build_checklist_service,
    build_fact_review_service,
    build_ingestion_service,
    build_matter_scope_service,
    build_source_file_storage,
)
from src.modules.check.infrastructure.orm import CrossDocumentCheckRow
from src.modules.content_governance.contracts import TRANSFER_SALE_SUBTYPE_ID, CompilerInput
from src.modules.document.contracts import FactEvidenceLocator
from src.modules.document.infrastructure.fact_reader import SqlDocumentFactReader
from src.modules.document.infrastructure.orm import (
    DetectedDocumentRow,
    DocumentFragmentRow,
    DocumentInterpretationRow,
    ProcessingCandidateFieldRow,
    ProcessingLogicalDocumentRow,
)
from src.modules.document.infrastructure.repository import SqlDocumentIngestionRepository
from src.modules.draft.infrastructure.orm import GeneratedFormFieldRow, GeneratedFormRow
from src.modules.task.infrastructure.orm import ChecklistItemRow, SatisfactionLinkRow
from src.modules.verification.application.review_service import ManualFactInput, ReviewFactInput
from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader
from src.platform.errors import DomainRuleError
from src.platform.ids import new_id
from tests.db.test_scoped_fact_review import machine_candidate
from tests.db.test_scoped_fact_review import matter as matter


async def reviewed_candidate(session, matter):
    ctx, txn, candidate = await machine_candidate(session, matter)
    service = build_fact_review_service(session)
    party = await build_matter_scope_service(session).create_subject(
        ctx, matter.matter_id, kind="party", key="synthetic-holder"
    )
    associated = await service.decide(
        ctx,
        matter.matter_id,
        candidate,
        ReviewFactInput(
            "associate", 1, reason="Synthetic holder", transaction_id=txn, subject_id=party.id
        ),
        key="synthetic-associate",
    )
    accepted = await service.decide_candidate(
        ctx, matter.matter_id, candidate, action="accept", expected_version=associated.version
    )
    view = await service.get_view(ctx, matter.matter_id, accepted.id)
    document = await session.get(DetectedDocumentRow, view.evidence[0].detected_document_id)
    document.boundary_status = "CONFIRMED"
    await session.execute(
        update(DocumentFragmentRow)
        .where(DocumentFragmentRow.detected_document_id == document.id)
        .values(boundary_status="CONFIRMED")
    )
    await session.flush()
    return ctx, candidate, accepted, view.evidence[0].detected_document_id


async def test_correction_immediately_withholds_reviewed_authority_and_preserves_history(
    db_session, matter
):
    ctx, candidate, accepted, document_id = await reviewed_candidate(db_session, matter)
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert any(value.fact_id == accepted.id for value in summary.scoped_confirmed)
    document = await db_session.get(DetectedDocumentRow, document_id)
    await build_ingestion_service(db_session).decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id="rta.doc.title_certificate",
        actor_id=ctx.actor_id,
        correlation_id="synthetic-correction",
        expected_version=document.version,
    )
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert not any(value.fact_id == accepted.id for value in summary.scoped_confirmed)
    service = build_fact_review_service(db_session)
    history = await service.history(ctx, matter.matter_id, accepted.id)
    assert history.facts[0].original_value == "199900000000"
    assert history.decisions[-1].decision == "accept"
    with pytest.raises(DomainRuleError):
        await service.decide_candidate(
            ctx, matter.matter_id, candidate, action="accept", expected_version=accepted.version
        )


async def test_same_class_confirmation_keeps_reviewed_authority(db_session, matter):
    ctx, _, accepted, document_id = await reviewed_candidate(db_session, matter)
    document = await db_session.get(DetectedDocumentRow, document_id)
    await build_ingestion_service(db_session).decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id=document.class_id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-unchanged",
        expected_version=document.version,
    )
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert any(value.fact_id == accepted.id for value in summary.scoped_confirmed)


async def test_manual_evidence_pins_generation_and_unrelated_manual_fact_stays_current(
    db_session, matter
):
    ctx, _, accepted, document_id = await reviewed_candidate(db_session, matter)
    service = build_fact_review_service(db_session)
    original = await service.get_view(ctx, matter.matter_id, accepted.id)
    ref = original.evidence[0]
    with_evidence = await service.add_manual(
        ctx,
        matter.matter_id,
        ManualFactInput(
            "rta.parcel.village",
            "SYNTHETIC VILLAGE",
            "Synthetic reading",
            evidence=FactEvidenceLocator(
                ref.source_file_id,
                ref.page_number,
                ref.source_sha256,
                detected_document_id=document_id,
            ),
        ),
        key="manual-evidence",
    )
    unrelated = await service.add_manual(
        ctx,
        matter.matter_id,
        ManualFactInput(
            "rta.parcel.village",
            "SYNTHETIC OTHER",
            "Synthetic instructions",
        ),
        key="manual-unrelated",
    )
    manual_view = await service.get_view(ctx, matter.matter_id, with_evidence.id)
    assert manual_view.evidence[0].interpretation_generation == 1
    document = await db_session.get(DetectedDocumentRow, document_id)
    await build_ingestion_service(db_session).decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id="rta.doc.title_certificate",
        actor_id=ctx.actor_id,
        correlation_id="synthetic-manual-correction",
        expected_version=document.version,
    )
    assert (await service.get_view(ctx, matter.matter_id, with_evidence.id)).fact.evidence_stale
    assert not (await service.get_view(ctx, matter.matter_id, unrelated.id)).fact.evidence_stale


async def test_populated_correction_refuses_lossy_downgrade(db_session, matter):
    from importlib import import_module
    from unittest.mock import patch

    ctx, _, _, document_id = await reviewed_candidate(db_session, matter)
    document = await db_session.get(DetectedDocumentRow, document_id)
    await build_ingestion_service(db_session).decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id="rta.doc.title_certificate",
        actor_id=ctx.actor_id,
        correlation_id="synthetic-rollback",
        expected_version=document.version,
    )
    migration = import_module("migrations.versions.document_0003_interpretations")

    def downgrade(session):
        with patch("alembic.op.get_bind", return_value=session.connection()):
            with pytest.raises(RuntimeError, match="Cannot downgrade document interpretations"):
                migration.downgrade()

    await db_session.run_sync(downgrade)
    assert (await db_session.get(DetectedDocumentRow, document_id)).interpretation_generation == 2


async def test_returning_to_old_type_does_not_revive_old_candidates(db_session, matter):
    ctx, candidate, _, document_id = await reviewed_candidate(db_session, matter)
    await build_checklist_service(db_session).compile_snapshot(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        compiler_input=CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID),
        actor_id=ctx.actor_id,
        correlation_id="synthetic-checklist",
    )
    service = build_ingestion_service(db_session)
    for class_id in ("rta.doc.title_certificate", "rta.doc.nic"):
        document = await service.get_detected_document(
            user_id=ctx.actor_id, document_id=document_id
        )
        await service.decide_classification(
            user_id=ctx.actor_id,
            document_id=document_id,
            class_id=class_id,
            actor_id=ctx.actor_id,
            correlation_id="synthetic-return",
            expected_version=document.document.version,
        )
    observation = await SqlDocumentFactReader(
        db_session, build_source_file_storage()
    ).get_candidate(ctx.actor_id, matter.matter_id, candidate)
    assert observation.current is False
    historical = await SqlDocumentIngestionRepository(db_session).get_document_review(
        ctx.actor_id, document_id
    )
    assert historical.interpretation_generation == 1
    assert historical.current is False
    assert historical.pages[0].source_file_id == observation.evidence.source_file_id


async def test_failed_refresh_keeps_prior_generation_historical_and_records_failure(
    db_session, matter, monkeypatch
):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "vision-stub")
    monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "false")
    import src.platform.config as config

    config._settings = None
    ctx, candidate, accepted, document_id = await reviewed_candidate(db_session, matter)
    service = build_ingestion_service(db_session)
    document = await service.get_detected_document(user_id=ctx.actor_id, document_id=document_id)
    corrected = await service.decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id="rta.doc.title_certificate",
        actor_id=ctx.actor_id,
        correlation_id="synthetic-failed-refresh",
        expected_version=document.document.version,
    )
    for _ in range(2):
        corrected = await service.refresh_extraction(
            user_id=ctx.actor_id,
            document_id=document_id,
            actor_id=ctx.actor_id,
            correlation_id="synthetic-failed-refresh",
            expected_version=corrected.document.version,
        )
        assert corrected.document.extraction_state == "failed"
        assert corrected.document.refresh_failure_reason == "DATA_PROTECTION_GATE"
        assert corrected.document.interpretation_generation == 2
    assert not (
        await SqlDocumentFactReader(db_session, build_source_file_storage()).get_candidate(
            ctx.actor_id, matter.matter_id, candidate
        )
    ).current
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert accepted.id not in {item.fact_id for item in summary.scoped_confirmed}


async def test_refresh_uses_confirmed_type_appends_candidates_and_keeps_original(
    db_session, matter, monkeypatch
):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "vision-stub")
    monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "true")
    import src.platform.config as config

    config._settings = None
    ctx, candidate, _, document_id = await reviewed_candidate(db_session, matter)
    await build_checklist_service(db_session).compile_snapshot(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        compiler_input=CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID),
        actor_id=ctx.actor_id,
        correlation_id="synthetic-checklist",
    )
    service = build_ingestion_service(db_session)
    document = await service.get_detected_document(user_id=ctx.actor_id, document_id=document_id)
    corrected = await service.decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id="rta.doc.title_certificate",
        actor_id=ctx.actor_id,
        correlation_id="synthetic-type",
        expected_version=document.document.version,
    )
    refreshed = await service.refresh_extraction(
        user_id=ctx.actor_id,
        document_id=document_id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-refresh",
        expected_version=corrected.document.version,
    )
    assert refreshed.document.extraction_state == "current"
    logicals = list(
        (
            await db_session.execute(
                select(ProcessingLogicalDocumentRow)
                .where(ProcessingLogicalDocumentRow.detected_document_id == document_id)
                .order_by(ProcessingLogicalDocumentRow.interpretation_generation)
            )
        ).scalars()
    )
    assert [row.type_id for row in logicals] == ["rta.doc.nic", "rta.doc.title_certificate"]
    assert [row.interpretation_generation for row in logicals] == [1, 2]
    original = await db_session.get(ProcessingCandidateFieldRow, candidate)
    assert original.candidate_value == "199900000000"
    assert list(
        (
            await db_session.execute(
                select(DocumentInterpretationRow.generation)
                .where(DocumentInterpretationRow.detected_document_id == document_id)
                .order_by(DocumentInterpretationRow.generation)
            )
        ).scalars()
    ) == [1, 2]
    reader = SqlDocumentFactReader(db_session, build_source_file_storage())
    assert (await reader.get_candidate(ctx.actor_id, matter.matter_id, candidate)).current is False
    current = [
        item
        for item in await reader.list_candidates(ctx.actor_id, matter.matter_id)
        if item.current
    ]
    assert current
    for item in current:
        assert item.evidence.interpretation_generation == 2
        await reader.validate_evidence(ctx.actor_id, matter.matter_id, item.evidence)


async def test_correction_stales_only_dependent_links_checks_and_approved_form(db_session, matter):
    ctx, _, accepted, document_id = await reviewed_candidate(db_session, matter)
    await build_checklist_service(db_session).compile_snapshot(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        compiler_input=CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID),
        actor_id=ctx.actor_id,
        correlation_id="synthetic-checklist",
    )
    item = (
        await db_session.execute(
            select(ChecklistItemRow).where(ChecklistItemRow.matter_id == matter.matter_id).limit(1)
        )
    ).scalar_one()
    item.digital_review, item.resolution = "LAWYER_CONFIRMED", "SATISFIED"
    link = SatisfactionLinkRow(
        id=new_id("link"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        checklist_item_id=item.id,
        detected_document_id=document_id,
        digital_review="LAWYER_CONFIRMED",
        created_by=ctx.actor_id,
    )
    check = CrossDocumentCheckRow(
        id=new_id("check"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        check_definition_id="CHK_SYNTHETIC",
        check_definition_version="1",
        run_id=new_id("run"),
        outcome="PASS",
        default_severity="HIGH_RISK",
        explanation_key="synthetic.pass",
        input_fact_versions=[{"factId": accepted.id, "version": accepted.version}],
    )
    form = GeneratedFormRow(
        id=new_id("form"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        template_id="synthetic-template",
        template_version="1",
        form_version=1,
        state="APPROVED",
        subtype_id=TRANSFER_SALE_SUBTYPE_ID,
        approved_artifact_hash="synthetic-hash",
        rule_pack_version="1",
        created_by=ctx.actor_id,
    )
    db_session.add_all([link, check, form])
    await db_session.flush()
    field = GeneratedFormFieldRow(
        id=new_id("field"),
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        generated_form_id=form.id,
        field_id="synthetic-field",
        fact_id=accepted.id,
        fact_version=accepted.version,
        rendered_value="SYNTHETIC VALUE",
        critical=True,
        required=True,
        order=1,
        evidence_reference_ids=list(accepted.evidence_reference_ids),
    )
    db_session.add(field)
    await db_session.flush()
    document = await db_session.get(DetectedDocumentRow, document_id)
    await build_ingestion_service(db_session).decide_classification(
        user_id=ctx.actor_id,
        document_id=document_id,
        class_id="rta.doc.title_certificate",
        actor_id=ctx.actor_id,
        correlation_id="synthetic-dependency",
        expected_version=document.version,
    )
    await db_session.refresh(link)
    await db_session.refresh(item)
    await db_session.refresh(form)
    assert link.digital_review == "SUPERSEDED"
    assert item.resolution != "SATISFIED"
    assert form.state == "STALE_AFTER_APPROVAL"
    assert form.approved_artifact_hash == "synthetic-hash"
    assert field.rendered_value == "SYNTHETIC VALUE"
    checks = list(
        (
            await db_session.execute(
                select(CrossDocumentCheckRow).where(
                    CrossDocumentCheckRow.matter_id == matter.matter_id
                )
            )
        ).scalars()
    )
    assert {row.outcome for row in checks} == {"PASS", "INCONCLUSIVE"}

"""Synthetic requirement links cannot manufacture receipt or legal sufficiency."""

import pytest

from src.bootstrap import build_checklist_service
from src.modules.content_governance.contracts import (
    TRANSFER_SALE_SUBTYPE_ID,
    CollectionStatus,
    CompilerInput,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
)
from src.modules.document.infrastructure.orm import DetectedDocumentRow
from src.platform.errors import NotFoundError
from tests.db.test_document_interpretations import reviewed_candidate
from tests.db.test_scoped_fact_review import matter as matter


async def requirement(session, matter):
    ctx, _, _, document_id = await reviewed_candidate(session, matter)
    service = build_checklist_service(session)
    await service.compile_snapshot(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        compiler_input=CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID),
        actor_id=ctx.actor_id,
        correlation_id="synthetic-requirement",
    )
    checklist = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    item = next(
        row
        for row in checklist.items
        if "rta.doc.nic" in row.requirement.accepted_document_class_ids
    )
    return service, ctx, item, document_id


@pytest.mark.parametrize("foreign", ["missing", "user", "matter"])
async def test_foreign_document_cannot_be_linked(db_session, matter, foreign):
    service, ctx, item, document_id = await requirement(db_session, matter)
    row = await db_session.get(DetectedDocumentRow, document_id)
    if foreign == "user":
        row.user_id = "usr_synthetic_foreign"
    elif foreign == "matter":
        row.matter_id = "mat_synthetic_foreign"
    else:
        document_id = "doc_synthetic_absent"
    # The scope mutation is fixture-only; no user/matter IDs leave the fixture.
    await db_session.flush()
    with pytest.raises(NotFoundError):
        await service.link_document(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            item_id=item.item.id,
            detected_document_id=document_id,
            expected_version=item.item.version,
            document_version=row.version,
            interpretation_generation=row.interpretation_generation,
            actor_id=ctx.actor_id,
            correlation_id="synthetic-link",
        )


async def test_link_receives_evidence_without_accepting_its_sufficiency(db_session, matter):
    service, ctx, item, document_id = await requirement(db_session, matter)
    document = await db_session.get(DetectedDocumentRow, document_id)
    await service.link_document(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        item_id=item.item.id,
        detected_document_id=document_id,
        expected_version=item.item.version,
        document_version=document.version,
        interpretation_generation=document.interpretation_generation,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-link",
    )
    checklist = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    current = next(row for row in checklist.items if row.item.id == item.item.id)
    assert current.item.collection is CollectionStatus.RECEIVED
    assert current.item.digital_review is not DigitalReviewStatus.LAWYER_CONFIRMED
    assert current.computed_resolution is not ResolutionStatus.SATISFIED


async def test_inspection_without_any_bound_original_is_refused(db_session, matter):
    from src.platform.errors import DomainRuleError

    service, ctx, item, _ = await requirement(db_session, matter)
    with pytest.raises(DomainRuleError):
        await service.record_original_inspection(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            item_id=item.item.id,
            actor_id=ctx.actor_id,
            correlation_id="synthetic-inspection",
            expected_version=item.item.version,
            method="Synthetic original sighted",
        )


async def test_a_different_original_does_not_inherit_a_previous_physical_inspection(
    db_session, matter
):
    from src.bootstrap import build_ingestion_service
    from src.modules.document.infrastructure.orm import DocumentFragmentRow
    from src.platform.ids import new_id
    from tests.factories.document import synthetic_pdf

    service, ctx, _, document_id = await requirement(db_session, matter)
    checklist = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    item = next(
        row.item
        for row in checklist.items
        if row.requirement.id == "R_C20_ORIGINAL_TITLE_CERTIFICATE_INSPECTED"
    )
    document = await db_session.get(DetectedDocumentRow, document_id)
    document.class_id = "rta.doc.title_certificate"
    await db_session.flush()
    who = {
        "user_id": ctx.actor_id,
        "matter_id": matter.matter_id,
        "item_id": item.id,
        "actor_id": ctx.actor_id,
        "correlation_id": "synthetic-inspection",
    }
    await service.link_document(
        **who,
        detected_document_id=document_id,
        expected_version=item.version,
        document_version=document.version,
        interpretation_generation=document.interpretation_generation,
    )
    checklist = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    current = next(row.item for row in checklist.items if row.item.id == item.id)
    inspected = await service.record_original_inspection(
        **who, expected_version=current.version, method="Synthetic original at office"
    )
    assert inspected.item.physical_original is PhysicalOriginalStatus.ORIGINAL_INSPECTED
    assert inspected.computed_resolution is not ResolutionStatus.SATISFIED
    await service.link_document(
        **who,
        detected_document_id=document_id,
        expected_version=inspected.item.version,
        document_version=document.version,
        interpretation_generation=document.interpretation_generation,
    )
    renewed = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    same = next(row.item for row in renewed.items if row.item.id == item.id)
    assert same.physical_original is PhysicalOriginalStatus.ORIGINAL_INSPECTED
    inspected = await service.record_original_inspection(
        **who, expected_version=same.version, method="Second synthetic inspection"
    )
    assert len(inspected.item.inspection_history) == 2
    assert inspected.item.inspection_history[0].method == "Synthetic original at office"
    replacement = await build_ingestion_service(db_session).upload_source_file(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-replacement",
        filename="SYNTHETIC-REPLACEMENT.pdf",
        declared_media_type="application/pdf",
        data=synthetic_pdf(1),
    )
    await db_session.refresh(document)
    second = DetectedDocumentRow(
        **{
            column.name: getattr(document, column.name)
            for column in DetectedDocumentRow.__table__.columns
            if column.name != "id"
        },
        id=new_id("doc"),
    )
    db_session.add(second)
    await db_session.flush()
    db_session.add(
        DocumentFragmentRow(
            id=new_id("fragment"),
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            source_file_id=replacement.source_file.id,
            detected_document_id=second.id,
            page_start=1,
            page_end=1,
            order_in_document=0,
            boundary_status="CONFIRMED",
        )
    )
    await db_session.flush()
    await service.link_document(
        **who,
        detected_document_id=second.id,
        expected_version=inspected.item.version,
        document_version=second.version,
        interpretation_generation=second.interpretation_generation,
    )
    checklist = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    current = next(row.item for row in checklist.items if row.item.id == item.id)
    assert current.physical_original is PhysicalOriginalStatus.UNKNOWN
    assert current.original_inspection == inspected.item.original_inspection


@pytest.mark.parametrize("foreign", ["user", "matter", "source", "generation", "document"])
async def test_foreign_or_stale_evidence_is_refused(db_session, matter, foreign):
    from sqlalchemy import select

    from src.modules.verification.infrastructure.orm import EvidenceReferenceRow
    from src.platform.errors import DomainRuleError

    service, ctx, item, document_id = await requirement(db_session, matter)
    document = await db_session.get(DetectedDocumentRow, document_id)
    evidence = (
        (
            await db_session.execute(
                select(EvidenceReferenceRow).where(
                    EvidenceReferenceRow.detected_document_id == document_id
                )
            )
        )
        .scalars()
        .first()
    )
    field, value = {
        "user": ("user_id", "usr_synthetic_foreign"),
        "matter": ("matter_id", "mat_synthetic_foreign"),
        "source": ("source_file_id", "src_synthetic_foreign"),
        "generation": ("interpretation_generation", 999),
        "document": ("detected_document_id", "doc_synthetic_foreign"),
    }[foreign]
    setattr(evidence, field, value)
    await db_session.flush()
    with pytest.raises((NotFoundError, DomainRuleError)):
        await service.link_document(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            item_id=item.item.id,
            detected_document_id=document_id,
            expected_version=item.item.version,
            document_version=document.version,
            interpretation_generation=document.interpretation_generation,
            evidence_reference_ids=(evidence.id,),
            actor_id=ctx.actor_id,
            correlation_id="synthetic-foreign-evidence",
        )
    assert await service.list_links(user_id=ctx.actor_id, item_id=item.item.id) == []


@pytest.mark.parametrize(
    "pin", ["document_version", "interpretation_generation", "expected_version"]
)
async def test_displayed_requirement_and_document_pins_are_required(db_session, matter, pin):
    from src.platform.errors import PreconditionFailedError

    service, ctx, item, document_id = await requirement(db_session, matter)
    document = await db_session.get(DetectedDocumentRow, document_id)
    pins = {
        "expected_version": item.item.version,
        "document_version": document.version,
        "interpretation_generation": document.interpretation_generation,
    }
    pins[pin] += 1
    with pytest.raises(PreconditionFailedError):
        await service.link_document(
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            item_id=item.item.id,
            detected_document_id=document_id,
            **pins,
            actor_id=ctx.actor_id,
            correlation_id="synthetic-stale-pin",
        )
    assert await service.list_links(user_id=ctx.actor_id, item_id=item.item.id) == []


async def test_read_projection_withholds_review_on_changed_document_pin(db_session, matter):
    from src.modules.task.infrastructure.orm import ChecklistItemRow

    service, ctx, item, document_id = await requirement(db_session, matter)
    document = await db_session.get(DetectedDocumentRow, document_id)
    await service.link_document(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        item_id=item.item.id,
        detected_document_id=document_id,
        expected_version=item.item.version,
        document_version=document.version,
        interpretation_generation=document.interpretation_generation,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-link-read",
    )
    stored = await db_session.get(ChecklistItemRow, item.item.id)
    stored.digital_review = "LAWYER_CONFIRMED"
    document.version += 1
    await db_session.flush()
    current = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
    view = next(row for row in current.items if row.item.id == item.item.id)
    assert view.live_link_count == 0
    assert view.item.digital_review is DigitalReviewStatus.UNREVIEWED
    assert stored.digital_review == "LAWYER_CONFIRMED"  # Historical decision is retained.

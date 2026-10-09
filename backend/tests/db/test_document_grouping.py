"""Synthetic page accounting, split recovery and merge history on migrated schemas."""

import pytest
from sqlalchemy import select

from src.bootstrap import build_ingestion_service
from src.modules.document.domain.ingestion import FragmentRange
from src.modules.document.infrastructure.orm import (
    DocumentFragmentRow,
    DocumentInterpretationRow,
    SourceFileRow,
)
from src.platform.errors import DomainRuleError
from tests.db.test_scoped_fact_review import matter as matter
from tests.factories.document import synthetic_pdf


async def upload(service, matter, pages=3):
    return await service.upload_source_file(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-grouping",
        filename="synthetic-pages.pdf",
        declared_media_type="application/pdf",
        data=synthetic_pdf(pages),
    )


async def test_split_recovery_and_merge_account_every_page_and_preserve_ranges(db_session, matter):
    service = build_ingestion_service(db_session)
    source = (await upload(service, matter)).source_file
    args = {
        "user_id": matter.lawyer_id,
        "matter_id": matter.matter_id,
        "actor_id": matter.lawyer_id,
        "correlation_id": "synthetic-grouping",
    }
    first = await service.create_group(
        **args, class_id="rta.doc.nic", ranges=[FragmentRange(source.id, 1, 3, 0)]
    )
    first = await service.decide_boundary(
        user_id=matter.lawyer_id,
        document_id=first.document.id,
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-split",
        expected_version=first.document.version,
        ranges=[FragmentRange(source.id, 1, 1, 0)],
    )
    inbox = await service.get_document_inbox(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    assert inbox.page_accounting[0].unclaimed_page_numbers == (2, 3)
    assert not inbox.page_accounting[0].complete
    second = await service.create_group(
        **args, class_id="rta.doc.title_certificate", ranges=[FragmentRange(source.id, 2, 3, 0)]
    )
    inbox = await service.get_document_inbox(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    assert inbox.page_accounting[0].complete
    merged = await service.decide_boundary(
        user_id=matter.lawyer_id,
        document_id=first.document.id,
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-merge",
        expected_version=first.document.version,
        ranges=[FragmentRange(source.id, 1, 3, 0)],
        retire_documents=((second.document.id, second.document.version),),
    )
    assert merged.document.extraction_state == "refresh_required"
    inbox = await service.get_document_inbox(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    assert {item.document.id for item in inbox.documents} == {first.document.id}
    assert inbox.page_accounting[0].complete
    snapshots = (
        (
            await db_session.execute(
                select(DocumentInterpretationRow)
                .where(DocumentInterpretationRow.detected_document_id == first.document.id)
                .order_by(DocumentInterpretationRow.generation)
            )
        )
        .scalars()
        .all()
    )
    assert [row.fragments[0]["page_end"] for row in snapshots] == [3, 1, 3]


async def test_cross_document_overlap_and_repeated_pages_are_refused(db_session, matter):
    service = build_ingestion_service(db_session)
    source = (await upload(service, matter)).source_file
    args = {
        "user_id": matter.lawyer_id,
        "matter_id": matter.matter_id,
        "actor_id": matter.lawyer_id,
        "correlation_id": "synthetic-grouping",
    }
    await service.create_group(
        **args, class_id="rta.doc.nic", ranges=[FragmentRange(source.id, 1, 2, 0)]
    )
    with pytest.raises(DomainRuleError):
        await service.create_group(
            **args, class_id="rta.doc.nic", ranges=[FragmentRange(source.id, 2, 3, 0)]
        )
    with pytest.raises(DomainRuleError):
        await service.create_group(
            **args,
            class_id="rta.doc.nic",
            ranges=[FragmentRange(source.id, 3, 3, 0), FragmentRange(source.id, 3, 3, 1)],
        )


async def test_blank_and_unsupported_dispositions_account_without_claiming_extraction(
    db_session, matter
):
    service = build_ingestion_service(db_session)
    source = (await upload(service, matter, pages=2)).source_file
    for number, kind in ((1, "blank"), (2, "unsupported")):
        await service.decide_page_disposition(
            user_id=matter.lawyer_id,
            source_file_id=source.id,
            page_number=number,
            disposition=kind,
            reason="Synthetic visual review",
            actor_id=matter.lawyer_id,
            correlation_id="synthetic-page-review",
            expected_version=number,
        )
    inbox = await service.get_document_inbox(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    accounted = inbox.page_accounting[0]
    assert accounted.complete
    assert accounted.blank_page_numbers == (1,)
    assert accounted.unsupported_page_numbers == (2,)
    assert accounted.manual_review_required
    assert not inbox.documents


async def test_blank_single_page_group_can_be_retired_explicitly_without_losing_history(
    db_session, matter
):
    service = build_ingestion_service(db_session)
    source = (await upload(service, matter, pages=1)).source_file
    group = await service.create_group(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-blank",
        ranges=[FragmentRange(source.id, 1, 1, 0)],
    )
    await service.decide_page_disposition(
        user_id=matter.lawyer_id,
        source_file_id=source.id,
        page_number=1,
        disposition="blank",
        reason="Synthetic visual review",
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-blank",
        expected_version=source.version,
        retire_documents=((group.document.id, group.document.version),),
    )
    inbox = await service.get_document_inbox(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    assert not inbox.documents
    accounted = next(item for item in inbox.page_accounting if item.source_file_id == source.id)
    assert accounted.complete and not accounted.manual_review_required
    assert (await service.interpretation_history(matter.lawyer_id, group.document.id)).snapshots


async def test_legacy_out_of_bounds_claim_never_completes_page_accounting(db_session, matter):
    service = build_ingestion_service(db_session)
    source = (await upload(service, matter, pages=2)).source_file
    group = await service.create_group(
        user_id=matter.lawyer_id,
        matter_id=matter.matter_id,
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-bounds",
        ranges=[FragmentRange(source.id, 1, 2, 0)],
    )
    fragment = await db_session.get(DocumentFragmentRow, group.fragments[0].id)
    fragment.page_end = 3
    await db_session.flush()
    inbox = await service.get_document_inbox(user_id=matter.lawyer_id, matter_id=matter.matter_id)
    accounted = next(item for item in inbox.page_accounting if item.source_file_id == source.id)
    assert not accounted.complete
    assert accounted.out_of_bounds_page_numbers == (3,)


async def test_grouping_refuses_unknown_bounds_and_unchanged_segmentation_does_not_churn(
    db_session, matter
):
    service = build_ingestion_service(db_session)
    source = (await upload(service, matter, pages=2)).source_file
    args = {
        "user_id": matter.lawyer_id,
        "matter_id": matter.matter_id,
        "actor_id": matter.lawyer_id,
        "correlation_id": "synthetic-bounds",
    }
    group = await service.create_group(**args, ranges=[FragmentRange(source.id, 1, 2, 0)])
    same = await service.decide_boundary(
        user_id=matter.lawyer_id,
        document_id=group.document.id,
        actor_id=matter.lawyer_id,
        correlation_id="synthetic-segmentation",
        expected_version=group.document.version,
        ranges=[FragmentRange(source.id, 1, 1, 0), FragmentRange(source.id, 2, 2, 1)],
    )
    assert same.document.interpretation_generation == group.document.interpretation_generation
    unknown = (await upload(service, matter, pages=1)).source_file
    row = await db_session.get(SourceFileRow, unknown.id)
    row.page_count = None
    await db_session.flush()
    with pytest.raises(DomainRuleError):
        await service.create_group(**args, ranges=[FragmentRange(unknown.id, 1, 1, 0)])

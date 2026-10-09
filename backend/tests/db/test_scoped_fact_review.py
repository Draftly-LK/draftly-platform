"""Synthetic scoped review journeys on migrated PostgreSQL."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from scripts.seed_synthetic_matter import seed
from src.bootstrap import (
    build_document_review_service,
    build_fact_review_service,
    build_matter_scope_service,
    build_matter_service,
    build_source_file_storage,
)
from src.modules.auth.domain.errors import PracticeStatusError
from src.modules.auth.domain.models import Role
from src.modules.auth.infrastructure.orm import UserRow
from src.modules.document.contracts import FactEvidenceLocator
from src.modules.document.infrastructure.orm import (
    DetectedDocumentRow,
    DocumentFragmentRow,
    DocumentProcessingPageRow,
    ProcessingCandidateFieldRow,
    ProcessingLogicalDocumentRow,
    SourceFileProcessingRunRow,
    SourceFileRow,
)
from src.modules.matter.application.matter_service import CreateMatterInput
from src.modules.verification.application.review_service import ManualFactInput, ReviewFactInput
from src.modules.verification.domain.errors import (
    EvidenceRequiredError,
    NegativeFactRequiresSearchError,
)
from src.modules.verification.domain.models import EvidenceReference
from src.modules.verification.infrastructure.orm import ExtractedFactRow
from src.modules.verification.infrastructure.repository import (
    SqlConfirmedFactReader,
    SqlVerificationRepository,
)
from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    NotFoundError,
    PreconditionFailedError,
)
from src.platform.ids import new_id
from src.platform.request_context import RequestContext


@pytest.fixture
async def matter(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    report = await seed(db_session)
    user = await db_session.get(UserRow, report.lawyer_id)
    user.notary_registration = "SYNTHETIC-PRACTICE-ONLY"
    user.certificate_valid_until = datetime.now(UTC) + timedelta(days=30)
    await db_session.flush()
    return report


@pytest.mark.parametrize("missing", [True, False])
async def test_missing_or_expired_practice_refuses_manual_command(db_session, matter, missing):
    user = await db_session.get(UserRow, matter.lawyer_id)
    if missing:
        user.notary_registration = None
    else:
        user.certificate_valid_until = datetime.now(UTC) - timedelta(days=1)
    await db_session.flush()
    await db_session.refresh(user)
    with pytest.raises(PracticeStatusError):
        await build_fact_review_service(db_session).add_manual(
            RequestContext(matter.lawyer_id, Role.APPROVER, "practice-refusal"),
            matter.matter_id,
            ManualFactInput("rta.parcel.village", "SYNTHETIC", "Synthetic instructions"),
            key="practice",
        )


async def test_manual_input_is_unverified_and_replay_does_not_duplicate(db_session, matter):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-review")
    scopes = build_matter_scope_service(db_session)
    subject = await scopes.create_subject(ctx, matter.matter_id, kind="party", key="subject-a")
    transaction = await scopes.create_transaction(ctx, matter.matter_id, key="transaction-a")
    service = build_fact_review_service(db_session)
    data = ManualFactInput(
        "rta.party.transferee_name",
        "SYNTHETIC PARTY ALPHA",
        "Synthetic instructions",
        transaction.id,
        subject.id,
    )
    saved = await service.add_manual(ctx, matter.matter_id, data, key="manual-a")
    replay = await service.add_manual(ctx, matter.matter_id, data, key="manual-a")
    assert saved.id == replay.id
    assert saved.origin == "lawyer"
    assert saved.status.value == "REVIEW_REQUIRED"
    assert saved.original_value is None
    assert saved.manual_reason == "Synthetic instructions"
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert "rta.party.transferee_name" not in summary.confirmed
    assert (
        len(
            await SqlVerificationRepository(db_session).list_decisions(
                ctx.actor_id, matter.matter_id
            )
        )
        == 1
    )


async def test_foreign_scope_and_role_cannot_create_manual_fact(db_session, matter):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-review")
    service = build_fact_review_service(db_session)
    data = ManualFactInput(
        "rta.party.transferee_name",
        "SYNTHETIC PARTY",
        "Synthetic instructions",
        None,
        "foreign-subject",
    )
    with pytest.raises(NotFoundError):
        await service.add_manual(ctx, matter.matter_id, data, key="foreign")
    with pytest.raises(CapabilityDeniedError):
        await service.add_manual(
            replace(ctx, account_role=Role.ADMINISTRATOR),
            matter.matter_id,
            replace(data, subject_id=None),
            key="role",
        )


async def test_rejection_is_a_successor_with_history_and_stale_write_refused(db_session, matter):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-review")
    service = build_fact_review_service(db_session)
    original = await service.add_manual(
        ctx,
        matter.matter_id,
        ManualFactInput("rta.parcel.village", "SYNTHETIC VILLAGE", "Synthetic instructions"),
        key="manual",
    )
    data = ReviewFactInput(
        action="reject", expected_version=original.version, reason="Synthetic rejection"
    )
    rejected = await service.decide(ctx, matter.matter_id, original.id, data, key="reject")
    assert rejected.status.value == "REJECTED"
    assert rejected.supersedes_fact_id == original.id
    assert rejected.value == original.value
    assert (
        await service.decide(ctx, matter.matter_id, original.id, data, key="reject")
    ).id == rejected.id
    with pytest.raises(PreconditionFailedError):
        await service.decide(ctx, matter.matter_id, original.id, data, key="stale")
    history = await service.history(ctx, matter.matter_id, rejected.id)
    assert [f.id for f in history.facts] == [original.id, rejected.id]
    assert [d.decision for d in history.decisions] == ["manual", "reject"]


async def scoped_input(session, matter):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-evidence")
    scopes = build_matter_scope_service(session)
    subject = await scopes.create_subject(ctx, matter.matter_id, kind="parcel", key="parcel")
    txn = await scopes.create_transaction(
        ctx, matter.matter_id, parcel_subject_ids=(subject.id,), key="txn"
    )
    source = (
        await session.execute(
            select(SourceFileRow).where(SourceFileRow.matter_id == matter.matter_id)
        )
    ).scalar_one()
    source.page_count = 1
    await session.flush()
    locator = FactEvidenceLocator(source.id, 1, source.sha256)
    return ctx, ManualFactInput(
        "rta.parcel.village",
        "SYNTHETIC VILLAGE A",
        "Synthetic evidence review",
        txn.id,
        subject.id,
        locator,
    )


async def test_real_cross_matter_scope_and_evidence_and_foreign_user_reads_refuse(
    db_session, matter
):
    ctx, data = await scoped_input(db_session, matter)
    other = await build_matter_service(db_session).create_matter(
        ctx, CreateMatterInput(reference="SYNTHETIC OTHER MATTER")
    )
    service = build_fact_review_service(db_session)
    with pytest.raises(NotFoundError):
        await service.add_manual(ctx, other.id, data, key="cross-scope")
    with pytest.raises(NotFoundError):
        await service.add_manual(
            ctx, other.id, replace(data, transaction_id=None, subject_id=None), key="cross-evidence"
        )
    original = await service.add_manual(ctx, matter.matter_id, data, key="original")
    with pytest.raises(NotFoundError):
        await service.get_view(replace(ctx, actor_id="foreign-user"), matter.matter_id, original.id)
    with pytest.raises(NotFoundError):
        await service.get_view(ctx, other.id, original.id)


async def test_negative_conclusion_requires_current_search_even_with_manual_evidence(
    db_session, matter
):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    fact = await service.add_manual(
        ctx,
        matter.matter_id,
        replace(data, fact_type_id="rta.interest.mortgage_status", value="NONE"),
        key="negative",
    )
    view = await service.get_view(ctx, matter.matter_id, fact.id)
    with pytest.raises(NegativeFactRequiresSearchError):
        await service.decide(
            ctx,
            matter.matter_id,
            fact.id,
            ReviewFactInput("accept", fact.version, expected_scope_token=view.scope_token),
            key="negative-accept",
        )


async def test_accept_requires_evidence_and_correction_preserves_history(db_session, matter):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    original = await service.add_manual(
        ctx, matter.matter_id, replace(data, evidence=None), key="add"
    )
    view = await service.get_view(ctx, matter.matter_id, original.id)
    command = ReviewFactInput("accept", original.version, expected_scope_token=view.scope_token)
    with pytest.raises(EvidenceRequiredError):
        await service.decide(ctx, matter.matter_id, original.id, command, key="accept")
    accepted = await service.decide(
        ctx, matter.matter_id, original.id, replace(command, evidence=data.evidence), key="accept"
    )
    assert accepted.is_confirmed
    view = await service.get_view(ctx, matter.matter_id, accepted.id)
    correction = ReviewFactInput(
        "correct",
        accepted.version,
        reason="Read printed village again",
        value="SYNTHETIC VILLAGE B",
        expected_scope_token=view.scope_token,
    )
    corrected = await service.decide(ctx, matter.matter_id, accepted.id, correction, key="correct")
    assert corrected.is_confirmed and corrected.value == "SYNTHETIC VILLAGE B"
    assert corrected.supersedes_fact_id == accepted.id
    history = await service.history(ctx, matter.matter_id, corrected.id)
    assert [f.value for f in history.facts] == [data.value, data.value, corrected.value]
    assert len(history.decisions) == 3
    assert (
        await service.decide(ctx, matter.matter_id, accepted.id, correction, key="correct")
    ).id == corrected.id
    with pytest.raises(CapabilityDeniedError):
        await service.decide(
            replace(ctx, account_role=Role.ADMINISTRATOR),
            matter.matter_id,
            accepted.id,
            correction,
            key="correct",
        )


async def test_accept_unassigned_observations_without_inventing_scope_or_resolving_other_documents(
    db_session, matter
):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    unassigned = replace(data, transaction_id=None, subject_id=None)
    first = await service.add_manual(ctx, matter.matter_id, unassigned, key="unassigned-first")
    second = await service.add_manual(
        ctx,
        matter.matter_id,
        replace(unassigned, value="SYNTHETIC DIFFERENT DOCUMENT"),
        key="unassigned-second",
    )
    view = await service.get_view(ctx, matter.matter_id, first.id)
    assert view.conflict_fact_ids == ()
    command = ReviewFactInput("accept", first.version, expected_scope_token=view.scope_token)
    accepted = await service.decide(ctx, matter.matter_id, first.id, command, key="quick-accept")
    assert accepted.is_confirmed
    assert accepted.scope_status == "unassigned"
    assert accepted.transaction_id is None and accepted.subject_id is None
    assert (await service.get_view(ctx, matter.matter_id, second.id)).fact.is_live
    assert (
        await service.decide(ctx, matter.matter_id, first.id, command, key="quick-accept")
    ).id == accepted.id
    history = await service.history(ctx, matter.matter_id, accepted.id)
    assert [d.decision for d in history.decisions] == ["manual", "accept"]
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert summary.confirmed == {} and summary.scoped_confirmed == ()
    assert summary.conflicted_fact_type_ids == () and summary.scoped_conflicts == ()


async def test_competing_arrival_requires_reload_and_explicit_resolution(db_session, matter):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    original = await service.add_manual(ctx, matter.matter_id, data, key="first")
    prior = await service.get_view(ctx, matter.matter_id, original.id)
    competitor = await service.add_manual(
        ctx, matter.matter_id, replace(data, value="SYNTHETIC OTHER"), key="second"
    )
    command = ReviewFactInput("accept", original.version, expected_scope_token=prior.scope_token)
    with pytest.raises(PreconditionFailedError):
        await service.decide(ctx, matter.matter_id, original.id, command, key="accept")
    current = await service.get_view(ctx, matter.matter_id, original.id)
    assert current.conflict_fact_ids == (competitor.id,)
    command = replace(command, expected_scope_token=current.scope_token)
    with pytest.raises(ConflictError):
        await service.decide(ctx, matter.matter_id, original.id, command, key="accept")
    accepted = await service.decide(
        ctx,
        matter.matter_id,
        original.id,
        replace(
            command,
            reason="Printed source supports first village",
            resolve_fact_ids=(competitor.id,),
        ),
        key="accept",
    )
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert summary.confirmed[data.fact_type_id].fact_id == accepted.id
    competing_history = await service.history(ctx, matter.matter_id, competitor.id)
    assert competing_history.facts[0].superseded_by_fact_id == accepted.id


@pytest.mark.parametrize("failure", ["foreign", "hash", "page", "missing", "stale"])
async def test_invalid_evidence_refused(db_session, matter, failure):
    ctx, data = await scoped_input(db_session, matter)
    locator = data.evidence
    if failure == "foreign":
        locator = replace(locator, source_file_id="foreign-source")
    elif failure == "hash":
        locator = replace(locator, source_sha256="0" * 64)
    elif failure == "page":
        locator = replace(locator, page_number=2)
    else:
        source = await db_session.get(SourceFileRow, locator.source_file_id)
        if failure == "missing":
            source.storage_object_key = "missing-artifact"
        else:
            source.state = "PROCESSING"
        await db_session.flush()
    with pytest.raises((NotFoundError, DomainRuleError)):
        await build_fact_review_service(db_session).add_manual(
            ctx, matter.matter_id, replace(data, evidence=locator), key="invalid"
        )


async def test_history_pages_do_not_lose_later_decisions(db_session, matter):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    original = await service.add_manual(ctx, matter.matter_id, data, key="add")
    rejected = await service.decide(
        ctx,
        matter.matter_id,
        original.id,
        ReviewFactInput("reject", original.version, reason="Synthetic rejection"),
        key="reject",
    )
    first = await service.history(ctx, matter.matter_id, rejected.id, limit=1)
    assert first.has_more
    second = await service.history(
        ctx, matter.matter_id, rejected.id, limit=1, after=first.facts[-1].id
    )
    assert [f.id for f in second.facts] == [rejected.id]
    assert second.decisions[0].decision == "reject"


async def machine_candidate(session, matter):
    ctx, data = await scoped_input(session, matter)
    source = await session.get(SourceFileRow, data.evidence.source_file_id)
    source.state = "PROCESSED"
    document_id = new_id("document")
    session.add(
        DetectedDocumentRow(
            id=document_id,
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            class_id="rta.doc.nic",
            class_status="LAWYER_CONFIRMED",
            boundary_status="CONFIRMED",
        )
    )
    await session.flush()
    session.add(
        DocumentFragmentRow(
            id=new_id("fragment"),
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            detected_document_id=document_id,
            source_file_id=source.id,
            page_start=1,
            page_end=1,
            boundary_status="CONFIRMED",
        )
    )
    run_id, logical_id, candidate_id = new_id("run"), new_id("logical"), new_id("candidate")
    session.add(
        SourceFileProcessingRunRow(
            id=run_id,
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            source_file_id=source.id,
            provider="synthetic",
            outcome="PROCESSED",
            pages_processed=1,
            ai_extraction_calls=0,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
    )
    await session.flush()
    session.add(
        ProcessingLogicalDocumentRow(
            id=logical_id,
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            source_file_id=source.id,
            processing_run_id=run_id,
            document_index=0,
            detected_document_id=document_id,
            type_id="rta.doc.nic",
            page_numbers=[1],
        )
    )
    storage = build_source_file_storage()
    image_key, text_key = "synthetic/page.webp", "synthetic/page.txt"
    image_version = await storage.put(image_key, b"synthetic image artifact")
    text_version = await storage.put(text_key, b"SYNTHETIC NIC 199900000000")
    session.add(
        DocumentProcessingPageRow(
            id=new_id("page"),
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            source_file_id=source.id,
            processing_run_id=run_id,
            page_no=1,
            quality_status="GOOD",
            original_width=100,
            original_height=100,
            corrected_width=100,
            corrected_height=100,
            correction_degrees=0,
            rotation_status="UNCHANGED",
            rotation_vote_share=1,
            usable_word_count=3,
            detected_languages=[],
            classification_type_id="rta.doc.nic",
            starts_new_document=True,
            classification_confidence=1,
            corrected_webp_key=image_key,
            corrected_webp_version=image_version,
            corrected_ocr_key=text_key,
            corrected_ocr_version=text_version,
            plain_text_key=text_key,
            plain_text_version=text_version,
        )
    )
    await session.flush()
    session.add(
        ProcessingCandidateFieldRow(
            id=candidate_id,
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            logical_document_id=logical_id,
            key="transfereeNic",
            candidate_value="199900000000",
            page_no=1,
            model_reported_confidence=1,
        )
    )
    await session.flush()
    return ctx, data.transaction_id, candidate_id


async def test_accept_machine_observation_directly_preserves_evidence_and_history(
    db_session, matter
):
    ctx, _, candidate_id = await machine_candidate(db_session, matter)
    service = build_fact_review_service(db_session)
    accepted = await service.decide_candidate(
        ctx, matter.matter_id, candidate_id, action="accept", expected_version=1
    )
    assert accepted.is_confirmed and accepted.scope_status == "unassigned"
    assert accepted.transaction_id is None and accepted.subject_id is None
    assert accepted.original_value == "199900000000"
    current = await service.get_view(ctx, matter.matter_id, accepted.id)
    assert current.evidence[0].text_span == "199900000000"
    history = await service.history(ctx, matter.matter_id, accepted.id)
    assert [decision.decision for decision in history.decisions] == ["accept"]
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert summary.confirmed == {} and summary.scoped_confirmed == ()


async def test_machine_original_nic_alias_association_and_compatibility_retry(db_session, matter):
    ctx, txn_id, candidate_id = await machine_candidate(db_session, matter)
    service = build_fact_review_service(db_session)
    view = await service.get_view(ctx, matter.matter_id, candidate_id)
    document_service = build_document_review_service(db_session)
    document_review = await document_service.get_review(
        user_id=ctx.actor_id, detected_document_id=view.evidence[0].detected_document_id
    )
    assert document_review.candidates[0].key == "holderNic"
    assert view.fact.fact_type_id == "rta.party.holder_nic"
    assert view.fact.scope_status == "unassigned"
    assert view.evidence[0].precision == "text"
    assert view.evidence[0].text_span == "199900000000"
    assert view.evidence[0].bounding_box is None
    edited = await service.decide_candidate(
        ctx, matter.matter_id, candidate_id, action="edit", expected_version=1, value="199900000001"
    )
    assert edited.original_value == "199900000000"
    assert not edited.is_confirmed
    assert (
        await service.decide_candidate(
            ctx,
            matter.matter_id,
            candidate_id,
            action="edit",
            expected_version=1,
            value="199900000001",
        )
    ).id == edited.id
    party = await build_matter_scope_service(db_session).create_subject(
        ctx, matter.matter_id, kind="party", key="holder"
    )
    associated = await service.decide(
        ctx,
        matter.matter_id,
        edited.id,
        ReviewFactInput(
            "associate",
            edited.version,
            reason="Identify source holder",
            transaction_id=txn_id,
            subject_id=party.id,
        ),
        key="associate",
    )
    accepted = await service.decide_candidate(
        ctx, matter.matter_id, candidate_id, action="accept", expected_version=associated.version
    )
    assert accepted.is_confirmed and accepted.original_value == "199900000000"
    assert (
        await service.decide_candidate(
            ctx,
            matter.matter_id,
            candidate_id,
            action="accept",
            expected_version=associated.version,
        )
    ).id == accepted.id
    transaction = await build_matter_scope_service(db_session).get_transaction(
        ctx, matter.matter_id, txn_id
    )
    assert transaction.party_roles == ()
    original = await db_session.get(ProcessingCandidateFieldRow, candidate_id)
    assert original.candidate_value == "199900000000" and original.edited_value is None
    assert original.review_state == "unverified"
    summary = await SqlConfirmedFactReader(db_session).summarise(ctx.actor_id, matter.matter_id)
    assert "rta.party.transferee_nic" not in summary.confirmed
    assert summary.confirmed["rta.party.holder_nic"].value == "199900000001"


async def test_same_key_concurrency_creates_one_decision_and_distinct_stale_keys_refuse(
    db_committing, tmp_path, monkeypatch
):
    import asyncio

    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    async with db_committing() as session:
        matter = await seed(session)
        user = await session.get(UserRow, matter.lawyer_id)
        user.notary_registration = "SYNTHETIC-PRACTICE"
        user.certificate_valid_until = datetime.now(UTC) + timedelta(days=30)
        await session.commit()
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "concurrent-review")
    data = ManualFactInput("rta.parcel.village", "SYNTHETIC", "Synthetic instructions")

    async def add():
        async with db_committing() as session:
            saved = await build_fact_review_service(session).add_manual(
                ctx, matter.matter_id, data, key="same-key"
            )
            await session.commit()
            return saved

    first, second = await asyncio.gather(add(), add())
    assert first.id == second.id

    async def reject(key):
        async with db_committing() as session:
            try:
                saved = await build_fact_review_service(session).decide(
                    ctx,
                    matter.matter_id,
                    first.id,
                    ReviewFactInput("reject", first.version, reason="Synthetic rejection"),
                    key=key,
                )
                await session.commit()
                return saved.id
            except PreconditionFailedError:
                await session.rollback()
                return "stale"

    results = await asyncio.gather(reject("first"), reject("second"))
    assert results.count("stale") == 1
    async with db_committing() as session:
        decisions = await SqlVerificationRepository(session).list_decisions(
            ctx.actor_id, matter.matter_id
        )
        assert len(decisions) == 2


async def test_replacement_evidence_keeps_its_own_candidate_relationship(db_session, matter):
    ctx, txn_id, candidate_id = await machine_candidate(db_session, matter)
    service = build_fact_review_service(db_session)
    party = await build_matter_scope_service(db_session).create_subject(
        ctx, matter.matter_id, kind="party", key="holder"
    )
    associated = await service.decide(
        ctx,
        matter.matter_id,
        candidate_id,
        ReviewFactInput(
            "associate", 1, reason="Synthetic holder", transaction_id=txn_id, subject_id=party.id
        ),
        key="associate",
    )
    view = await service.get_view(ctx, matter.matter_id, associated.id)
    evidence = view.evidence[0]
    direct_page = FactEvidenceLocator(
        evidence.source_file_id, evidence.page_number, evidence.source_sha256
    )
    corrected = await service.decide(
        ctx,
        matter.matter_id,
        associated.id,
        ReviewFactInput(
            "correct",
            associated.version,
            reason="Lawyer reviewed original page directly",
            value="199900000002",
            evidence=direct_page,
            expected_scope_token=view.scope_token,
        ),
        key="correct",
    )
    current = await service.get_view(ctx, matter.matter_id, corrected.id)
    accepted = await service.decide(
        ctx,
        matter.matter_id,
        corrected.id,
        ReviewFactInput("accept", corrected.version, expected_scope_token=current.scope_token),
        key="accept",
    )
    assert accepted.is_confirmed


async def test_changed_candidate_version_refuses_acceptance(db_session, matter):
    ctx, txn_id, candidate_id = await machine_candidate(db_session, matter)
    service = build_fact_review_service(db_session)
    party = await build_matter_scope_service(db_session).create_subject(
        ctx, matter.matter_id, kind="party", key="holder"
    )
    associated = await service.decide(
        ctx,
        matter.matter_id,
        candidate_id,
        ReviewFactInput(
            "associate", 1, reason="Synthetic holder", transaction_id=txn_id, subject_id=party.id
        ),
        key="associate",
    )
    view = await service.get_view(ctx, matter.matter_id, associated.id)
    candidate = await db_session.get(ProcessingCandidateFieldRow, candidate_id)
    candidate.version += 1
    await db_session.flush()
    with pytest.raises(PreconditionFailedError):
        await service.decide(
            ctx,
            matter.matter_id,
            associated.id,
            ReviewFactInput("accept", associated.version, expected_scope_token=view.scope_token),
            key="accept",
        )


async def test_acceptance_preserves_all_existing_evidence_links(db_session, matter):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    fact = await service.add_manual(ctx, matter.matter_id, data, key="manual")
    repository = SqlVerificationRepository(db_session)
    additional = await repository.create_evidence(
        EvidenceReference(
            new_id("evidence"),
            ctx.actor_id,
            matter.matter_id,
            data.evidence.source_file_id,
            1,
            data.evidence.source_sha256,
            datetime.now(UTC),
        )
    )
    # A legacy fact may already cite several pages/sources.
    row = await db_session.get(ExtractedFactRow, fact.id)
    row.evidence_reference_ids = [*row.evidence_reference_ids, additional.id]
    await db_session.flush()
    view = await service.get_view(ctx, matter.matter_id, fact.id)
    accepted = await service.decide(
        ctx,
        matter.matter_id,
        fact.id,
        ReviewFactInput("accept", fact.version, expected_scope_token=view.scope_token),
        key="accept",
    )
    assert len(accepted.evidence_reference_ids) == 2


async def test_register_http_contract_requires_headers_and_returns_history_cursor(
    db_session, matter
):
    from httpx import ASGITransport, AsyncClient

    from src.api.deps import get_request_context
    from src.main import create_app
    from src.platform.db.session import get_db

    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "http-register")
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_request_context] = lambda: ctx
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        path = f"/api/v1/matters/{matter.matter_id}/facts"
        body = {
            "factTypeId": "rta.parcel.village",
            "value": "SYNTHETIC",
            "reason": "Synthetic instructions",
        }
        missing_key = await client.post(path, json=body)
        assert missing_key.status_code == 400
        added = await client.post(path, json=body, headers={"Idempotency-Key": "http-add"})
        assert added.status_code == 201, added.text
        original = added.json()
        assert original["scopeStatus"] == "unassigned" and original["status"] == "REVIEW_REQUIRED"
        rejected = await client.post(
            f"{path}/{original['id']}/reject",
            json={"reason": "Synthetic rejection"},
            headers={"Idempotency-Key": "http-reject", "If-Match": added.headers["ETag"]},
        )
        assert rejected.status_code == 200, rejected.text
        history = await client.get(f"{path}/{rejected.json()['id']}/history?limit=1")
        cursor = history.json()["page"]["nextCursor"]
        assert cursor
        next_page = await client.get(
            f"{path}/{rejected.json()['id']}/history", params={"limit": 1, "cursor": cursor}
        )
        assert next_page.json()["items"][0]["status"] == "REJECTED"
        assert (await client.get(f"{path}?limit=101")).status_code == 422

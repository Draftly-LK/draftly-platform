"""Synthetic regressions for the independent scoped-register review findings."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.deps import get_request_context
from src.bootstrap import (
    build_fact_review_service,
    build_matter_scope_service,
    build_source_file_storage,
)
from src.main import create_app
from src.modules.document.contracts import FactEvidenceLocator
from src.modules.document.infrastructure.fact_reader import SqlDocumentFactReader
from src.modules.document.infrastructure.orm import (
    DocumentFragmentRow,
    DocumentProcessingPageRow,
    ProcessingCandidateFieldRow,
    SourceFileRow,
)
from src.modules.verification.application.review_service import ManualFactInput, ReviewFactInput
from src.modules.verification.domain.errors import NegativeFactRequiresSearchError
from src.modules.verification.domain.models import EvidenceReference
from src.modules.verification.infrastructure.orm import ExtractedFactRow
from src.modules.verification.infrastructure.repository import SqlVerificationRepository
from src.platform.db.session import get_db
from src.platform.errors import DomainRuleError
from src.platform.ids import new_id
from tests.db.test_scoped_fact_review import machine_candidate, scoped_input
from tests.db.test_scoped_fact_review import matter as matter


async def accept(service, ctx, matter_id, fact, key):
    view = await service.get_view(ctx, matter_id, fact.id)
    return await service.decide(
        ctx,
        matter_id,
        fact.id,
        ReviewFactInput("accept", fact.version, expected_scope_token=view.scope_token),
        key=key,
    )


async def second_source(session, source):
    fields = {
        column.name: getattr(source, column.name) for column in SourceFileRow.__table__.columns
    }
    identity = new_id("source")
    content = b"%PDF-1.4 SYNTHETIC SECOND SOURCE ONLY"
    key = f"synthetic/{identity}.pdf"
    version = await build_source_file_storage().put(key, content)
    fields.update(
        id=identity,
        byte_length=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_object_key=key,
        storage_object_version=version,
        state="PROCESSED",
    )
    result = SourceFileRow(**fields)
    session.add(result)
    await session.flush()
    return result


@pytest.mark.parametrize("different", ["subject", "transaction", "both", "same"])
async def test_negative_conclusion_uses_only_search_in_its_scope(db_session, matter, different):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    search = await service.add_manual(
        ctx,
        matter.matter_id,
        replace(data, fact_type_id="rta.title.register_search_datetime", value="2026-10-09"),
        key="search",
    )
    await accept(service, ctx, matter.matter_id, search, "search-accept")
    scopes = build_matter_scope_service(db_session)
    subject = await scopes.create_subject(ctx, matter.matter_id, kind="parcel", key="other-parcel")
    transaction = await scopes.create_transaction(ctx, matter.matter_id, key="other-txn")
    negative = await service.add_manual(
        ctx,
        matter.matter_id,
        replace(
            data,
            fact_type_id="rta.interest.mortgage_status",
            value="NONE",
            transaction_id=transaction.id
            if different in ("transaction", "both")
            else data.transaction_id,
            subject_id=subject.id if different in ("subject", "both") else data.subject_id,
        ),
        key="negative",
    )
    if different == "same":
        assert (
            await accept(service, ctx, matter.matter_id, negative, "negative-accept")
        ).is_confirmed
    else:
        with pytest.raises(NegativeFactRequiresSearchError):
            await accept(service, ctx, matter.matter_id, negative, "negative-accept")


@pytest.mark.parametrize("secondary_state", ["PROCESSED", "SUPERSEDED", "missing"])
async def test_old_extraction_refuses_complete_mixed_source_grouping(
    db_session, matter, secondary_state
):
    ctx, _, candidate_id = await machine_candidate(db_session, matter)
    reader = SqlDocumentFactReader(db_session, build_source_file_storage())
    candidate = await reader.get_candidate(ctx.actor_id, matter.matter_id, candidate_id)
    source = await db_session.get(SourceFileRow, candidate.evidence.source_file_id)
    secondary = await second_source(db_session, source)
    if secondary_state == "missing":
        secondary.storage_object_key = "synthetic/missing-secondary"
    else:
        secondary.state = secondary_state
        if secondary_state == "SUPERSEDED":
            secondary.superseded_by_source_file_id = source.id
    db_session.add(
        DocumentFragmentRow(
            id=new_id("fragment"),
            user_id=ctx.actor_id,
            matter_id=matter.matter_id,
            detected_document_id=candidate.evidence.detected_document_id,
            source_file_id=secondary.id,
            page_start=1,
            page_end=1,
            order_in_document=1,
            boundary_status="LAWYER_CONFIRMED",
        )
    )
    await db_session.flush()
    current = await reader.get_candidate(ctx.actor_id, matter.matter_id, candidate_id)
    assert current is not None and not current.current
    with pytest.raises(DomainRuleError):
        await reader.validate_evidence(ctx.actor_id, matter.matter_id, candidate.evidence)


async def test_distinct_source_evidence_is_retained_and_each_source_revalidated(db_session, matter):
    ctx, data = await scoped_input(db_session, matter)
    source = await db_session.get(SourceFileRow, data.evidence.source_file_id)
    secondary = await second_source(db_session, source)
    service = build_fact_review_service(db_session)
    fact = await service.add_manual(ctx, matter.matter_id, data, key="manual")
    repo = SqlVerificationRepository(db_session)
    extra = await repo.create_evidence(
        EvidenceReference(
            new_id("evidence"),
            ctx.actor_id,
            matter.matter_id,
            secondary.id,
            1,
            secondary.sha256,
            datetime.now(UTC),
        )
    )
    row = await db_session.get(ExtractedFactRow, fact.id)
    row.evidence_reference_ids = [*row.evidence_reference_ids, extra.id]
    await db_session.flush()
    confirmed = await accept(service, ctx, matter.matter_id, fact, "accept")
    references = await repo.list_evidence(ctx.actor_id, confirmed.evidence_reference_ids)
    assert {r.source_file_id for r in references} == {source.id, secondary.id}
    secondary.state = "SUPERSEDED"
    secondary.superseded_by_source_file_id = source.id
    await db_session.flush()
    view = await service.get_view(ctx, matter.matter_id, confirmed.id)
    with pytest.raises(DomainRuleError):
        await service.decide(
            ctx,
            matter.matter_id,
            confirmed.id,
            ReviewFactInput(
                "correct",
                confirmed.version,
                reason="Synthetic correction",
                value="SYNTHETIC B",
                expected_scope_token=view.scope_token,
            ),
            key="correct",
        )


async def test_resolved_machine_loser_stays_historical_after_fresh_read(
    db_committing, tmp_path, monkeypatch
):
    async with db_committing() as session:
        report = await matter.__wrapped__(session, tmp_path, monkeypatch)
        ctx, txn, first_id = await machine_candidate(session, report)
        service = build_fact_review_service(session)
        party = await build_matter_scope_service(session).create_subject(
            ctx,
            report.matter_id,
            kind="party",
            key="holder",
        )
        first = await session.get(ProcessingCandidateFieldRow, first_id)
        second_id = new_id("candidate")
        session.add(
            ProcessingCandidateFieldRow(
                id=second_id,
                user_id=ctx.actor_id,
                matter_id=report.matter_id,
                logical_document_id=first.logical_document_id,
                key=first.key,
                candidate_value="199900000099",
                page_no=1,
                model_reported_confidence=1,
            )
        )
        await session.flush()
        associated = []
        for identity in (first_id, second_id):
            associated.append(
                await service.decide(
                    ctx,
                    report.matter_id,
                    identity,
                    ReviewFactInput(
                        "associate",
                        1,
                        reason="Synthetic holder",
                        transaction_id=txn,
                        subject_id=party.id,
                    ),
                    key=identity,
                )
            )
        winner, loser = associated
        view = await service.get_view(ctx, report.matter_id, winner.id)
        resolved = await service.decide(
            ctx,
            report.matter_id,
            winner.id,
            ReviewFactInput(
                "accept",
                winner.version,
                reason="Synthetic resolution",
                expected_scope_token=view.scope_token,
                resolve_fact_ids=(loser.id,),
            ),
            key="resolve",
        )
        await session.commit()
    async with db_committing() as session:
        service = build_fact_review_service(session)
        register, _ = await service.list_facts(ctx, report.matter_id)
        assert not any(v.fact.source_candidate_id == second_id for v in register)
        assert any(v.fact.id == resolved.id for v in register)
        original = await service.get_view(ctx, report.matter_id, second_id)
        assert original.fact.status.value == "SUPERSEDED"
        history = await service.history(ctx, report.matter_id, second_id)
        assert [f.id for f in history.facts] == [second_id, loser.id]
        assert history.facts[-1].superseded_by_fact_id == resolved.id
        assert (await service.get_view(ctx, report.matter_id, resolved.id)).fact.is_confirmed


async def test_missing_optional_ocr_keeps_page_precision_and_manual_review(db_session, matter):
    ctx, txn, candidate_id = await machine_candidate(db_session, matter)
    page = (await db_session.execute(select(DocumentProcessingPageRow))).scalar_one()
    page.plain_text_key = "synthetic/missing-ocr"
    await db_session.flush()
    service = build_fact_review_service(db_session)
    view = await service.get_view(ctx, matter.matter_id, candidate_id)
    assert not view.fact.evidence_stale
    assert len(view.evidence) == 1
    assert view.evidence[0].precision == "page"
    assert not view.evidence[0].page_text and view.evidence[0].text_span is None
    register, _ = await service.list_facts(ctx, matter.matter_id)
    assert next(v for v in register if v.fact.id == candidate_id).evidence[0].precision == "page"
    party = await build_matter_scope_service(db_session).create_subject(
        ctx, matter.matter_id, kind="party", key="holder"
    )
    associated = await service.decide(
        ctx,
        matter.matter_id,
        candidate_id,
        ReviewFactInput(
            "associate",
            1,
            reason="Synthetic holder",
            transaction_id=txn,
            subject_id=party.id,
        ),
        key="associate",
    )
    assert (await accept(service, ctx, matter.matter_id, associated, "accept")).is_confirmed


@pytest.mark.parametrize("artifact", ["original", "page"])
async def test_unavailable_candidate_does_not_hide_healthy_register_rows(
    db_session, matter, artifact
):
    ctx, txn, candidate_id = await machine_candidate(db_session, matter)
    reader = SqlDocumentFactReader(db_session, build_source_file_storage())
    candidate = await reader.get_candidate(ctx.actor_id, matter.matter_id, candidate_id)
    source = await db_session.get(SourceFileRow, candidate.evidence.source_file_id)
    secondary = await second_source(db_session, source)
    transaction = await build_matter_scope_service(db_session).get_transaction(
        ctx, matter.matter_id, txn
    )
    service = build_fact_review_service(db_session)
    healthy = await service.add_manual(
        ctx,
        matter.matter_id,
        ManualFactInput(
            "rta.parcel.village",
            "SYNTHETIC HEALTHY",
            "Synthetic input",
            txn,
            transaction.parcel_subject_ids[0],
            FactEvidenceLocator(secondary.id, 1, secondary.sha256),
        ),
        key="healthy",
    )
    if artifact == "original":
        source.storage_object_key = "synthetic/missing-original"
    else:
        page = (await db_session.execute(select(DocumentProcessingPageRow))).scalar_one()
        page.corrected_webp_key = "synthetic/missing-page"
    await db_session.flush()
    with pytest.raises(DomainRuleError, match="artifact is unavailable"):
        await reader.validate_evidence(ctx.actor_id, matter.matter_id, candidate.evidence)
    register, _ = await service.list_facts(ctx, matter.matter_id)
    unavailable = next(v for v in register if v.fact.id == candidate_id)
    assert unavailable.fact.evidence_stale and not unavailable.evidence
    assert any(v.fact.id == healthy.id and not v.fact.evidence_stale for v in register)
    assert (await service.get_view(ctx, matter.matter_id, candidate_id)).fact.evidence_stale


@pytest.mark.parametrize("action", ["accept", "correct"])
@pytest.mark.parametrize("scope", ["foreign", "mismatch", "matching"])
async def test_non_associate_commands_refuse_explicit_scope(db_session, matter, action, scope):
    ctx, data = await scoped_input(db_session, matter)
    scopes = build_matter_scope_service(db_session)
    subject = await scopes.create_subject(ctx, matter.matter_id, kind="parcel", key="other")
    txn = await scopes.create_transaction(ctx, matter.matter_id, key="other")
    service = build_fact_review_service(db_session)
    fact = await service.add_manual(ctx, matter.matter_id, data, key="manual")
    view = await service.get_view(ctx, matter.matter_id, fact.id)
    transaction_id, subject_id = {
        "foreign": ("foreign-transaction", "foreign-subject"),
        "mismatch": (txn.id, subject.id),
        "matching": (data.transaction_id, data.subject_id),
    }[scope]
    command = ReviewFactInput(
        action,
        fact.version,
        reason="Synthetic review",
        value=data.value,
        transaction_id=transaction_id,
        subject_id=subject_id,
        expected_scope_token=view.scope_token,
    )
    with pytest.raises(DomainRuleError, match="associate"):
        await service.decide(ctx, matter.matter_id, fact.id, command, key="review")
    assert (
        await service.get_view(ctx, matter.matter_id, fact.id)
    ).fact.status.value == "REVIEW_REQUIRED"
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_request_context] = lambda: ctx
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/matters/{matter.matter_id}/facts/{fact.id}/{action}",
            json={
                "transactionId": transaction_id,
                "subjectId": subject_id,
                "reason": "Synthetic review",
                "value": data.value,
                "expectedScopeToken": view.scope_token,
            },
            headers={"If-Match": f'"{fact.version}"', "Idempotency-Key": "http-review"},
        )
        assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["transactionId", "subjectId"])
async def test_non_associate_http_refuses_explicit_null_scope(db_session, matter, field):
    ctx, data = await scoped_input(db_session, matter)
    service = build_fact_review_service(db_session)
    fact = await service.add_manual(ctx, matter.matter_id, data, key="manual")
    view = await service.get_view(ctx, matter.matter_id, fact.id)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_request_context] = lambda: ctx
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/matters/{matter.matter_id}/facts/{fact.id}/accept",
            json={field: None, "expectedScopeToken": view.scope_token},
            headers={"If-Match": f'"{fact.version}"', "Idempotency-Key": "http-review"},
        )
        assert response.status_code == 422, response.text


async def test_http_associate_returns_every_precondition_needed_for_acceptance(db_session, matter):
    ctx, txn, candidate_id = await machine_candidate(db_session, matter)
    party = await build_matter_scope_service(db_session).create_subject(
        ctx, matter.matter_id, kind="party", key="holder"
    )
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_request_context] = lambda: ctx
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        path = f"/api/v1/matters/{matter.matter_id}/facts"
        original = await client.get(f"{path}/{candidate_id}")
        assert original.status_code == 200
        associated = await client.post(
            f"{path}/{candidate_id}/associate",
            json={"transactionId": txn, "subjectId": party.id, "reason": "Synthetic holder"},
            headers={"If-Match": original.headers["ETag"], "Idempotency-Key": "http-associate"},
        )
        assert associated.status_code == 200, associated.text
        body = associated.json()
        accepted = await client.post(
            f"{path}/{body['id']}/accept",
            json={"expectedScopeToken": body["scopeToken"]},
            headers={"If-Match": associated.headers["ETag"], "Idempotency-Key": "http-accept"},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "LAWYER_CONFIRMED"
        assert accepted.json()["subjectId"] == party.id

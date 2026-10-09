"""Synthetic operational work on the real migration chain and API."""

from dataclasses import replace

import pytest
from sqlalchemy import select

from src.bootstrap import build_work_task_service
from src.modules.auth.domain.models import Role
from src.modules.document.infrastructure.orm import SourceFileRow
from src.modules.task.contracts import ReadinessReference
from src.modules.task.infrastructure.orm import WorkHistoryRow, WorkTaskRow
from src.platform.errors import (
    CapabilityDeniedError,
    DomainRuleError,
    NotFoundError,
    PreconditionFailedError,
)
from src.platform.request_context import RequestContext
from tests.db.test_scoped_fact_review import matter as matter


async def source_pin(session, matter):
    source = await session.scalar(
        select(SourceFileRow).where(SourceFileRow.matter_id == matter.matter_id)
    )
    return source, ReadinessReference("source-file", source.id, source.version)


async def test_completion_stales_after_source_change_and_history_survives(db_session, matter):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-work")
    service = build_work_task_service(db_session)
    source, pin = await source_pin(db_session, matter)
    task = await service.create(
        ctx,
        matter.matter_id,
        title="Synthetic evidence review",
        reason="Synthetic work only",
        group="execution",
        evidence=(pin,),
    )
    task = await service.decide(
        ctx,
        matter.matter_id,
        task.id,
        expected_version=1,
        decision="complete",
        note="Synthetic reviewed record",
    )
    assert task.version == 2 and task.completed_by == ctx.actor_id
    source.version += 1
    await db_session.flush()
    tasks, suggestions, progress, next_id = await service.checklist(ctx, matter.matter_id)
    assert next(row for row in tasks if row.id == task.id).state == "stale"
    with pytest.raises(PreconditionFailedError):
        await service.decide(
            ctx, matter.matter_id, task.id, expected_version=2, decision="complete"
        )
    with pytest.raises(DomainRuleError):
        await service.decide(
            ctx, matter.matter_id, task.id, expected_version=2, decision="complete", evidence=()
        )
    task = await service.decide(
        ctx, matter.matter_id, task.id, expected_version=2, decision="review"
    )
    assert task.state == "not-started" and task.evidence[0].version == pin.version + 1
    history = await service.history(ctx, matter.matter_id, task.id, after=None, limit=50)
    assert len(history) == 3
    assert any(row.decision == "complete" and row.evidence == (pin,) for row in history)
    assert task.completed_by == ctx.actor_id
    assert progress[1] < progress[0]
    assert suggestions == [] and next_id is not None


async def test_agent_suggestions_deduplicate_require_acceptance_and_reject_changed_pins(
    db_session, matter
):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-suggestion")
    service = build_work_task_service(db_session)
    source, pin = await source_pin(db_session, matter)
    args = {
        "title": "Synthetic proposed review",
        "reason": "Synthetic extracted work",
        "group": "documents",
        "evidence": (pin,),
        "dedup_key": "synthetic-processing-1",
    }
    first = await service.create_suggestion(ctx, matter.matter_id, **args)
    duplicate = await service.create_suggestion(ctx, matter.matter_id, **args)
    assert first.id == duplicate.id
    tasks, suggestions, _, _ = await service.checklist(ctx, matter.matter_id)
    assert first.id not in {row.id for row in tasks}
    assert suggestions[0].id == first.id
    source.version += 1
    await db_session.flush()
    with pytest.raises(PreconditionFailedError):
        await service.decide_suggestion(
            ctx, matter.matter_id, first.id, expected_version=1, decision="accept"
        )
    dismissed = await service.decide_suggestion(
        ctx, matter.matter_id, first.id, expected_version=1, decision="dismiss"
    )
    assert dismissed.state == "cancelled"
    fresh = await service.create_suggestion(
        ctx, matter.matter_id, **{**args, "evidence": (replace(pin, version=source.version),)}
    )
    accepted = await service.decide_suggestion(
        ctx, matter.matter_id, fresh.id, expected_version=1, decision="accept"
    )
    assert accepted.state == "not-started" and accepted.origin == "agent"


async def test_operational_records_never_change_matter_lifecycle_and_foreign_access_is_hidden(
    db_session, matter
):
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-work")
    service = build_work_task_service(db_session)
    from src.bootstrap import build_matter_service

    before = await build_matter_service(db_session).get_access_summary(
        ctx.actor_id, matter.matter_id
    )
    for group in ("execution", "registration", "completion"):
        result = await service.decide(
            ctx,
            matter.matter_id,
            f"work:{matter.matter_id}:{group}",
            expected_version=1,
            decision="complete",
            note="Synthetic recorded work",
        )
        assert result.completed_by == ctx.actor_id
    after = await build_matter_service(db_session).get_access_summary(
        ctx.actor_id, matter.matter_id
    )
    assert before == after
    with pytest.raises(NotFoundError):
        await service.checklist(replace(ctx, actor_id="usr_foreign_synthetic"), matter.matter_id)
    with pytest.raises(CapabilityDeniedError):
        await service.create(
            replace(ctx, account_role=Role.ADMINISTRATOR),
            matter.matter_id,
            title="Synthetic denied",
            reason=None,
            group="documents",
        )
    with pytest.raises(NotFoundError):
        await service.decide(
            ctx, matter.matter_id, "foreign-task", expected_version=1, decision="complete"
        )


async def test_work_api_replays_concurrency_and_signed_history_pagination(db_session, matter):
    from httpx import ASGITransport, AsyncClient

    from src.api.deps import get_request_context
    from src.main import create_app
    from src.platform.db.session import get_db

    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-api-work")
    # Each HTTP error rolls back its request UoW; keep the seeded baseline
    # outside that request savepoint while the fixture's outer rollback remains.
    await db_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_request_context] = lambda: ctx
    path = f"/api/v1/matters/{matter.matter_id}/work-tasks"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://synthetic") as client:
        body = {"title": "Synthetic task", "reason": "Synthetic work", "group": "completion"}
        assert (await client.post(path, json=body)).status_code == 400
        created = await client.post(
            path, json=body, headers={"Idempotency-Key": "synthetic-create"}
        )
        assert created.status_code == 201, created.text
        repeated = await client.post(
            path, json=body, headers={"Idempotency-Key": "synthetic-create"}
        )
        assert repeated.json()["id"] == created.json()["id"]
        task_path = f"{path}/{created.json()['id']}/decisions"
        assert (
            await client.post(
                task_path,
                json={"decision": "complete"},
                headers={"Idempotency-Key": "synthetic-complete"},
            )
        ).status_code == 428
        headers = {"Idempotency-Key": "synthetic-complete", "If-Match": '"1"'}
        completed = await client.post(task_path, json={"decision": "complete"}, headers=headers)
        assert completed.status_code == 200, completed.text
        assert (
            await client.post(task_path, json={"decision": "complete"}, headers=headers)
        ).json() == completed.json()
        assert (
            await client.post(
                task_path,
                json={"decision": "review"},
                headers={**headers, "Idempotency-Key": "synthetic-stale"},
            )
        ).status_code == 412
        history_path = f"{path}/{created.json()['id']}/history"
        page = await client.get(history_path, params={"limit": 1})
        assert len(page.json()["items"]) == 1 and page.json()["nextCursor"]
        next_page = await client.get(
            history_path, params={"limit": 1, "cursor": page.json()["nextCursor"]}
        )
        assert next_page.json()["items"][0]["id"] != page.json()["items"][0]["id"]
        assert (await client.get(history_path, params={"cursor": "forged"})).status_code == 400
        rows = await db_session.scalars(
            select(WorkTaskRow).where(WorkTaskRow.title == body["title"])
        )
        assert len(list(rows)) == 1
        records = await db_session.scalars(
            select(WorkHistoryRow).where(WorkHistoryRow.task_id == created.json()["id"])
        )
        assert len(list(records)) == 2


async def test_reviewer_can_propose_but_cannot_accept_operational_suggestion(db_session, matter):
    reviewer = RequestContext(matter.lawyer_id, Role.REVIEWER, "synthetic-reviewer-proposal")
    service = build_work_task_service(db_session)
    _, pin = await source_pin(db_session, matter)
    proposal = await service.create_suggestion(
        reviewer,
        matter.matter_id,
        title="Synthetic proposal",
        reason="Synthetic source review",
        group="documents",
        evidence=(pin,),
        dedup_key="synthetic-reviewer-proposal",
    )
    assert proposal.state == "pending-applicability"
    with pytest.raises(CapabilityDeniedError):
        await service.decide_suggestion(
            reviewer, matter.matter_id, proposal.id, expected_version=1, decision="accept"
        )


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
async def test_source_support_requires_recorded_object_integrity_without_mutation(
    db_session, matter, failure
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from src.bootstrap import build_ingestion_service
    from src.modules.document.domain.errors import SourceObjectNotFoundError

    source, pin = await source_pin(db_session, matter)
    reader = build_ingestion_service(db_session)
    get = (
        AsyncMock(side_effect=SourceObjectNotFoundError())
        if failure == "missing"
        else AsyncMock(return_value=b"SYNTHETIC CORRUPTED OBJECT")
    )
    reader._storage = SimpleNamespace(get=get)
    assert not await reader.has_current_original(
        user_id=matter.lawyer_id, matter_id=matter.matter_id, source_file_id=source.id
    )
    await db_session.refresh(source)
    assert source.version == pin.version

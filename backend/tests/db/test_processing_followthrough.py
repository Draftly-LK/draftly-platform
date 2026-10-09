"""Synthetic ingestion route to committed outbox to lawyer-accepted work."""

from io import BytesIO

from httpx import ASGITransport, AsyncClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from sqlalchemy import select

from src.api.deps import get_request_context
from src.bootstrap import build_dispatcher, build_ingestion_service, build_work_task_service
from src.main import create_app
from src.modules.auth.domain.models import Role
from src.modules.document.infrastructure.orm import DetectedDocumentRow
from src.platform.db.session import get_db
from src.platform.messaging.dispatcher import MessageResult
from src.platform.messaging.orm import OutboxRow
from src.platform.messaging.outbox import ClaimedMessage
from src.platform.request_context import RequestContext
from tests.db.test_scoped_fact_review import matter as matter


async def test_processing_route_queues_deduplicated_review_work(db_session, matter, monkeypatch):
    import src.platform.config as config

    monkeypatch.setenv("EXTRACTION_PROVIDER", "vision-stub")
    monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "true")
    config._settings = None
    ctx = RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-followthrough")
    image = Image.new("RGB", (400, 200), "white")
    metadata = PngInfo()
    metadata.add_text("Comment", "STUB-KIND:survey-plan\n")
    content = BytesIO()
    image.save(content, format="PNG", pnginfo=metadata)
    uploaded = await build_ingestion_service(db_session).upload_source_file(
        user_id=ctx.actor_id,
        matter_id=matter.matter_id,
        actor_id=ctx.actor_id,
        correlation_id=ctx.correlation_id,
        filename="SYNTHETIC-FOLLOWTHROUGH.png",
        declared_media_type="image/png",
        data=content.getvalue(),
    )
    source = uploaded.source_file
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_request_context] = lambda: ctx
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://synthetic") as client:
        route = f"/api/v1/source-files/{source.id}/process"
        headers = {"If-Match": f'"{source.version}"', "Idempotency-Key": "synthetic-process"}
        response = await client.post(route, headers=headers)
        assert response.status_code == 200, response.text
        assert (await client.post(route, headers=headers)).json() == response.json()
    events = list(
        await db_session.scalars(
            select(OutboxRow).where(OutboxRow.name == "document.processing-completed")
        )
    )
    assert len(events) == 1
    event = events[0]
    assert "SYNTHETIC-FOLLOWTHROUGH" not in str(event.payload)
    message = ClaimedMessage(
        event.id,
        event.organisation_id,
        event.kind,
        event.name,
        event.payload,
        event.idempotency_key,
        0,
    )
    assert await build_dispatcher().dispatch(db_session, message) is MessageResult.DONE
    assert await build_dispatcher().dispatch(db_session, message) is MessageResult.DONE
    service = build_work_task_service(db_session)
    tasks, suggestions, _, _ = await service.checklist(ctx, matter.matter_id)
    assert len(suggestions) == 1
    proposal = suggestions[0]
    assert proposal.id not in {task.id for task in tasks}
    assert proposal.evidence[0].id == source.id
    assert proposal.title_key == "matterChecklist.tasks.documentReview.title"
    accepted = await service.decide_suggestion(
        ctx, matter.matter_id, proposal.id, expected_version=proposal.version, decision="accept"
    )
    assert accepted.state == "not-started"
    assert any(ref.kind == "document" for ref in accepted.evidence)
    completed = await service.decide(
        ctx, matter.matter_id, accepted.id, expected_version=accepted.version, decision="complete"
    )
    doc_pin = next(ref for ref in completed.evidence if ref.kind == "document")
    document = await db_session.get(DetectedDocumentRow, doc_pin.id)
    document.version += 1
    document.interpretation_generation += 1
    await db_session.flush()
    changed, _, _, _ = await service.checklist(ctx, matter.matter_id)
    assert next(task for task in changed if task.id == completed.id).state == "stale"
    current_source = (
        await build_ingestion_service(db_session).get_source_file(
            user_id=ctx.actor_id, source_file_id=source.id
        )
    ).source_file
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://synthetic") as client:
        rerun = await client.post(
            route,
            headers={
                "If-Match": f'"{current_source.version}"',
                "Idempotency-Key": "synthetic-rerun",
            },
        )
        assert rerun.status_code == 200, rerun.text
    queued = list(
        await db_session.scalars(
            select(OutboxRow)
            .where(OutboxRow.name == "document.processing-completed")
            .order_by(OutboxRow.id)
        )
    )
    assert len(queued) == 2
    assert queued[-1].payload["data"]["documentReferences"]

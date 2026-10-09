"""Committed requirement commands replay after access checks, over migrated PostgreSQL."""

import asyncio
from dataclasses import replace

from src.bootstrap import build_checklist_service
from src.modules.auth.domain.models import Role
from src.modules.content_governance.contracts import TRANSFER_SALE_SUBTYPE_ID, CompilerInput
from tests.db.test_ingestion_replay import client as client


async def test_requirement_decision_replay_is_once_and_authorization_precedes_replay(
    client, db_committing
):
    http, matter, identity = client
    async with db_committing() as session:
        service = build_checklist_service(session)
        await service.compile_snapshot(
            user_id=matter.lawyer_id,
            matter_id=matter.matter_id,
            compiler_input=CompilerInput(subtype_id=TRANSFER_SALE_SUBTYPE_ID),
            actor_id=matter.lawyer_id,
            correlation_id="synthetic-replay",
        )
        view = await service.get_checklist(user_id=matter.lawyer_id, matter_id=matter.matter_id)
        item = view.items[0].item
        await session.commit()
    path = f"/api/v1/matters/{matter.matter_id}/checklist-items/{item.id}/decisions"
    body = {"collection": "REQUESTED"}
    headers = {"If-Match": f'"{item.version}"', "Idempotency-Key": "synthetic-requirement-once"}
    assert (
        await http.post(path, json=body, headers={"Idempotency-Key": "synthetic-missing-version"})
    ).status_code == 428
    assert (
        await http.post(path, json=body, headers={"If-Match": headers["If-Match"]})
    ).status_code == 400
    first, replay = await asyncio.gather(
        *[http.post(path, json=body, headers=headers) for _ in range(2)]
    )
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["version"] == item.version + 1
    assert (
        await http.post(path, json={"collection": "MISSING"}, headers=headers)
    ).status_code == 409
    identity["ctx"] = replace(identity["ctx"], account_role=Role.ADMINISTRATOR)
    assert (await http.post(path, json=body, headers=headers)).status_code == 403
    identity["ctx"] = replace(identity["ctx"], actor_id="usr_synthetic_foreign")
    assert (await http.post(path, json=body, headers=headers)).status_code == 404


async def test_link_and_original_inspection_replay_preserve_one_history_entry(
    client, db_committing
):
    from datetime import UTC, datetime, timedelta

    from src.modules.auth.infrastructure.orm import UserRow
    from src.modules.document.infrastructure.orm import DetectedDocumentRow
    from tests.db.test_requirement_evidence import requirement

    http, matter, identity = client
    async with db_committing() as session:
        user = await session.get(UserRow, matter.lawyer_id)
        user.notary_registration = "SYNTHETIC-PRACTICE-ONLY"
        user.certificate_valid_until = datetime.now(UTC) + timedelta(days=30)
        await session.flush()
        await session.refresh(user)
        service, ctx, _, document_id = await requirement(session, matter)
        checklist = await service.get_checklist(user_id=ctx.actor_id, matter_id=matter.matter_id)
        item = next(
            row.item
            for row in checklist.items
            if row.requirement.id == "R_C20_ORIGINAL_TITLE_CERTIFICATE_INSPECTED"
        )
        document = await session.get(DetectedDocumentRow, document_id)
        document.class_id = "rta.doc.title_certificate"
        body = {
            "detectedDocumentId": document_id,
            "documentVersion": document.version,
            "interpretationGeneration": document.interpretation_generation,
        }
        await session.commit()
    path = f"/api/v1/matters/{matter.matter_id}/checklist-items/{item.id}"
    headers = {"If-Match": f'"{item.version}"', "Idempotency-Key": "synthetic-link-once"}
    assert (
        await http.post(
            path + "/links", json=body, headers={"Idempotency-Key": "synthetic-missing-version"}
        )
    ).status_code == 428
    assert (
        await http.post(path + "/links", json=body, headers={"If-Match": headers["If-Match"]})
    ).status_code == 400
    first, replay = await asyncio.gather(
        *[http.post(path + "/links", json=body, headers=headers) for _ in range(2)]
    )
    assert first.status_code == replay.status_code == 201, first.text
    assert first.json() == replay.json()
    headers = {"If-Match": f'"{item.version + 1}"', "Idempotency-Key": "synthetic-inspect-once"}
    body = {"method": "Synthetic sighting at office"}
    assert (
        await http.post(
            path + "/original-inspection",
            json=body,
            headers={"Idempotency-Key": "synthetic-missing-version"},
        )
    ).status_code == 428
    assert (
        await http.post(
            path + "/original-inspection", json=body, headers={"If-Match": headers["If-Match"]}
        )
    ).status_code == 400
    first, replay = await asyncio.gather(
        *[http.post(path + "/original-inspection", json=body, headers=headers) for _ in range(2)]
    )
    assert first.status_code == replay.status_code == 200, first.text
    assert first.json() == replay.json()
    assert len(first.json()["inspectionHistory"]) == 1
    assert first.json()["originalInspection"]["originals"]
    identity["ctx"] = replace(identity["ctx"], account_role=Role.ADMINISTRATOR)
    assert (
        await http.post(path + "/original-inspection", json=body, headers=headers)
    ).status_code == 403

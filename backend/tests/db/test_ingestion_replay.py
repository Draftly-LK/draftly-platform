"""Committed synthetic HTTP retries: no provider access and no shared fake session."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from scripts.seed_synthetic_matter import seed
from src.api.deps import get_request_context
from src.main import create_app
from src.modules.auth.domain.models import Role
from src.modules.document.infrastructure.orm import (
    DocumentInterpretationRow,
    SourceFileProcessingRunRow,
    SourceFileRow,
)
from src.modules.matter.infrastructure.orm import MatterRow
from src.platform.db.idempotency import IdempotencyKeyRow
from src.platform.db.session import get_db
from src.platform.request_context import RequestContext
from tests.factories.document import synthetic_pdf


@pytest.fixture
async def client(db_committing, tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("EXTRACTION_PROVIDER", "none")
    monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "false")
    import src.platform.config as config

    config._settings = None
    async with db_committing() as session:
        matter = await seed(session)
        await session.commit()
    app = create_app()
    identity = {"ctx": RequestContext(matter.lawyer_id, Role.APPROVER, "synthetic-http-retry")}

    async def session_dependency():
        async with db_committing() as session:
            yield session

    app.dependency_overrides[get_db] = session_dependency
    app.dependency_overrides[get_request_context] = lambda: identity["ctx"]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://synthetic.test"
    ) as http:
        yield http, matter, identity


async def test_concurrent_upload_replays_and_intentional_identical_upload_stays_distinct(
    client, db_committing
):
    http, matter, _ = client
    path = f"/api/v1/matters/{matter.matter_id}/source-files"

    async def upload(key):
        response = await http.post(
            path,
            files={"file": ("synthetic.pdf", synthetic_pdf(3), "application/pdf")},
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 201, response.text
        return response.json()

    first, replay = await asyncio.gather(upload("same-upload"), upload("same-upload"))
    assert first["id"] == replay["id"]
    deliberate = await upload("new-upload")
    assert deliberate["id"] != first["id"]
    assert deliberate["duplicateOfSourceFileId"] == first["id"]
    async with db_committing() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(SourceFileRow)
                .where(SourceFileRow.original_filename == "synthetic.pdf")
            )
            == 2
        )
    changed = await http.post(
        path,
        files={"file": ("synthetic.pdf", synthetic_pdf(2), "application/pdf")},
        headers={"Idempotency-Key": "same-upload"},
    )
    assert changed.status_code == 409


async def test_process_network_retry_reuses_run_terminal_failure_retry_starts_new_run(
    client, db_committing
):
    http, matter, _ = client
    uploaded = await http.post(
        f"/api/v1/matters/{matter.matter_id}/source-files",
        files={"file": ("synthetic.pdf", synthetic_pdf(1), "application/pdf")},
        headers={"Idempotency-Key": "upload-process"},
    )
    source = uploaded.json()
    path = f"/api/v1/source-files/{source['id']}/process"
    headers = {"Idempotency-Key": "first-run", "If-Match": uploaded.headers["ETag"]}
    first, replay = await asyncio.gather(
        http.post(path, headers=headers), http.post(path, headers=headers)
    )
    assert first.status_code == replay.status_code == 200
    assert first.json()["jobId"] == replay.json()["jobId"]
    assert first.json()["state"] == "failed"
    current = await http.get(f"/api/v1/source-files/{source['id']}")
    retry = await http.post(
        path,
        headers={"Idempotency-Key": "known-failure-retry", "If-Match": current.headers["ETag"]},
    )
    assert retry.status_code == 200
    assert retry.json()["jobId"] != first.json()["jobId"]
    async with db_committing() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(SourceFileProcessingRunRow)
                .where(SourceFileProcessingRunRow.source_file_id == source["id"])
            )
            == 2
        )


async def test_concurrent_matter_create_is_replayed_and_changed_body_conflicts(
    client, db_committing
):
    http, _, _ = client
    headers = {"Idempotency-Key": "create-intent"}
    first, replay = await asyncio.gather(
        *[
            http.post("/api/v1/matters", json={"reference": "SYNTHETIC-RETRY"}, headers=headers)
            for _ in range(2)
        ]
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    changed = await http.post(
        "/api/v1/matters", json={"reference": "SYNTHETIC-CHANGED"}, headers=headers
    )
    assert changed.status_code == 409
    async with db_committing() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(MatterRow)
                .where(MatterRow.reference == "SYNTHETIC-RETRY")
            )
            == 1
        )


async def test_correction_replay_keeps_historical_response_without_reviving_current_generation(
    client, db_committing
):
    http, matter, identity = client
    uploaded = await http.post(
        f"/api/v1/matters/{matter.matter_id}/source-files",
        files={"file": ("synthetic.pdf", synthetic_pdf(1), "application/pdf")},
        headers={"Idempotency-Key": "upload-correction"},
    )
    group = await http.post(
        f"/api/v1/matters/{matter.matter_id}/detected-documents",
        json={
            "classId": "rta.doc.nic",
            "fragments": [{"sourceFileId": uploaded.json()["id"], "pageStart": 1, "pageEnd": 1}],
        },
        headers={"Idempotency-Key": "group-correction"},
    )
    assert group.status_code == 201, group.text
    path = f"/api/v1/detected-documents/{group.json()['id']}/classification-decisions"
    headers = {"Idempotency-Key": "correct-once", "If-Match": group.headers["ETag"]}
    first, replay = await asyncio.gather(
        *[
            http.post(path, json={"classId": "rta.doc.title_certificate"}, headers=headers)
            for _ in range(2)
        ]
    )
    assert first.status_code == replay.status_code == 200
    assert (
        first.json()["interpretationGeneration"] == replay.json()["interpretationGeneration"] == 2
    )
    back = await http.post(
        path,
        json={"classId": "rta.doc.nic"},
        headers={
            "Idempotency-Key": "correct-back",
            "If-Match": first.headers["ETag"],
        },
    )
    assert back.status_code == 200
    old = await http.post(path, json={"classId": "rta.doc.title_certificate"}, headers=headers)
    assert old.json()["interpretationGeneration"] == 2
    current = await http.get(f"/api/v1/detected-documents/{group.json()['id']}")
    assert current.json()["interpretationGeneration"] == 3
    assert current.json()["extractionState"] == "refresh_required"
    async with db_committing() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DocumentInterpretationRow)
                .where(DocumentInterpretationRow.detected_document_id == group.json()["id"])
            )
            == 3
        )
    identity["ctx"] = replace(identity["ctx"], actor_id="synthetic-foreign-user")
    assert (
        await http.post(path, json={"classId": "rta.doc.title_certificate"}, headers=headers)
    ).status_code == 404


async def test_refresh_and_boundary_replays_append_once_and_authorization_precedes_cache(
    client, db_committing
):
    http, matter, identity = client
    uploaded = await http.post(
        f"/api/v1/matters/{matter.matter_id}/source-files",
        files={"file": ("synthetic.pdf", synthetic_pdf(2), "application/pdf")},
        headers={"Idempotency-Key": "refresh-upload"},
    )
    fragments = [{"sourceFileId": uploaded.json()["id"], "pageStart": 1, "pageEnd": 2}]
    group = await http.post(
        f"/api/v1/matters/{matter.matter_id}/detected-documents",
        json={"classId": "rta.doc.nic", "fragments": fragments},
        headers={"Idempotency-Key": "refresh-group"},
    )
    document_id = group.json()["id"]
    path = f"/api/v1/detected-documents/{document_id}"
    boundary_headers = {"Idempotency-Key": "boundary-once", "If-Match": group.headers["ETag"]}
    one_page = [{**fragments[0], "pageEnd": 1}]
    first, replay = await asyncio.gather(
        *[
            http.post(
                path + "/boundary-decisions", json={"fragments": one_page}, headers=boundary_headers
            )
            for _ in range(2)
        ]
    )
    assert first.status_code == replay.status_code == 200
    assert first.json()["version"] == replay.json()["version"]
    headers = {"Idempotency-Key": "refresh-once", "If-Match": first.headers["ETag"]}
    first, replay = await asyncio.gather(
        *[http.post(path + "/refresh-extraction", headers=headers) for _ in range(2)]
    )
    assert first.status_code == replay.status_code == 200
    assert first.json()["latestRefreshRunId"] == replay.json()["latestRefreshRunId"]
    assert first.json()["extractionState"] == "failed"
    async with db_committing() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(SourceFileProcessingRunRow)
                .where(SourceFileProcessingRunRow.detected_document_id == document_id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DocumentInterpretationRow)
                .where(DocumentInterpretationRow.detected_document_id == document_id)
            )
            == 2
        )
    identity["ctx"] = replace(identity["ctx"], account_role=Role.ADMINISTRATOR)
    assert (await http.post(path + "/refresh-extraction", headers=headers)).status_code == 403


async def test_expired_upload_key_can_be_used_without_unique_collision(client, db_committing):
    http, matter, _ = client
    path = f"/api/v1/matters/{matter.matter_id}/source-files"

    async def upload():
        return await http.post(
            path,
            files={"file": ("synthetic.pdf", synthetic_pdf(1), "application/pdf")},
            headers={"Idempotency-Key": "expire-upload"},
        )

    first = await upload()
    assert first.status_code == 201
    async with db_committing() as session:
        row = (
            await session.execute(
                select(IdempotencyKeyRow).where(
                    IdempotencyKeyRow.idempotency_key == "expire-upload"
                )
            )
        ).scalar_one()
        row.created_at = datetime.now(UTC) - timedelta(hours=25)
        await session.commit()
    second = await upload()
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]

"""Real intake + ingestion wiring, synthetic provider doubles, migrated PostgreSQL."""

from io import BytesIO

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from sqlalchemy import select

from src.bootstrap import build_ingestion_service
from src.modules.matter.application.matter_service import CreateMatterInput
from src.modules.task.infrastructure.orm import ChecklistSnapshotRow
from tests.db.test_matter_service import owner as owner


@pytest.mark.parametrize(
    "kind,document_class",
    [
        ("identity-card", "rta.doc.nic"),
        ("title-certificate", "rta.doc.title_certificate"),
        ("survey-plan", "rta.doc.survey_plan"),
        ("form8-instrument", "rta.doc.form8_instrument"),
    ],
)
async def test_intake_extracts_supported_candidates_before_any_subtype_or_checklist(
    db_session, owner, monkeypatch, kind, document_class
):
    import src.platform.config as config

    monkeypatch.setenv("EXTRACTION_PROVIDER", "vision-stub")
    monkeypatch.setenv("PROVIDER_DATA_APPROVAL", "true")
    config._settings = None
    matters, ctx, _ = owner
    matter = await matters.create_matter(ctx, CreateMatterInput(reference="SYN/INTAKE/ONLY"))
    image = Image.new("RGB", (400, 200), "white")
    meta = PngInfo()
    meta.add_text("Comment", f"STUB-KIND:{kind}\n")
    stream = BytesIO()
    image.save(stream, format="PNG", pnginfo=meta)
    ingestion = build_ingestion_service(db_session)
    upload = await ingestion.upload_source_file(
        user_id=ctx.actor_id,
        matter_id=matter.id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-intake",
        filename="SYNTHETIC-INTAKE.png",
        declared_media_type="image/png",
        data=stream.getvalue(),
    )
    result = await ingestion.process_source_file(
        user_id=ctx.actor_id,
        source_file_id=upload.source_file.id,
        actor_id=ctx.actor_id,
        correlation_id="synthetic-intake",
        expected_version=upload.source_file.version,
    )
    assert result.run.succeeded
    assert result.run.candidates[0].class_id == document_class
    assert result.run.candidates[0].candidate_fields
    assert all(field.value for field in result.run.candidates[0].candidate_fields)
    assert matter.subtype_id is None
    assert (
        not (
            await db_session.execute(
                select(ChecklistSnapshotRow.id).where(ChecklistSnapshotRow.matter_id == matter.id)
            )
        )
        .scalars()
        .all()
    )

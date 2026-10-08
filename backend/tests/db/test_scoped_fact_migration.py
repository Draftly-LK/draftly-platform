"""The reviewed backfill preserves history and never assigns a NIC holder role."""

from datetime import UTC, datetime

from alembic import command
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.pool import NullPool

from tests.db.postgres import database_url
from tests.db.test_migrations import _config, _scoped, _sync, empty_schema  # noqa: F401

__all__ = ["empty_schema"]


def test_legacy_backfill_is_scoped_preserves_history_and_survives_cycle(empty_schema):
    command.upgrade(_config(), "verification0002")
    engine = create_engine(_sync(_scoped(database_url(), empty_schema)), poolclass=NullPool)
    metadata = MetaData()
    tables = {
        name: Table(name, metadata, autoload_with=engine)
        for name in (
            "source_files",
            "source_file_processing_runs",
            "processing_logical_documents",
            "extracted_facts",
            "processing_candidate_fields",
            "review_decisions",
        )
    }
    now = datetime.now(UTC)
    cases = (
        ("nic", "rta.doc.nic", "transfereeNic", "owner", "matter"),
        ("parcel", "rta.doc.survey_plan", "parcelNo", "owner", "matter"),
        ("foreign-user", "rta.doc.nic", "transfereeNic", "other", "matter"),
        ("foreign-matter", "rta.doc.nic", "transfereeNic", "owner", "other"),
    )
    before_facts, before_decisions = {}, {}
    try:
        with engine.begin() as connection:
            for suffix, type_id, key, candidate_user, candidate_matter in cases:
                fact_id, source_id, run_id, logical_id = (
                    f"{kind}_{suffix}" for kind in ("fact", "source", "run", "logical")
                )
                connection.execute(
                    tables["source_files"]
                    .insert()
                    .values(
                        id=source_id,
                        user_id=candidate_user,
                        matter_id=candidate_matter,
                        original_filename="synthetic.pdf",
                        media_type="application/pdf",
                        byte_length=1,
                        sha256="a" * 64,
                        storage_object_key="synthetic",
                        storage_object_version="1",
                        upload_actor_id=candidate_user,
                        state="PROCESSED",
                        page_count=1,
                        detected_languages=[],
                        retention_class="synthetic",
                        version=1,
                    )
                )
                connection.execute(
                    tables["source_file_processing_runs"]
                    .insert()
                    .values(
                        id=run_id,
                        user_id=candidate_user,
                        matter_id=candidate_matter,
                        source_file_id=source_id,
                        provider="synthetic",
                        outcome="PROCESSED",
                        reasons=[],
                        pages_processed=1,
                        ai_extraction_calls=0,
                        started_at=now,
                        finished_at=now,
                        correlation_id="synthetic",
                    )
                )
                connection.execute(
                    tables["processing_logical_documents"]
                    .insert()
                    .values(
                        id=logical_id,
                        user_id=candidate_user,
                        matter_id=candidate_matter,
                        source_file_id=source_id,
                        processing_run_id=run_id,
                        document_index=0,
                        type_id=type_id,
                        page_numbers=[1],
                    )
                )
                connection.execute(
                    tables["extracted_facts"]
                    .insert()
                    .values(
                        id=fact_id,
                        user_id="owner",
                        matter_id="matter",
                        fact_type_id="rta.party.transferee_nic"
                        if key == "transfereeNic"
                        else "rta.parcel.parcel_number",
                        value="SYNTHETIC CORRECTED VALUE",
                        status="LAWYER_CONFIRMED",
                        evidence_reference_ids=[],
                        derivation_input_fact_ids=[],
                        reviewed_by="owner",
                        reviewed_at=now,
                        review_decision_id=f"decision_{suffix}",
                        version=2,
                    )
                )
                connection.execute(
                    tables["processing_candidate_fields"]
                    .insert()
                    .values(
                        id=f"candidate_{suffix}",
                        user_id=candidate_user,
                        matter_id=candidate_matter,
                        logical_document_id=logical_id,
                        key=key,
                        candidate_value="SYNTHETIC ORIGINAL VALUE",
                        edited_value="SYNTHETIC CORRECTED VALUE",
                        page_no=1,
                        model_reported_confidence=1,
                        review_state="approved",
                        approved_by=candidate_user,
                        approved_at=now,
                        approved_fact_id=fact_id,
                        version=2,
                    )
                )
                connection.execute(
                    tables["review_decisions"]
                    .insert()
                    .values(
                        id=f"decision_{suffix}",
                        user_id="owner",
                        matter_id="matter",
                        target_type="FACT",
                        target_id=fact_id,
                        decision="correct",
                        previous_value="SYNTHETIC ORIGINAL VALUE",
                        new_value="SYNTHETIC CORRECTED VALUE",
                        reason="Synthetic review",
                        reviewer_id="owner",
                        reviewer_role="approver",
                        human_decision=True,
                    )
                )
            before_facts = {
                row.id: dict(row._mapping)
                for row in connection.execute(select(tables["extracted_facts"]))
            }
            before_decisions = {
                row.id: dict(row._mapping)
                for row in connection.execute(select(tables["review_decisions"]))
            }
        command.upgrade(_config(), "head")
        facts = Table("extracted_facts", MetaData(), autoload_with=engine)
        decisions = Table("review_decisions", MetaData(), autoload_with=engine)
        with engine.connect() as connection:
            rows = {row.id: row._mapping for row in connection.execute(select(facts))}
            for fact_id, prior in before_facts.items():
                for name, value in prior.items():
                    if name != "scope_status":
                        assert rows[fact_id][name] == value
            assert rows["fact_nic"]["scope_status"] == "unassigned"
            assert rows["fact_parcel"]["scope_status"] == "legacy-unassigned"
            for suffix in ("nic", "parcel"):
                assert rows[f"fact_{suffix}"]["source_candidate_id"] == f"candidate_{suffix}"
                assert rows[f"fact_{suffix}"]["original_value"] == "SYNTHETIC ORIGINAL VALUE"
            for suffix in ("foreign-user", "foreign-matter"):
                assert rows[f"fact_{suffix}"]["source_candidate_id"] is None
                assert rows[f"fact_{suffix}"]["scope_status"] == "legacy-unassigned"
            for row in connection.execute(select(decisions)):
                assert all(
                    row._mapping[name] == value for name, value in before_decisions[row.id].items()
                )
        command.downgrade(_config(), "verification0002")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    select(tables["extracted_facts"].c.scope_status).where(
                        tables["extracted_facts"].c.id == "fact_nic"
                    )
                ).scalar_one()
                == "unassigned"
            )
        command.upgrade(_config(), "head")
    finally:
        engine.dispose()

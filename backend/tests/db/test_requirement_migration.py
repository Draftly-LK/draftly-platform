"""Populated legacy evidence stays historical; rollback refuses new bindings."""

from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.pool import NullPool

from tests.db.postgres import database_url
from tests.db.test_migrations import _config, _scoped, _sync, empty_schema  # noqa: F401

__all__ = ["empty_schema"]


def test_legacy_links_and_inspection_upgrade_without_invented_bindings(empty_schema):
    command.upgrade(_config(), "document0004")
    engine = create_engine(_sync(_scoped(database_url(), empty_schema)), poolclass=NullPool)

    def table(name):
        return Table(name, MetaData(), autoload_with=engine)

    try:
        with engine.begin() as connection:
            connection.execute(
                table("checklist_snapshots")
                .insert()
                .values(
                    id="snapshot",
                    user_id="synthetic",
                    matter_id="synthetic",
                    compiler_version="1",
                    taxonomy_version="1",
                    checklist_version="1",
                    rule_pack_version="1",
                    fingerprint="a" * 64,
                    module_definition_ids=[],
                    created_by="synthetic",
                )
            )
            connection.execute(
                table("checklist_items")
                .insert()
                .values(
                    id="item",
                    user_id="synthetic",
                    matter_id="synthetic",
                    snapshot_id="snapshot",
                    requirement_definition_id="synthetic",
                    module_definition_id="synthetic",
                    inclusion_reason="MANDATORY",
                    applicability="REQUIRED",
                    collection="RECEIVED",
                    digital_review="LAWYER_CONFIRMED",
                    physical_original="ORIGINAL_INSPECTED",
                    currency="CURRENT",
                    consistency="MATCHED",
                    resolution="SATISFIED",
                    original_inspection_reviewer_id="synthetic",
                    original_inspection_at=datetime.now(UTC),
                    original_inspection_method="SYNTHETIC SIGHTING",
                    version=1,
                )
            )
            connection.execute(
                table("checklist_satisfaction_links")
                .insert()
                .values(
                    id="link",
                    user_id="synthetic",
                    matter_id="synthetic",
                    checklist_item_id="item",
                    detected_document_id="synthetic-document",
                    digital_review="LAWYER_CONFIRMED",
                    evidence_reference_ids=[],
                    created_by="synthetic",
                )
            )
        command.upgrade(_config(), "head")
        items, links = table("checklist_items"), table("checklist_satisfaction_links")
        with engine.begin() as connection:
            item = connection.execute(select(items)).mappings().one()
            link = connection.execute(select(links)).mappings().one()
            assert item["original_inspection_method"] == "SYNTHETIC SIGHTING"
            assert item["original_inspection_sources"] == item["inspection_history"] == []
            assert link["document_version"] is None and link["interpretation_generation"] is None
            assert link["originals"] == [] and link["digital_review"] == "LAWYER_CONFIRMED"
            connection.execute(
                items.update().values(inspection_history=[{"synthetic": "retained"}])
            )
        with pytest.raises(RuntimeError, match="inspection history"):
            command.downgrade(_config(), "document0004")
        with engine.connect() as connection:
            assert connection.execute(select(items.c.inspection_history)).scalar_one() == [
                {"synthetic": "retained"}
            ]
    finally:
        engine.dispose()

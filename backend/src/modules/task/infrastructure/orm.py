"""ORM models for compiled checklists.

The snapshot table has no update path by design: a recompile inserts a new row
pointing at the one it supersedes. Items belong to exactly one snapshot, so the
state a matter was worked under stays readable after the rules change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.platform.db.session import Base


class ChecklistSnapshotRow(Base):
    __tablename__ = "checklist_snapshots"
    __table_args__ = (
        Index("ix_checklist_snapshots_user_matter", "user_id", "matter_id"),
        Index("ix_checklist_snapshots_fingerprint", "matter_id", "fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(32), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checklist_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    module_definition_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supersedes_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChecklistItemRow(Base):
    """One requirement on one matter under one snapshot.

    The seven status columns are separate columns, not one enum, because §5.4
    needs them to disagree with each other.
    """

    __tablename__ = "checklist_items"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "requirement_definition_id",
            name="uq_checklist_item_snapshot_requirement",
        ),
        Index("ix_checklist_items_user_matter", "user_id", "matter_id"),
        Index("ix_checklist_items_snapshot", "snapshot_id"),
        # Defence in depth for §5.4: even a direct SQL write cannot claim an
        # inspected original without the reviewer, time, and method that make it
        # an inspection.
        CheckConstraint(
            "(physical_original <> 'ORIGINAL_INSPECTED') OR "
            "(original_inspection_reviewer_id IS NOT NULL "
            "AND original_inspection_at IS NOT NULL "
            "AND original_inspection_method IS NOT NULL)",
            name="ck_checklist_item_original_inspection_requires_human",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("checklist_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    requirement_definition_id: Mapped[str] = mapped_column(String(128), nullable=False)
    module_definition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    inclusion_reason: Mapped[str] = mapped_column(String(40), nullable=False)
    inclusion_trigger_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicability: Mapped[str] = mapped_column(String(32), nullable=False)
    collection: Mapped[str] = mapped_column(String(32), nullable=False)
    digital_review: Mapped[str] = mapped_column(String(32), nullable=False)
    physical_original: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(32), nullable=False)
    consistency: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    applicability_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicability_decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    local_authority_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Physical-original inspection is stored inline rather than as a nullable
    # flag so the reviewer, time, and method can never drift apart from the
    # status they justify (§5.4).
    original_inspection_reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_inspection_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    original_inspection_method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_inspection_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_inspection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_inspection_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    inspection_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SatisfactionLinkRow(Base):
    """Many-to-many between items and detected documents, each with a decision.

    One combined certificate links to several items; each link is reviewed on its
    own merits, and replacing the document supersedes the link rather than
    deleting it (§5.4, §6.3).
    """

    __tablename__ = "checklist_satisfaction_links"
    __table_args__ = (
        Index("ix_satisfaction_links_user_matter", "user_id", "matter_id"),
        Index("ix_satisfaction_links_item", "checklist_item_id"),
        Index("ix_satisfaction_links_document", "detected_document_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    matter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    checklist_item_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("checklist_items.id", ondelete="CASCADE"), nullable=False
    )
    detected_document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    document_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interpretation_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    originals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    digital_review: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_reference_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_by_link_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

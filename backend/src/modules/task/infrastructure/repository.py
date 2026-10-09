"""SQLAlchemy repositories for compiled checklists."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    ApplicabilityStatus,
    CollectionStatus,
    ConsistencyStatus,
    CurrencyStatus,
    DigitalReviewStatus,
    PhysicalOriginalStatus,
    ResolutionStatus,
)
from src.modules.document.contracts import OriginalSourcePin
from src.modules.task.domain.errors import ChecklistItemStaleError
from src.modules.task.domain.models import (
    ChecklistItem,
    ChecklistSnapshot,
    OriginalInspection,
    SatisfactionLink,
)
from src.modules.task.infrastructure.orm import (
    ChecklistItemRow,
    ChecklistSnapshotRow,
    SatisfactionLinkRow,
)


def _to_snapshot(row: ChecklistSnapshotRow) -> ChecklistSnapshot:
    return ChecklistSnapshot(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        compiler_version=row.compiler_version,
        taxonomy_version=row.taxonomy_version,
        checklist_version=row.checklist_version,
        rule_pack_version=row.rule_pack_version,
        fingerprint=row.fingerprint,
        module_definition_ids=tuple(row.module_definition_ids),
        created_at=row.created_at,
        created_by=row.created_by,
        supersedes_id=row.supersedes_id,
    )


def _to_item(row: ChecklistItemRow) -> ChecklistItem:
    inspection = None
    if row.original_inspection_reviewer_id and row.original_inspection_at:
        inspection = OriginalInspection(
            reviewer_id=row.original_inspection_reviewer_id,
            inspected_at=row.original_inspection_at,
            method=row.original_inspection_method or "",
            location=row.original_inspection_location,
            note=row.original_inspection_note,
            originals=tuple(OriginalSourcePin(**pin) for pin in row.original_inspection_sources),
        )
    return ChecklistItem(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        snapshot_id=row.snapshot_id,
        requirement_definition_id=row.requirement_definition_id,
        module_definition_id=row.module_definition_id,
        inclusion_reason=row.inclusion_reason,
        inclusion_trigger_id=row.inclusion_trigger_id,
        applicability=ApplicabilityStatus(row.applicability),
        collection=CollectionStatus(row.collection),
        digital_review=DigitalReviewStatus(row.digital_review),
        physical_original=(
            PhysicalOriginalStatus.UNKNOWN
            if row.physical_original == "ORIGINAL_INSPECTED"
            and (
                not inspection
                or not inspection.originals
                or not all(pin.precise for pin in inspection.originals)
            )
            else PhysicalOriginalStatus(row.physical_original)
        ),
        currency=CurrencyStatus(row.currency),
        consistency=ConsistencyStatus(row.consistency),
        resolution=ResolutionStatus(row.resolution),
        applicability_reason=row.applicability_reason,
        applicability_decided_by=row.applicability_decided_by,
        assigned_to=row.assigned_to,
        due_at=row.due_at,
        local_authority_id=row.local_authority_id,
        original_inspection=inspection,
        inspection_history=tuple(
            OriginalInspection(
                reviewer_id=entry["reviewer_id"],
                inspected_at=datetime.fromisoformat(entry["inspected_at"]),
                method=entry["method"],
                location=entry.get("location"),
                note=entry.get("note"),
                originals=tuple(OriginalSourcePin(**pin) for pin in entry.get("originals", [])),
            )
            for entry in row.inspection_history
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


def _apply_item(row: ChecklistItemRow, item: ChecklistItem) -> None:
    row.applicability = item.applicability.value
    row.collection = item.collection.value
    row.digital_review = item.digital_review.value
    row.physical_original = item.physical_original.value
    row.currency = item.currency.value
    row.consistency = item.consistency.value
    row.resolution = item.resolution.value
    row.applicability_reason = item.applicability_reason
    row.applicability_decided_by = item.applicability_decided_by
    row.assigned_to = item.assigned_to
    row.due_at = item.due_at
    row.local_authority_id = item.local_authority_id
    inspection = item.original_inspection
    row.original_inspection_reviewer_id = inspection.reviewer_id if inspection else None
    row.original_inspection_at = inspection.inspected_at if inspection else None
    row.original_inspection_method = inspection.method if inspection else None
    row.original_inspection_location = inspection.location if inspection else None
    row.original_inspection_note = inspection.note if inspection else None
    row.original_inspection_sources = (
        [asdict(pin) for pin in inspection.originals] if inspection else []
    )
    row.inspection_history = [
        {**asdict(entry), "inspected_at": entry.inspected_at.isoformat()}
        for entry in item.inspection_history
    ]


def _to_link(row: SatisfactionLinkRow) -> SatisfactionLink:
    return SatisfactionLink(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        checklist_item_id=row.checklist_item_id,
        detected_document_id=row.detected_document_id,
        document_version=row.document_version,
        interpretation_generation=row.interpretation_generation,
        originals=tuple(OriginalSourcePin(**pin) for pin in row.originals),
        digital_review=DigitalReviewStatus(row.digital_review),
        evidence_reference_ids=tuple(row.evidence_reference_ids),
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_note=row.review_note,
        superseded_by_link_id=row.superseded_by_link_id,
        created_by=row.created_by,
        created_at=row.created_at,
    )


class SqlChecklistRepository:
    """Snapshots, items, and satisfaction links for one request's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Snapshots ────────────────────────────────────────────────────────────

    async def create_snapshot(self, snapshot: ChecklistSnapshot) -> ChecklistSnapshot:
        row = ChecklistSnapshotRow(
            id=snapshot.id,
            user_id=snapshot.user_id,
            matter_id=snapshot.matter_id,
            compiler_version=snapshot.compiler_version,
            taxonomy_version=snapshot.taxonomy_version,
            checklist_version=snapshot.checklist_version,
            rule_pack_version=snapshot.rule_pack_version,
            fingerprint=snapshot.fingerprint,
            module_definition_ids=list(snapshot.module_definition_ids),
            supersedes_id=snapshot.supersedes_id,
            created_by=snapshot.created_by,
            created_at=snapshot.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_snapshot(row)

    async def get_snapshot(self, user_id: str, snapshot_id: str) -> ChecklistSnapshot | None:
        result = await self._session.execute(
            select(ChecklistSnapshotRow).where(
                ChecklistSnapshotRow.user_id == user_id,
                ChecklistSnapshotRow.id == snapshot_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_snapshot(row) if row is not None else None

    async def latest_snapshot(self, user_id: str, matter_id: str) -> ChecklistSnapshot | None:
        result = await self._session.execute(
            select(ChecklistSnapshotRow)
            .where(
                ChecklistSnapshotRow.user_id == user_id,
                ChecklistSnapshotRow.matter_id == matter_id,
            )
            .order_by(ChecklistSnapshotRow.created_at.desc(), ChecklistSnapshotRow.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_snapshot(row) if row is not None else None

    async def find_snapshot_by_fingerprint(
        self, user_id: str, matter_id: str, fingerprint: str
    ) -> ChecklistSnapshot | None:
        """Used to make compilation idempotent over unchanged inputs (§12.4)."""
        result = await self._session.execute(
            select(ChecklistSnapshotRow)
            .where(
                ChecklistSnapshotRow.user_id == user_id,
                ChecklistSnapshotRow.matter_id == matter_id,
                ChecklistSnapshotRow.fingerprint == fingerprint,
            )
            .order_by(ChecklistSnapshotRow.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_snapshot(row) if row is not None else None

    # ── Items ────────────────────────────────────────────────────────────────

    async def create_items(self, items: list[ChecklistItem]) -> list[ChecklistItem]:
        rows = []
        for item in items:
            row = ChecklistItemRow(
                id=item.id,
                user_id=item.user_id,
                matter_id=item.matter_id,
                snapshot_id=item.snapshot_id,
                requirement_definition_id=item.requirement_definition_id,
                module_definition_id=item.module_definition_id,
                inclusion_reason=item.inclusion_reason,
                inclusion_trigger_id=item.inclusion_trigger_id,
                created_at=item.created_at,
                updated_at=item.updated_at,
                version=item.version,
                applicability=item.applicability.value,
                collection=item.collection.value,
                digital_review=item.digital_review.value,
                physical_original=item.physical_original.value,
                currency=item.currency.value,
                consistency=item.consistency.value,
                resolution=item.resolution.value,
                local_authority_id=item.local_authority_id,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return [_to_item(row) for row in rows]

    async def list_items(self, user_id: str, snapshot_id: str) -> list[ChecklistItem]:
        result = await self._session.execute(
            select(ChecklistItemRow)
            .where(
                ChecklistItemRow.user_id == user_id,
                ChecklistItemRow.snapshot_id == snapshot_id,
            )
            .order_by(
                ChecklistItemRow.module_definition_id.asc(),
                ChecklistItemRow.requirement_definition_id.asc(),
            )
        )
        return [_to_item(row) for row in result.scalars().all()]

    async def get_item(self, user_id: str, item_id: str) -> ChecklistItem | None:
        row = await self._item_row(user_id, item_id)
        return _to_item(row) if row is not None else None

    async def _item_row(self, user_id: str, item_id: str) -> ChecklistItemRow | None:
        result = await self._session.execute(
            select(ChecklistItemRow).where(
                ChecklistItemRow.user_id == user_id, ChecklistItemRow.id == item_id
            )
        )
        return result.scalar_one_or_none()

    async def update_item(self, item: ChecklistItem, expected_version: int) -> ChecklistItem:
        result = await self._session.execute(
            update(ChecklistItemRow)
            .where(
                ChecklistItemRow.id == item.id,
                ChecklistItemRow.user_id == item.user_id,
                ChecklistItemRow.version == expected_version,
            )
            .values(version=expected_version + 1)
            .returning(ChecklistItemRow.id)
        )
        if result.scalar_one_or_none() is None:
            raise ChecklistItemStaleError(expectedVersion=expected_version)
        row = await self._item_row(item.user_id, item.id)
        if row is None:
            raise ChecklistItemStaleError(expectedVersion=expected_version)
        _apply_item(row, item)
        row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return _to_item(row)

    async def reviewed_requirement_ids(self, user_id: str, matter_id: str) -> list[str]:
        """Requirements a human has already worked, across every snapshot.

        Feeds the compiler's retention rule: an item that stops being triggered
        but has been reviewed is carried forward, not dropped (§5.1).
        """
        result = await self._session.execute(
            select(ChecklistItemRow.requirement_definition_id)
            .where(
                ChecklistItemRow.user_id == user_id,
                ChecklistItemRow.matter_id == matter_id,
                ChecklistItemRow.digital_review != DigitalReviewStatus.UNREVIEWED.value,
            )
            .distinct()
        )
        return list(result.scalars().all())

    # ── Satisfaction links ───────────────────────────────────────────────────

    async def create_link(self, link: SatisfactionLink) -> SatisfactionLink:
        row = SatisfactionLinkRow(
            id=link.id,
            user_id=link.user_id,
            matter_id=link.matter_id,
            checklist_item_id=link.checklist_item_id,
            detected_document_id=link.detected_document_id,
            document_version=link.document_version,
            interpretation_generation=link.interpretation_generation,
            originals=[asdict(pin) for pin in link.originals],
            digital_review=link.digital_review.value,
            evidence_reference_ids=list(link.evidence_reference_ids),
            reviewed_by=link.reviewed_by,
            reviewed_at=link.reviewed_at,
            review_note=link.review_note,
            created_by=link.created_by,
            created_at=link.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_link(row)

    async def list_links_for_item(self, user_id: str, item_id: str) -> list[SatisfactionLink]:
        result = await self._session.execute(
            select(SatisfactionLinkRow)
            .where(
                SatisfactionLinkRow.user_id == user_id,
                SatisfactionLinkRow.checklist_item_id == item_id,
            )
            .order_by(SatisfactionLinkRow.created_at.asc())
        )
        return [_to_link(row) for row in result.scalars().all()]

    async def list_links_for_items(
        self, user_id: str, item_ids: Sequence[str]
    ) -> list[SatisfactionLink]:
        """Every link for a set of items, in one round trip.

        Reading a checklist needs the links for all of its items, and asking per
        item costs one query each — 79 on an ordinary transfer, against a remote
        database. The caller groups the result; `is_live` stays a domain rule
        rather than being restated as SQL here, where it could drift.
        """
        if not item_ids:
            return []
        result = await self._session.execute(
            select(SatisfactionLinkRow)
            .where(
                SatisfactionLinkRow.user_id == user_id,
                SatisfactionLinkRow.checklist_item_id.in_(list(item_ids)),
            )
            .order_by(SatisfactionLinkRow.created_at.asc())
        )
        return [_to_link(row) for row in result.scalars().all()]

    async def list_links_for_document(
        self, user_id: str, detected_document_id: str
    ) -> list[SatisfactionLink]:
        result = await self._session.execute(
            select(SatisfactionLinkRow)
            .where(
                SatisfactionLinkRow.user_id == user_id,
                SatisfactionLinkRow.detected_document_id == detected_document_id,
            )
            .order_by(SatisfactionLinkRow.created_at.asc())
        )
        return [_to_link(row) for row in result.scalars().all()]

    async def supersede_item_document_links(
        self, user_id: str, item_id: str, document_id: str, replacement_id: str
    ) -> None:
        await self._session.execute(
            update(SatisfactionLinkRow)
            .where(
                SatisfactionLinkRow.user_id == user_id,
                SatisfactionLinkRow.checklist_item_id == item_id,
                SatisfactionLinkRow.detected_document_id == document_id,
                SatisfactionLinkRow.id != replacement_id,
                SatisfactionLinkRow.superseded_by_link_id.is_(None),
            )
            .values(superseded_by_link_id=replacement_id, digital_review="SUPERSEDED")
        )
        await self._session.flush()

    async def supersede_links_for_document(
        self, user_id: str, detected_document_id: str, *, replacement_link_id: str | None
    ) -> int:
        """Mark a replaced document's links superseded. History is preserved."""
        result = await self._session.execute(
            update(SatisfactionLinkRow)
            .where(
                SatisfactionLinkRow.user_id == user_id,
                SatisfactionLinkRow.detected_document_id == detected_document_id,
                SatisfactionLinkRow.superseded_by_link_id.is_(None),
            )
            .values(
                superseded_by_link_id=replacement_link_id,
                digital_review=DigitalReviewStatus.SUPERSEDED.value,
            )
            # RETURNING gives a portable count; ``rowcount`` on an async
            # CursorResult is not part of the typed surface.
            .returning(SatisfactionLinkRow.id)
        )
        superseded = list(result.scalars().all())
        await self._session.flush()
        return len(superseded)

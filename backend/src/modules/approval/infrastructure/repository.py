"""SQLAlchemy repositories for approvals, exports, and registration events.

Every query filters on ``user_id`` first — that is the tenancy boundary in this
deployment, not a convenience predicate (plan §5.3 invariant 10).

There is no update path and no delete path anywhere in this file except
`SqlApprovalRepository.revoke`, which writes the one field an approval ever
changes and refuses to clear it. All three tables are records of human acts:
an act that was recorded and then edited away is not an audit trail.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.approval.domain.models import (
    Approval,
    ExportFormat,
    FormExport,
    RegistrationEvent,
)
from src.modules.approval.infrastructure.orm import (
    ApprovalRow,
    FormExportRow,
    RegistrationEventRow,
)
from src.modules.content_governance.contracts import (
    ApprovalTargetType,
    RegistrationEventType,
    RtaWorkflowRole,
)
from src.platform.pagination import Cursor, decode_cursor, encode_cursor


def _encode_cursor(created_at: datetime, record_id: str) -> str:
    return encode_cursor(Cursor(created_at=created_at, id=record_id))


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """The keyset position, or InvalidCursorError (400) for a forged or bad cursor."""
    decoded = decode_cursor(cursor)
    return (decoded.created_at, decoded.id) if decoded is not None else None


def _to_approval(row: ApprovalRow) -> Approval:
    return Approval(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        target_type=ApprovalTargetType(row.target_type),
        target_id=row.target_id,
        target_version=row.target_version,
        approver_id=row.approver_id,
        approver_workflow_role=RtaWorkflowRole(row.approver_workflow_role),
        declaration_version=row.declaration_version,
        declaration_text_hash=row.declaration_text_hash,
        snapshot_hash=row.snapshot_hash,
        confirmed_fact_hash=row.confirmed_fact_hash,
        warning_disposition_ids=tuple(row.warning_disposition_ids),
        template_id=row.template_id,
        template_version=row.template_version,
        rule_pack_version=row.rule_pack_version,
        created_at=row.created_at,
        revoked_by_approval_id=row.revoked_by_approval_id,
    )


def _to_export(row: FormExportRow) -> FormExport:
    return FormExport(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        generated_form_id=row.generated_form_id,
        approval_id=row.approval_id,
        export_format=ExportFormat(row.export_format),
        artifact_hash=row.artifact_hash,
        artifact_key=row.artifact_key,
        watermarked=row.watermarked,
        registration_ready=row.registration_ready,
        manifest=dict(row.manifest),
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _to_event(row: RegistrationEventRow) -> RegistrationEvent:
    return RegistrationEvent(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        generated_form_id=row.generated_form_id,
        event_type=RegistrationEventType(row.event_type),
        event_date=row.event_date,
        evidence_reference_ids=tuple(row.evidence_reference_ids),
        day_book_reference=row.day_book_reference,
        registry_office=row.registry_office,
        result_note=row.result_note,
        recorded_by=row.recorded_by,
        created_at=row.created_at,
    )


class SqlApprovalRepository:
    """Implements ``ApprovalRepository`` over one request's AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, approval: Approval) -> Approval:
        row = ApprovalRow(
            id=approval.id,
            user_id=approval.user_id,
            matter_id=approval.matter_id,
            target_type=approval.target_type.value,
            target_id=approval.target_id,
            target_version=approval.target_version,
            approver_id=approval.approver_id,
            approver_workflow_role=approval.approver_workflow_role.value,
            declaration_version=approval.declaration_version,
            declaration_text_hash=approval.declaration_text_hash,
            snapshot_hash=approval.snapshot_hash,
            confirmed_fact_hash=approval.confirmed_fact_hash,
            warning_disposition_ids=list(approval.warning_disposition_ids),
            template_id=approval.template_id,
            template_version=approval.template_version,
            rule_pack_version=approval.rule_pack_version,
            revoked_by_approval_id=approval.revoked_by_approval_id,
            created_at=approval.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_approval(row)

    async def list_for_target(
        self, user_id: str, target_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[Approval], str | None]:
        query = select(ApprovalRow).where(
            ApprovalRow.user_id == user_id, ApprovalRow.target_id == target_id
        )
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            query = query.where(
                (ApprovalRow.created_at < created_at)
                | ((ApprovalRow.created_at == created_at) & (ApprovalRow.id < last_id))
            )
        query = query.order_by(ApprovalRow.created_at.desc(), ApprovalRow.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_approval(row) for row in rows], next_cursor

    async def current_for_target(self, user_id: str, target_id: str) -> Approval | None:
        result = await self._session.execute(
            select(ApprovalRow)
            .where(
                ApprovalRow.user_id == user_id,
                ApprovalRow.target_id == target_id,
                ApprovalRow.revoked_by_approval_id.is_(None),
            )
            .order_by(ApprovalRow.created_at.desc(), ApprovalRow.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_approval(row) if row is not None else None

    async def revoke(self, user_id: str, approval_id: str, revoked_by_approval_id: str) -> None:
        """Point an approval at its successor.

        Guarded on ``revoked_by_approval_id IS NULL`` so a second revocation
        cannot rewrite which approval superseded this one: the first successor
        is the one that did.
        """
        await self._session.execute(
            update(ApprovalRow)
            .where(
                ApprovalRow.user_id == user_id,
                ApprovalRow.id == approval_id,
                ApprovalRow.revoked_by_approval_id.is_(None),
            )
            .values(revoked_by_approval_id=revoked_by_approval_id)
        )
        await self._session.flush()


class SqlFormExportRepository:
    """Implements ``FormExportRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, export: FormExport) -> FormExport:
        row = FormExportRow(
            id=export.id,
            user_id=export.user_id,
            matter_id=export.matter_id,
            generated_form_id=export.generated_form_id,
            approval_id=export.approval_id,
            export_format=export.export_format.value,
            artifact_hash=export.artifact_hash,
            artifact_key=export.artifact_key,
            watermarked=export.watermarked,
            registration_ready=export.registration_ready,
            manifest=dict(export.manifest),
            created_by=export.created_by,
            created_at=export.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_export(row)

    async def list_for_matter(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[FormExport], str | None]:
        query = select(FormExportRow).where(
            FormExportRow.user_id == user_id, FormExportRow.matter_id == matter_id
        )
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            query = query.where(
                (FormExportRow.created_at < created_at)
                | ((FormExportRow.created_at == created_at) & (FormExportRow.id < last_id))
            )
        query = query.order_by(FormExportRow.created_at.desc(), FormExportRow.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_export(row) for row in rows], next_cursor


class SqlRegistrationEventRepository:
    """Implements ``RegistrationEventRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, event: RegistrationEvent) -> RegistrationEvent:
        row = RegistrationEventRow(
            id=event.id,
            user_id=event.user_id,
            matter_id=event.matter_id,
            generated_form_id=event.generated_form_id,
            event_type=event.event_type.value,
            event_date=event.event_date,
            evidence_reference_ids=list(event.evidence_reference_ids),
            day_book_reference=event.day_book_reference,
            registry_office=event.registry_office,
            result_note=event.result_note,
            recorded_by=event.recorded_by,
            created_at=event.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_event(row)

    async def list_for_matter(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[RegistrationEvent], str | None]:
        query = select(RegistrationEventRow).where(
            RegistrationEventRow.user_id == user_id, RegistrationEventRow.matter_id == matter_id
        )
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            query = query.where(
                (RegistrationEventRow.created_at < created_at)
                | (
                    (RegistrationEventRow.created_at == created_at)
                    & (RegistrationEventRow.id < last_id)
                )
            )
        query = query.order_by(
            RegistrationEventRow.created_at.desc(), RegistrationEventRow.id.desc()
        ).limit(limit + 1)
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_event(row) for row in rows], next_cursor

    async def all_for_matter(self, user_id: str, matter_id: str) -> list[RegistrationEvent]:
        result = await self._session.execute(
            select(RegistrationEventRow)
            .where(
                RegistrationEventRow.user_id == user_id,
                RegistrationEventRow.matter_id == matter_id,
            )
            .order_by(RegistrationEventRow.event_date.asc(), RegistrationEventRow.id.asc())
        )
        return [_to_event(row) for row in result.scalars().all()]


__all__ = [
    "SqlApprovalRepository",
    "SqlFormExportRepository",
    "SqlRegistrationEventRepository",
]

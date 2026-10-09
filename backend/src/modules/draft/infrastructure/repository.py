"""SQLAlchemy repository for generated forms and their field bindings.

Every query filters on ``user_id`` first — that is the tenancy boundary in this
deployment, not a convenience predicate (plan §5.3 invariant 10).

There is no delete path. A superseded draft stays on file under its own
``form_version``, because §9.5 amends by opening a new version and §9.6 needs the
version an approval pinned itself to to remain readable afterwards.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import GeneratedFormState, UnresolvedReason
from src.modules.draft.contracts import FormScope
from src.modules.draft.domain.errors import GeneratedFormStaleError
from src.modules.draft.domain.models import GeneratedForm, GeneratedFormField
from src.modules.draft.infrastructure.orm import GeneratedFormFieldRow, GeneratedFormRow
from src.platform.pagination import Cursor, decode_cursor, encode_cursor


def _encode_cursor(created_at: datetime, record_id: str) -> str:
    return encode_cursor(Cursor(created_at=created_at, id=record_id))


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """The keyset position, or InvalidCursorError (400) for a forged or bad cursor."""
    decoded = decode_cursor(cursor)
    return (decoded.created_at, decoded.id) if decoded is not None else None


def _to_form(row: GeneratedFormRow) -> GeneratedForm:
    return GeneratedForm(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        template_id=row.template_id,
        template_version=row.template_version,
        form_version=row.form_version,
        state=GeneratedFormState(row.state),
        subtype_id=row.subtype_id,
        rule_pack_version=row.rule_pack_version,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        draft_artifact_hash=row.draft_artifact_hash,
        approved_artifact_hash=row.approved_artifact_hash,
        approval_id=row.approval_id,
        stale_reason=row.stale_reason,
        version=row.version,
        scope=FormScope(**row.scope) if row.scope else None,
        missing_causes=row.missing_causes or {},
        predecessor_form_id=row.predecessor_form_id,
    )


def _apply_form(row: GeneratedFormRow, form: GeneratedForm) -> None:
    """Copy the mutable half back onto the row.

    ``template_id``, ``template_version``, ``form_version``, ``subtype_id``, and
    ``rule_pack_version`` are deliberately absent: what a form was generated
    from never changes. A different template or a different rule pack is a
    different form version (§9.5).
    """
    row.state = form.state.value
    row.draft_artifact_hash = form.draft_artifact_hash
    row.approved_artifact_hash = form.approved_artifact_hash
    row.approval_id = form.approval_id
    row.stale_reason = form.stale_reason


def _to_field(row: GeneratedFormFieldRow) -> GeneratedFormField:
    return GeneratedFormField(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        generated_form_id=row.generated_form_id,
        field_id=row.field_id,
        critical=row.critical,
        required=row.required,
        order=row.order,
        fact_id=row.fact_id,
        fact_version=row.fact_version,
        evidence_reference_ids=tuple(row.evidence_reference_ids),
        rendered_value=row.rendered_value,
        unresolved_reason=(
            UnresolvedReason(row.unresolved_reason) if row.unresolved_reason else None
        ),
        transformation_id=row.transformation_id,
        review_decision_id=row.review_decision_id,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
    )


def _apply_field(row: GeneratedFormFieldRow, form_field: GeneratedFormField) -> None:
    row.fact_id = form_field.fact_id
    row.fact_version = form_field.fact_version
    row.evidence_reference_ids = list(form_field.evidence_reference_ids)
    row.rendered_value = form_field.rendered_value
    row.unresolved_reason = (
        form_field.unresolved_reason.value if form_field.unresolved_reason else None
    )
    row.transformation_id = form_field.transformation_id
    row.review_decision_id = form_field.review_decision_id
    row.reviewed_by = form_field.reviewed_by
    row.reviewed_at = form_field.reviewed_at


class SqlGeneratedFormRepository:
    """Implements ``GeneratedFormRepository`` over one request's AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Forms ────────────────────────────────────────────────────────────────

    async def create_form(self, form: GeneratedForm) -> GeneratedForm:
        row = GeneratedFormRow(
            id=form.id,
            user_id=form.user_id,
            matter_id=form.matter_id,
            template_id=form.template_id,
            template_version=form.template_version,
            form_version=form.form_version,
            state=form.state.value,
            subtype_id=form.subtype_id,
            draft_artifact_hash=form.draft_artifact_hash,
            approved_artifact_hash=form.approved_artifact_hash,
            approval_id=form.approval_id,
            stale_reason=form.stale_reason,
            rule_pack_version=form.rule_pack_version,
            created_by=form.created_by,
            created_at=form.created_at,
            updated_at=form.updated_at,
            version=form.version,
            scope=asdict(form.scope) if form.scope else None,
            missing_causes=form.missing_causes,
            predecessor_form_id=form.predecessor_form_id,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_form(row)

    async def get_form(self, user_id: str, form_id: str) -> GeneratedForm | None:
        row = await self._form_row(user_id, form_id)
        return _to_form(row) if row is not None else None

    async def _form_row(self, user_id: str, form_id: str) -> GeneratedFormRow | None:
        result = await self._session.execute(
            select(GeneratedFormRow)
            .execution_options(populate_existing=True)
            .where(GeneratedFormRow.user_id == user_id, GeneratedFormRow.id == form_id)
        )
        return result.scalar_one_or_none()

    async def list_forms(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[GeneratedForm], str | None]:
        query = select(GeneratedFormRow).where(
            GeneratedFormRow.user_id == user_id, GeneratedFormRow.matter_id == matter_id
        )
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            query = query.where(
                (GeneratedFormRow.created_at < created_at)
                | ((GeneratedFormRow.created_at == created_at) & (GeneratedFormRow.id < last_id))
            )
        query = query.order_by(
            GeneratedFormRow.created_at.desc(), GeneratedFormRow.id.desc()
        ).limit(limit + 1)
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_form(row) for row in rows], next_cursor

    async def next_form_version(self, user_id: str, matter_id: str, template_id: str) -> int:
        result = await self._session.execute(
            select(func.max(GeneratedFormRow.form_version)).where(
                GeneratedFormRow.user_id == user_id,
                GeneratedFormRow.matter_id == matter_id,
                GeneratedFormRow.template_id == template_id,
            )
        )
        return (result.scalar_one_or_none() or 0) + 1

    async def update_form(self, form: GeneratedForm, expected_version: int) -> GeneratedForm:
        result = await self._session.execute(
            update(GeneratedFormRow)
            .where(
                GeneratedFormRow.id == form.id,
                GeneratedFormRow.user_id == form.user_id,
                GeneratedFormRow.version == expected_version,
            )
            .values(version=expected_version + 1)
            .returning(GeneratedFormRow.id)
        )
        if result.scalar_one_or_none() is None:
            raise GeneratedFormStaleError(expectedVersion=expected_version)
        row = await self._form_row(form.user_id, form.id)
        if row is None:
            raise GeneratedFormStaleError(expectedVersion=expected_version)
        _apply_form(row, form)
        row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return _to_form(row)

    # ── Fields ───────────────────────────────────────────────────────────────

    async def create_fields(self, fields: list[GeneratedFormField]) -> list[GeneratedFormField]:
        rows = []
        for form_field in fields:
            row = GeneratedFormFieldRow(
                id=form_field.id,
                user_id=form_field.user_id,
                matter_id=form_field.matter_id,
                generated_form_id=form_field.generated_form_id,
                field_id=form_field.field_id,
                fact_id=form_field.fact_id,
                fact_version=form_field.fact_version,
                evidence_reference_ids=list(form_field.evidence_reference_ids),
                rendered_value=form_field.rendered_value,
                unresolved_reason=(
                    form_field.unresolved_reason.value if form_field.unresolved_reason else None
                ),
                transformation_id=form_field.transformation_id,
                review_decision_id=form_field.review_decision_id,
                reviewed_by=form_field.reviewed_by,
                reviewed_at=form_field.reviewed_at,
                critical=form_field.critical,
                required=form_field.required,
                order=form_field.order,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return [_to_field(row) for row in rows]

    async def list_fields(self, user_id: str, form_id: str) -> list[GeneratedFormField]:
        result = await self._session.execute(
            select(GeneratedFormFieldRow)
            .where(
                GeneratedFormFieldRow.user_id == user_id,
                GeneratedFormFieldRow.generated_form_id == form_id,
            )
            .order_by(GeneratedFormFieldRow.order.asc(), GeneratedFormFieldRow.field_id.asc())
        )
        return [_to_field(row) for row in result.scalars().all()]

    async def update_field(self, form_field: GeneratedFormField) -> GeneratedFormField:
        result = await self._session.execute(
            select(GeneratedFormFieldRow).where(
                GeneratedFormFieldRow.user_id == form_field.user_id,
                GeneratedFormFieldRow.id == form_field.id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise GeneratedFormStaleError(fieldId=form_field.field_id)
        _apply_field(row, form_field)
        await self._session.flush()
        return _to_field(row)

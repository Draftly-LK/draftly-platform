"""SQLAlchemy repositories for the matter module.

Every method takes ``user_id`` and filters on it first. A caller that "already
knows" the matter id still cannot read another user's row, which is the whole
point of putting the tenancy predicate in the repository rather than in a
service that might forget it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    AnswerStatus,
    AutomationScope,
    DispositionScope,
    DisputeStage,
    MatterFamily,
    MatterState,
    ParcelKind,
    PartyContext,
    SubtypeDecisionStatus,
    TitleStatus,
)
from src.modules.matter.domain.errors import MatterStaleError
from src.modules.matter.domain.models import (
    InstrumentLanguage,
    IntakeAnswer,
    Matter,
    MatterLifecycleStatus,
)
from src.modules.matter.infrastructure.orm import (
    IntakeAnswerRow,
    MatterClassificationRow,
    MatterRow,
)
from src.platform import ids
from src.platform.errors import ConflictError
from src.platform.pagination import Cursor, decode_cursor, encode_cursor


def _to_matter(row: MatterRow) -> Matter:
    return Matter(
        id=row.id,
        user_id=row.user_id,
        reference=row.reference,
        client_reference=row.client_reference,
        responsible_lawyer_id=row.responsible_lawyer_id,
        regime_id=row.regime_id,
        family_id=MatterFamily(row.family_id) if row.family_id else None,
        subtype_id=row.subtype_id,
        subtype_decision_status=SubtypeDecisionStatus(row.subtype_decision_status),
        legacy_matter_type=row.legacy_matter_type,
        lifecycle_status=MatterLifecycleStatus(row.lifecycle_status),
        rta_state=MatterState(row.rta_state),
        automation_scope=AutomationScope(row.automation_scope),
        title_status=TitleStatus(row.title_status),
        parcel_kind=ParcelKind(row.parcel_kind),
        disposition_scope=DispositionScope(row.disposition_scope),
        dispute_stage=DisputeStage(row.dispute_stage),
        instrument_language=InstrumentLanguage(row.instrument_language),
        declared_legal_basis=row.declared_legal_basis,
        local_authority_id=row.local_authority_id,
        active_checklist_snapshot_id=row.active_checklist_snapshot_id,
        party_contexts=frozenset(PartyContext(value) for value in row.party_contexts),
        activated_conditional_module_ids=frozenset(row.activated_conditional_module_ids),
        suppressed_conditional_module_ids=frozenset(row.suppressed_conditional_module_ids),
        automation_exclusion_reason_keys=tuple(row.automation_exclusion_reason_keys),
        created_at=row.created_at,
        updated_at=row.updated_at,
        version=row.version,
    )


def _apply(row: MatterRow, matter: Matter) -> None:
    row.reference = matter.reference
    row.client_reference = matter.client_reference
    row.responsible_lawyer_id = matter.responsible_lawyer_id
    row.regime_id = matter.regime_id
    row.family_id = matter.family_id.value if matter.family_id else None
    row.subtype_id = matter.subtype_id
    row.subtype_decision_status = matter.subtype_decision_status.value
    row.legacy_matter_type = matter.legacy_matter_type
    row.lifecycle_status = matter.lifecycle_status.value
    row.rta_state = matter.rta_state.value
    row.automation_scope = matter.automation_scope.value
    row.title_status = matter.title_status.value
    row.parcel_kind = matter.parcel_kind.value
    row.disposition_scope = matter.disposition_scope.value
    row.dispute_stage = matter.dispute_stage.value
    row.instrument_language = matter.instrument_language.value
    row.declared_legal_basis = matter.declared_legal_basis
    row.local_authority_id = matter.local_authority_id
    row.active_checklist_snapshot_id = matter.active_checklist_snapshot_id
    row.party_contexts = sorted(c.value for c in matter.party_contexts)
    row.activated_conditional_module_ids = sorted(matter.activated_conditional_module_ids)
    row.suppressed_conditional_module_ids = sorted(matter.suppressed_conditional_module_ids)
    row.automation_exclusion_reason_keys = list(matter.automation_exclusion_reason_keys)


def _encode_cursor(created_at: datetime, record_id: str) -> str:
    return encode_cursor(Cursor(created_at=created_at, id=record_id))


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """The keyset position, or InvalidCursorError (400) for a forged or bad cursor."""
    decoded = decode_cursor(cursor)
    return (decoded.created_at, decoded.id) if decoded is not None else None


class SqlMatterRepository:
    """Implements ``MatterRepository`` over the request's AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, matter_id: str) -> Matter | None:
        row = await self._row(user_id, matter_id)
        return _to_matter(row) if row is not None else None

    async def _row(self, user_id: str, matter_id: str) -> MatterRow | None:
        result = await self._session.execute(
            select(MatterRow).where(MatterRow.user_id == user_id, MatterRow.id == matter_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[Matter], str | None]:
        query = select(MatterRow).where(MatterRow.user_id == user_id)
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            # Keyset pagination: offset double-counts under concurrent writes
            # (api-conventions §2).
            query = query.where(
                (MatterRow.created_at < created_at)
                | ((MatterRow.created_at == created_at) & (MatterRow.id < last_id))
            )
        query = query.order_by(MatterRow.created_at.desc(), MatterRow.id.desc()).limit(limit + 1)
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)
        return [_to_matter(row) for row in rows], next_cursor

    async def create(self, matter: Matter) -> Matter:
        row = MatterRow(
            id=matter.id,
            user_id=matter.user_id,
            created_at=matter.created_at,
            updated_at=matter.updated_at,
            version=matter.version,
        )
        _apply(row, matter)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # uq_matters_user_reference: one reference per user. Reported as a
            # conflict so the caller can say which field clashed, rather than
            # escaping as a 500 — an unhandled error also loses the CORS
            # headers, which makes a duplicate reference look like a network
            # fault in the browser.
            if _is_duplicate_reference(exc):
                raise ConflictError(
                    f"Matter reference '{matter.reference}' is already used."
                ) from exc
            raise
        return _to_matter(row)

    async def update(self, matter: Matter, expected_version: int) -> Matter:
        result = await self._session.execute(
            update(MatterRow)
            .where(
                MatterRow.id == matter.id,
                MatterRow.user_id == matter.user_id,
                MatterRow.version == expected_version,
            )
            .values(version=expected_version + 1)
            .returning(MatterRow.id)
        )
        if result.scalar_one_or_none() is None:
            raise MatterStaleError(expected_version=expected_version)
        row = await self._row(matter.user_id, matter.id)
        if row is None:
            raise MatterStaleError(expected_version=expected_version)
        _apply(row, matter)
        row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return _to_matter(row)

    async def next_classification_version(self, matter_id: str) -> int:
        result = await self._session.execute(
            select(MatterClassificationRow.version)
            .where(MatterClassificationRow.matter_id == matter_id)
            .order_by(MatterClassificationRow.version.desc())
            .limit(1)
        )
        current = result.scalar_one_or_none()
        return (current or 0) + 1

    async def append_classification(
        self,
        matter: Matter,
        *,
        version: int,
        rule_pack_version: str,
        changed_by: str,
        reason: str | None,
    ) -> None:
        self._session.add(
            MatterClassificationRow(
                id=ids.new_id("mcl"),
                user_id=matter.user_id,
                matter_id=matter.id,
                version=version,
                regime_id=matter.regime_id,
                family_id=matter.family_id.value if matter.family_id else None,
                subtype_id=matter.subtype_id,
                subtype_decision_status=matter.subtype_decision_status.value,
                title_status=matter.title_status.value,
                parcel_kind=matter.parcel_kind.value,
                disposition_scope=matter.disposition_scope.value,
                property_characteristics={
                    "partyContexts": sorted(c.value for c in matter.party_contexts),
                    "conditionalModules": sorted(matter.activated_conditional_module_ids),
                    "localAuthorityId": matter.local_authority_id,
                },
                execution_circumstances={"instrumentLanguage": matter.instrument_language.value},
                rule_pack_version=rule_pack_version,
                changed_by=changed_by,
                reason=reason,
            )
        )
        await self._session.flush()


def _to_answer(row: IntakeAnswerRow) -> IntakeAnswer:
    return IntakeAnswer(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        question_definition_id=row.question_definition_id,
        value=row.value,
        status=AnswerStatus(row.status),
        inferred_from_fact_ids=tuple(row.inferred_from_fact_ids),
        answered_by=row.answered_by,
        answer_reason=row.answer_reason,
        supersedes_id=row.supersedes_id,
        created_at=row.created_at,
    )


class SqlIntakeAnswerRepository:
    """Implements ``IntakeAnswerRepository``. Answers are append-only."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, user_id: str, matter_id: str) -> list[IntakeAnswer]:
        result = await self._session.execute(
            select(IntakeAnswerRow)
            .where(IntakeAnswerRow.user_id == user_id, IntakeAnswerRow.matter_id == matter_id)
            .order_by(IntakeAnswerRow.created_at.asc(), IntakeAnswerRow.id.asc())
        )
        return [_to_answer(row) for row in result.scalars().all()]

    async def list_live(self, user_id: str, matter_id: str) -> list[IntakeAnswer]:
        result = await self._session.execute(
            select(IntakeAnswerRow)
            .where(
                IntakeAnswerRow.user_id == user_id,
                IntakeAnswerRow.matter_id == matter_id,
                IntakeAnswerRow.status != AnswerStatus.SUPERSEDED.value,
            )
            .order_by(IntakeAnswerRow.created_at.asc(), IntakeAnswerRow.id.asc())
        )
        return [_to_answer(row) for row in result.scalars().all()]

    async def supersede(self, user_id: str, matter_id: str, question_id: str) -> str | None:
        result = await self._session.execute(
            select(IntakeAnswerRow)
            .where(
                IntakeAnswerRow.user_id == user_id,
                IntakeAnswerRow.matter_id == matter_id,
                IntakeAnswerRow.question_definition_id == question_id,
                IntakeAnswerRow.status != AnswerStatus.SUPERSEDED.value,
            )
            .order_by(IntakeAnswerRow.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = AnswerStatus.SUPERSEDED.value
        await self._session.flush()
        return row.id

    async def create(self, answer: IntakeAnswer) -> IntakeAnswer:
        row = IntakeAnswerRow(
            id=answer.id,
            user_id=answer.user_id,
            matter_id=answer.matter_id,
            question_definition_id=answer.question_definition_id,
            value=answer.value,
            status=answer.status.value,
            inferred_from_fact_ids=list(answer.inferred_from_fact_ids),
            answered_by=answer.answered_by,
            answer_reason=answer.answer_reason,
            supersedes_id=answer.supersedes_id,
            lawyer_confirmed=answer.status is AnswerStatus.LAWYER_CONFIRMED,
            created_at=answer.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_answer(row)


def _is_duplicate_reference(exc: IntegrityError) -> bool:
    """True when the violated constraint is the per-user reference index."""
    return "uq_matters_user_reference" in str(getattr(exc, "orig", exc))

"""SQLAlchemy repository for check results and legal issues.

Every query filters on ``user_id`` first — that is the tenancy boundary in this
deployment, not a convenience predicate (plan §5.3 invariant 10). Check results
are inserted and never updated; issues are updated only through the optimistic
`update_issue`, so two lawyers deciding the same issue cannot silently overwrite
each other.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.check.domain.errors import LegalIssueStaleError
from src.modules.check.domain.models import CheckResult, FactVersionPin, LegalIssue
from src.modules.check.infrastructure.orm import CrossDocumentCheckRow, LegalIssueRow
from src.modules.content_governance.contracts import (
    BlockerKind,
    CheckOutcome,
    IssueSeverity,
    IssueState,
)
from src.platform.pagination import Cursor, decode_cursor, encode_cursor


def _encode_cursor(created_at: datetime, record_id: str) -> str:
    return encode_cursor(Cursor(created_at=created_at, id=record_id))


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """The keyset position, or InvalidCursorError (400) for a forged or bad cursor."""
    decoded = decode_cursor(cursor)
    return (decoded.created_at, decoded.id) if decoded is not None else None


def _to_result(row: CrossDocumentCheckRow) -> CheckResult:
    return CheckResult(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        transaction_id=row.transaction_id,
        subject_id=row.subject_id,
        association_version=row.association_version,
        check_definition_id=row.check_definition_id,
        check_definition_version=row.check_definition_version,
        run_id=row.run_id,
        outcome=CheckOutcome(row.outcome),
        default_severity=IssueSeverity(row.default_severity),
        explanation_key=row.explanation_key,
        created_at=row.created_at,
        input_fact_versions=tuple(
            FactVersionPin(fact_id=str(pin["factId"]), version=int(str(pin["version"])))
            for pin in row.input_fact_versions
        ),
        evidence_reference_ids=tuple(row.evidence_reference_ids),
        requires_human_conclusion=row.requires_human_conclusion,
    )


def _to_issue(row: LegalIssueRow) -> LegalIssue:
    return LegalIssue(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        transaction_id=row.transaction_id,
        subject_id=row.subject_id,
        association_version=row.association_version,
        issue_type_id=row.issue_type_id,
        severity=IssueSeverity(row.severity),
        blocker_kind=BlockerKind(row.blocker_kind),
        state=IssueState(row.state),
        summary_key=row.summary_key,
        created_at=row.created_at,
        updated_at=row.updated_at,
        check_id=row.check_id,
        source_record_ids=tuple(row.source_record_ids),
        evidence_reference_ids=tuple(row.evidence_reference_ids),
        assigned_to=row.assigned_to,
        resolution_decision_id=row.resolution_decision_id,
        resolution_reason=row.resolution_reason,
        version=row.version,
    )


def _apply_issue(row: LegalIssueRow, issue: LegalIssue) -> None:
    """Copy the mutable half back onto the row.

    ``issue_type_id``, ``check_id``, and ``created_at`` are deliberately absent:
    what an issue *is* never changes, only how it has been disposed of.
    """
    row.severity = issue.severity.value
    row.blocker_kind = issue.blocker_kind.value
    row.state = issue.state.value
    row.summary_key = issue.summary_key
    row.evidence_reference_ids = list(issue.evidence_reference_ids)
    row.assigned_to = issue.assigned_to
    row.resolution_decision_id = issue.resolution_decision_id
    row.resolution_reason = issue.resolution_reason


class SqlCheckRepository:
    """Implements ``CheckRepository`` over one request's AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Check results (append-only) ──────────────────────────────────────────

    async def stale_input_results(self, user_id: str, matter_id: str) -> tuple[CheckResult, ...]:
        rows = (
            await self._session.execute(
                select(CrossDocumentCheckRow)
                .where(
                    CrossDocumentCheckRow.user_id == user_id,
                    CrossDocumentCheckRow.matter_id == matter_id,
                )
                .order_by(CrossDocumentCheckRow.created_at.desc(), CrossDocumentCheckRow.id.desc())
            )
        ).scalars()
        seen: set[tuple[str, str | None, str | None]] = set()
        result: list[CheckResult] = []
        for row in rows:
            key = (row.check_definition_id, row.transaction_id, row.subject_id)
            if key in seen:
                continue
            seen.add(key)
            if row.explanation_key == "rta.check.input_changed":
                result.append(_to_result(row))
        return tuple(result)

    async def create_results(self, results: list[CheckResult]) -> list[CheckResult]:
        rows = []
        for result in results:
            row = CrossDocumentCheckRow(
                id=result.id,
                user_id=result.user_id,
                matter_id=result.matter_id,
                transaction_id=result.transaction_id,
                subject_id=result.subject_id,
                association_version=result.association_version,
                check_definition_id=result.check_definition_id,
                check_definition_version=result.check_definition_version,
                run_id=result.run_id,
                outcome=result.outcome.value,
                default_severity=result.default_severity.value,
                explanation_key=result.explanation_key,
                input_fact_versions=[
                    {"factId": pin.fact_id, "version": pin.version}
                    for pin in result.input_fact_versions
                ],
                evidence_reference_ids=list(result.evidence_reference_ids),
                requires_human_conclusion=result.requires_human_conclusion,
                created_at=result.created_at,
            )
            self._session.add(row)
            rows.append(row)
        await self._session.flush()
        return [_to_result(row) for row in rows]

    async def list_results(
        self, user_id: str, matter_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[CheckResult], str | None]:
        query = select(CrossDocumentCheckRow).where(
            CrossDocumentCheckRow.user_id == user_id,
            CrossDocumentCheckRow.matter_id == matter_id,
        )
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            query = query.where(
                (CrossDocumentCheckRow.created_at < created_at)
                | (
                    (CrossDocumentCheckRow.created_at == created_at)
                    & (CrossDocumentCheckRow.id < last_id)
                )
            )
        query = query.order_by(
            CrossDocumentCheckRow.created_at.desc(), CrossDocumentCheckRow.id.desc()
        ).limit(limit + 1)
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_result(row) for row in rows], next_cursor

    # ── Legal issues ─────────────────────────────────────────────────────────

    async def create_issue(self, issue: LegalIssue) -> LegalIssue:
        row = LegalIssueRow(
            id=issue.id,
            user_id=issue.user_id,
            matter_id=issue.matter_id,
            transaction_id=issue.transaction_id,
            subject_id=issue.subject_id,
            association_version=issue.association_version,
            check_id=issue.check_id,
            issue_type_id=issue.issue_type_id,
            severity=issue.severity.value,
            blocker_kind=issue.blocker_kind.value,
            state=issue.state.value,
            summary_key=issue.summary_key,
            source_record_ids=list(issue.source_record_ids),
            evidence_reference_ids=list(issue.evidence_reference_ids),
            assigned_to=issue.assigned_to,
            resolution_decision_id=issue.resolution_decision_id,
            resolution_reason=issue.resolution_reason,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            version=issue.version,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_issue(row)

    async def get_issue(self, user_id: str, issue_id: str) -> LegalIssue | None:
        row = await self._issue_row(user_id, issue_id)
        return _to_issue(row) if row is not None else None

    async def _issue_row(self, user_id: str, issue_id: str) -> LegalIssueRow | None:
        result = await self._session.execute(
            select(LegalIssueRow).where(
                LegalIssueRow.user_id == user_id, LegalIssueRow.id == issue_id
            )
        )
        return result.scalar_one_or_none()

    async def list_issues(
        self,
        user_id: str,
        matter_id: str,
        *,
        severity: IssueSeverity | None,
        state: IssueState | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[LegalIssue], str | None]:
        query: Select[tuple[LegalIssueRow]] = select(LegalIssueRow).where(
            LegalIssueRow.user_id == user_id, LegalIssueRow.matter_id == matter_id
        )
        if severity is not None:
            query = query.where(LegalIssueRow.severity == severity.value)
        if state is not None:
            query = query.where(LegalIssueRow.state == state.value)
        decoded = _decode_cursor(cursor) if cursor else None
        if decoded is not None:
            created_at, last_id = decoded
            query = query.where(
                (LegalIssueRow.created_at < created_at)
                | ((LegalIssueRow.created_at == created_at) & (LegalIssueRow.id < last_id))
            )
        query = query.order_by(LegalIssueRow.created_at.desc(), LegalIssueRow.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.execute(query)).scalars().all())
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id)
        return [_to_issue(row) for row in rows], next_cursor

    async def list_all_issues(self, user_id: str, matter_id: str) -> list[LegalIssue]:
        result = await self._session.execute(
            select(LegalIssueRow)
            .where(LegalIssueRow.user_id == user_id, LegalIssueRow.matter_id == matter_id)
            .order_by(LegalIssueRow.created_at.asc(), LegalIssueRow.id.asc())
        )
        return [_to_issue(row) for row in result.scalars().all()]

    async def update_issue(self, issue: LegalIssue, expected_version: int) -> LegalIssue:
        result = await self._session.execute(
            update(LegalIssueRow)
            .where(
                LegalIssueRow.id == issue.id,
                LegalIssueRow.user_id == issue.user_id,
                LegalIssueRow.version == expected_version,
            )
            .values(version=expected_version + 1)
            .returning(LegalIssueRow.id)
        )
        if result.scalar_one_or_none() is None:
            raise LegalIssueStaleError(expectedVersion=expected_version)
        row = await self._issue_row(issue.user_id, issue.id)
        if row is None:
            raise LegalIssueStaleError(expectedVersion=expected_version)
        _apply_issue(row, issue)
        row.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return _to_issue(row)

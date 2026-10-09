"""Check-owned successor evaluations for invalidated fact inputs."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.check.infrastructure.orm import CrossDocumentCheckRow, LegalIssueRow
from src.platform.ids import new_id

STALE_INPUT_KEY = "rta.check.input_changed"


class SqlCheckInputInvalidation:
    def __init__(self, session: AsyncSession, audit: AuditPort) -> None:
        self._session, self._audit = session, audit

    async def invalidate_inputs(
        self,
        *,
        user_id: str,
        matter_id: str,
        fact_ids: tuple[str, ...],
        actor_id: str,
        correlation_id: str,
    ) -> None:
        rows = list(
            (
                await self._session.execute(
                    select(CrossDocumentCheckRow)
                    .where(
                        CrossDocumentCheckRow.user_id == user_id,
                        CrossDocumentCheckRow.matter_id == matter_id,
                    )
                    .order_by(
                        CrossDocumentCheckRow.created_at.desc(), CrossDocumentCheckRow.id.desc()
                    )
                )
            ).scalars()
        )
        seen: set[str] = set()
        changed: set[str] = set()
        for row in rows:
            if row.check_definition_id in seen:
                continue
            seen.add(row.check_definition_id)
            if row.explanation_key == STALE_INPUT_KEY or not any(
                p["factId"] in fact_ids for p in row.input_fact_versions
            ):
                continue
            changed.add(row.id)
            successor = CrossDocumentCheckRow(
                id=new_id("chk"),
                user_id=user_id,
                matter_id=matter_id,
                check_definition_id=row.check_definition_id,
                check_definition_version=row.check_definition_version,
                run_id=new_id("run"),
                outcome="INCONCLUSIVE",
                default_severity=row.default_severity,
                explanation_key=STALE_INPUT_KEY,
                input_fact_versions=row.input_fact_versions,
                evidence_reference_ids=row.evidence_reference_ids,
                requires_human_conclusion=True,
                created_at=datetime.now(UTC),
            )
            self._session.add(successor)
            await self._audit.record(
                AuditEventInput(
                    user_id=user_id,
                    matter_id=matter_id,
                    actor=actor_id,
                    action="rta.check.input-stale",
                    target_type="check",
                    target_id=successor.id,
                    before_ref=row.id,
                    after_ref="INCONCLUSIVE",
                    correlation_id=correlation_id,
                )
            )
        issues = (
            await self._session.execute(
                select(LegalIssueRow).where(
                    LegalIssueRow.user_id == user_id,
                    LegalIssueRow.matter_id == matter_id,
                    LegalIssueRow.check_id.in_(changed),
                    LegalIssueRow.state.in_(("RESOLVED", "ACCEPTED_RISK", "FALSE_POSITIVE")),
                )
            )
        ).scalars()
        for issue in issues:
            before = issue.state
            issue.state = "OPEN"
            issue.version += 1
            await self._audit.record(
                AuditEventInput(
                    user_id=user_id,
                    matter_id=matter_id,
                    actor=actor_id,
                    action="rta.issue.reopened",
                    target_type="legal-issue",
                    target_id=issue.id,
                    before_ref=before,
                    after_ref="OPEN",
                    correlation_id=correlation_id,
                )
            )
        await self._session.flush()

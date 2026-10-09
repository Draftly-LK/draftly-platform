"""Check application service — run the checks, raise the issues, record the gates.

Two decisions in this file are product decisions, not implementation details.

**A rerun appends.** Every run mints a new ``run_id`` and inserts a fresh result
per check, pinned to the fact versions it actually read. Nothing edits an
earlier result, so "what did we know when we concluded that?" stays answerable
after a fact is corrected (§7.1, §12.2).

**A machine never closes a legal issue.** A rerun may create an issue, and it
may reopen one that new contrary evidence contradicts, but a check that now
passes leaves an open issue exactly where the lawyer left it. §10.6 puts every
closing disposition behind a recorded human decision, and "the rerun went green"
is not one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from src.modules.audit.domain.models import AuditAction, AuditTargetType
from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.check.application.currentness import read_current_transaction, subject_is_detached
from src.modules.check.contracts import IssueGateSummary
from src.modules.check.domain.errors import LegalIssueNotFoundError
from src.modules.check.domain.models import CheckResult, LegalIssue
from src.modules.check.domain.policies import (
    blocks_approval,
    blocks_draft_generation,
    blocks_registration_ready_export,
    guard_issue_decision,
    open_blocking_issue_ids,
    open_statutory_blocker_ids,
    reopen_state,
    reopens_on_new_evidence,
)
from src.modules.check.domain.runners import CheckEvaluation, CheckInput, run_all
from src.modules.check.ports import CheckRepository
from src.modules.content_governance.contracts import (
    CRITICAL_FACT_TYPE_IDS,
    IssueSeverity,
    IssueState,
    PartyContext,
    RtaWorkflowRole,
)
from src.modules.matter.contracts import MatterMutationLockPort, MatterScopeReadPort
from src.modules.verification.contracts import ConfirmedFactReadPort, FactTierSummary
from src.platform import ids
from src.platform.errors import DomainRuleError, NotFoundError, PreconditionFailedError

log = structlog.get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class CheckRunResult:
    """One run of the deterministic checks, and what it changed."""

    run_id: str
    results: tuple[CheckResult, ...]
    evaluations: tuple[CheckEvaluation, ...]
    #: Issues this run created or reopened. An issue an earlier run raised and
    #: nobody has disposed of is not repeated here; it is still in the gates.
    raised_issues: tuple[LegalIssue, ...]
    gates: IssueGateSummary


class CheckService:
    """Owns check results, the issues they raise, and the three §7.3 gates."""

    def __init__(
        self,
        *,
        repository: CheckRepository,
        facts: ConfirmedFactReadPort,
        audit: AuditPort,
        clock: Callable[[], datetime] = _utc_now,
        matter_lock: MatterMutationLockPort | None = None,
        scopes: MatterScopeReadPort | None = None,
    ) -> None:
        self._repo = repository
        self._facts = facts
        self._audit = audit
        # One run is one moment: the clock is read once per run and shared by
        # every result, so a slow run cannot look like several. Injectable so a
        # deadline test does not depend on the day it is run.
        self._clock = clock
        self._matter_lock = matter_lock
        self._scopes = scopes

    # ── Running ──────────────────────────────────────────────────────────────

    async def run_checks(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        subtype_id: str | None = None,
        party_contexts: frozenset[PartyContext] = frozenset(),
        search_currency_max_age_days: int | None = None,
        transaction_id: str | None = None,
        subject_id: str | None = None,
        association_version: int | None = None,
    ) -> CheckRunResult:
        """Run every implemented check against the current confirmed fact tier.

        The rule pack version and the input fact versions are pinned into each
        result at this moment, so a later rule change or fact correction never
        retroactively reinterprets a conclusion that has already been shown to a
        lawyer (§7.1).
        """
        if self._matter_lock:
            await self._matter_lock.lock(user_id, matter_id)
        if self._scopes is not None:
            if transaction_id is None or association_version is None:
                raise DomainRuleError(
                    "Select and review a transaction scope before running checks."
                )
            transaction = await self._scopes.transaction(user_id, matter_id, transaction_id)
            if transaction is None:
                raise NotFoundError()
            if transaction.version != association_version:
                raise PreconditionFailedError(currentVersion=transaction.version)
            if subject_id is not None:
                subject = await self._scopes.subject(user_id, matter_id, subject_id)
                if subject is None:
                    raise NotFoundError()
                members = {
                    *transaction.parcel_subject_ids,
                    *(role.subject_id for role in transaction.party_roles),
                }
                if subject_id not in members:
                    raise DomainRuleError("The subject is not associated with this transaction.")
        elif transaction_id is not None:
            raise DomainRuleError("Scope validation is unavailable.")
        now = self._clock()
        summary = await self._facts.summarise(user_id, matter_id)
        if transaction_id is not None:
            selected = tuple(
                value
                for value in summary.scoped_confirmed
                if value.transaction_id == transaction_id and value.subject_id == subject_id
            )
            # Duplicate types are withheld, never selected by recency.
            confirmed = {
                value.fact_type_id: value
                for value in selected
                if sum(other.fact_type_id == value.fact_type_id for other in selected) == 1
            }
            conflicts = tuple(
                kind
                for transaction, subject, kind in summary.scoped_conflicts
                if (transaction, subject) == (transaction_id, subject_id)
            )
            summary = FactTierSummary(
                confirmed=confirmed,
                scoped_confirmed=selected,
                unconfirmed_critical_fact_type_ids=tuple(
                    sorted(CRITICAL_FACT_TYPE_IDS - confirmed.keys())
                ),
                conflicted_fact_type_ids=conflicts,
                has_current_search_evidence="rta.title.register_search_datetime" in confirmed,
            )
        evaluations = run_all(
            CheckInput(
                matter_id=matter_id,
                facts=summary,
                evaluated_at=now,
                subtype_id=subtype_id,
                party_contexts=party_contexts,
                search_currency_max_age_days=search_currency_max_age_days,
            )
        )

        run_id = ids.new_id(ids.PROCESSING_RUN)
        results = await self._repo.create_results(
            [
                CheckResult(
                    id=ids.new_id(ids.CROSS_DOCUMENT_CHECK),
                    user_id=user_id,
                    matter_id=matter_id,
                    check_definition_id=evaluation.check_definition_id,
                    check_definition_version=evaluation.check_definition_version,
                    run_id=run_id,
                    transaction_id=transaction_id,
                    subject_id=subject_id,
                    association_version=association_version,
                    outcome=evaluation.outcome,
                    default_severity=evaluation.default_severity,
                    explanation_key=evaluation.explanation_key,
                    created_at=now,
                    input_fact_versions=evaluation.input_fact_versions,
                    evidence_reference_ids=evaluation.evidence_reference_ids,
                    requires_human_conclusion=evaluation.requires_human_conclusion,
                )
                for evaluation in evaluations
            ]
        )
        await self._audit.record(
            AuditEventInput(
                user_id=user_id,
                matter_id=matter_id,
                actor=actor_id,
                action=AuditAction.RTA_CHECK_RUN.value,
                target_type=AuditTargetType.CHECK.value,
                target_id=run_id,
                after_ref=_run_fingerprint(evaluations),
                correlation_id=correlation_id,
            )
        )

        raised = await self._reconcile_issues(
            user_id=user_id,
            matter_id=matter_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            now=now,
            evaluations=evaluations,
            result_ids={result.check_definition_id: result.id for result in results},
            transaction_id=transaction_id,
            subject_id=subject_id,
            association_version=association_version,
        )
        return CheckRunResult(
            run_id=run_id,
            results=tuple(results),
            evaluations=evaluations,
            raised_issues=raised,
            gates=await self.gates(user_id, matter_id),
        )

    async def _reconcile_issues(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        now: datetime,
        evaluations: tuple[CheckEvaluation, ...],
        result_ids: dict[str, str],
        transaction_id: str | None,
        subject_id: str | None,
        association_version: int | None,
    ) -> tuple[LegalIssue, ...]:
        """Create an issue for each failing check, or reopen one it contradicts."""
        existing = _latest_by_type(
            [
                issue
                for issue in await self._repo.list_all_issues(user_id, matter_id)
                if (issue.transaction_id, issue.subject_id, issue.association_version)
                == (transaction_id, subject_id, association_version)
            ]
        )
        raised: list[LegalIssue] = []
        for evaluation in evaluations:
            if not evaluation.raises_issue:
                continue
            current = existing.get(evaluation.issue_type_id)
            if current is None:
                raised.append(
                    await self._create_issue(
                        user_id=user_id,
                        matter_id=matter_id,
                        actor_id=actor_id,
                        correlation_id=correlation_id,
                        now=now,
                        evaluation=evaluation,
                        check_id=result_ids.get(evaluation.check_definition_id),
                        transaction_id=transaction_id,
                        subject_id=subject_id,
                        association_version=association_version,
                    )
                )
                continue
            if reopens_on_new_evidence(current, evaluation.evidence_reference_ids):
                raised.append(
                    await self._reopen_issue(
                        issue=current,
                        actor_id=actor_id,
                        correlation_id=correlation_id,
                        evaluation=evaluation,
                    )
                )
            # An issue that is still open needs no write: the fresh result row
            # already carries this run's evidence, and rewriting the issue would
            # churn a record a lawyer may be part-way through triaging.
        return tuple(raised)

    async def _create_issue(
        self,
        *,
        user_id: str,
        matter_id: str,
        actor_id: str,
        correlation_id: str,
        now: datetime,
        evaluation: CheckEvaluation,
        check_id: str | None,
        transaction_id: str | None,
        subject_id: str | None,
        association_version: int | None,
    ) -> LegalIssue:
        issue = await self._repo.create_issue(
            LegalIssue(
                id=ids.new_id(ids.LEGAL_ISSUE),
                user_id=user_id,
                matter_id=matter_id,
                issue_type_id=evaluation.issue_type_id,
                # §10.6: a check failure opens at the *default* severity and
                # blocker kind. Only a recorded human decision moves either.
                severity=evaluation.default_severity,
                blocker_kind=evaluation.blocker_kind,
                state=IssueState.OPEN,
                summary_key=f"{evaluation.issue_type_id}.summary",
                created_at=now,
                updated_at=now,
                check_id=check_id,
                transaction_id=transaction_id,
                subject_id=subject_id,
                association_version=association_version,
                source_record_ids=evaluation.source_record_ids,
                evidence_reference_ids=evaluation.evidence_reference_ids,
            )
        )
        await self._record_issue_event(
            issue=issue,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_ISSUE_CREATED,
            after_ref=f"{issue.state.value}@{evaluation.explanation_key}",
        )
        return issue

    async def _reopen_issue(
        self,
        *,
        issue: LegalIssue,
        actor_id: str,
        correlation_id: str,
        evaluation: CheckEvaluation,
    ) -> LegalIssue:
        """Reopen a closed issue that a rerun's new evidence contradicts (§10.6).

        The previous disposition is not erased — it stays in the audit trail, and
        the reason names the run that reopened it.
        """
        previous = issue.state
        issue.state = reopen_state(issue)
        issue.evidence_reference_ids = _merge(
            issue.evidence_reference_ids, evaluation.evidence_reference_ids
        )
        saved = await self._repo.update_issue(issue, issue.version)
        await self._record_issue_event(
            issue=saved,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_ISSUE_DECIDED,
            before_ref=previous.value,
            after_ref=saved.state.value,
            reason="Reopened: a rerun of the deterministic checks produced new contrary evidence.",
        )
        return saved

    # ── Reads ────────────────────────────────────────────────────────────────

    async def list_results(
        self, *, user_id: str, matter_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[CheckResult], str | None]:
        return await self._repo.list_results(user_id, matter_id, limit=limit, cursor=cursor)

    async def list_issues(
        self,
        *,
        user_id: str,
        matter_id: str,
        severity: IssueSeverity | None = None,
        state: IssueState | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[LegalIssue], str | None]:
        return await self._repo.list_issues(
            user_id, matter_id, severity=severity, state=state, limit=limit, cursor=cursor
        )

    async def get_issue(self, *, user_id: str, matter_id: str, issue_id: str) -> LegalIssue:
        issue = await self._repo.get_issue(user_id, issue_id)
        if issue is None or issue.matter_id != matter_id:
            raise LegalIssueNotFoundError()
        return issue

    async def gates(self, user_id: str, matter_id: str) -> IssueGateSummary:
        """Implements `check.contracts.IssueGatePort` for draft and approval."""
        if self._matter_lock:
            await self._matter_lock.lock(user_id, matter_id)
        issues = await self._repo.list_all_issues(user_id, matter_id)
        stale_results = await self._repo.stale_input_results(user_id, matter_id)
        transactions = {}
        stale_ids = []
        for result in stale_results:
            if result.transaction_id is not None and result.transaction_id not in transactions:
                transactions[result.transaction_id] = await read_current_transaction(
                    self._scopes, user_id, matter_id, result.transaction_id
                )
            transaction = transactions.get(result.transaction_id) if result.transaction_id else None
            if not subject_is_detached(result, transaction):
                stale_ids.append(result.id)
        stale = tuple(stale_ids)
        return IssueGateSummary(
            blocks_draft_generation=bool(stale) or blocks_draft_generation(issues),
            blocks_approval=bool(stale) or blocks_approval(issues),
            blocks_registration_ready_export=bool(stale)
            or blocks_registration_ready_export(issues),
            open_statutory_blocker_ids=open_statutory_blocker_ids(issues),
            open_blocking_issue_ids=open_blocking_issue_ids(issues),
            stale_check_ids=stale,
        )

    # ── Decisions ────────────────────────────────────────────────────────────

    async def decide_issue(
        self,
        *,
        user_id: str,
        matter_id: str,
        issue_id: str,
        actor_id: str,
        actor_workflow_role: RtaWorkflowRole,
        correlation_id: str,
        expected_version: int,
        target_state: IssueState,
        reason: str | None = None,
        new_evidence_reference_ids: tuple[str, ...] = (),
        assigned_to: str | None = None,
    ) -> LegalIssue:
        """Record one lawyer's disposition of one issue.

        The guard runs before anything is written, so a refused disposition —
        above all accepting risk on a statutory blocker — leaves no trace of a
        half-applied change.
        """
        if self._matter_lock:
            await self._matter_lock.lock(user_id, matter_id)
        issue = await self.get_issue(user_id=user_id, matter_id=matter_id, issue_id=issue_id)
        guard_issue_decision(
            issue,
            target_state,
            actor_workflow_role,
            reason,
            new_evidence_reference_ids=new_evidence_reference_ids,
        )
        previous = issue.state
        decision_id = ids.new_id(ids.REVIEW_DECISION)
        issue.state = target_state
        issue.evidence_reference_ids = _merge(
            issue.evidence_reference_ids, new_evidence_reference_ids
        )
        if assigned_to is not None:
            issue.assigned_to = assigned_to
        if reason is not None:
            issue.resolution_reason = reason
        issue.resolution_decision_id = decision_id
        saved = await self._repo.update_issue(issue, expected_version)
        await self._record_issue_event(
            issue=saved,
            actor_id=actor_id,
            correlation_id=correlation_id,
            action=AuditAction.RTA_ISSUE_DECIDED,
            before_ref=previous.value,
            # The decision id has no row of its own in this module: the audit
            # event *is* the record of the decision, and this links the two.
            after_ref=f"{saved.state.value}@{decision_id}",
            reason=reason,
        )
        return saved

    # ── Audit ────────────────────────────────────────────────────────────────

    async def _record_issue_event(
        self,
        *,
        issue: LegalIssue,
        actor_id: str,
        correlation_id: str,
        action: AuditAction,
        before_ref: str | None = None,
        after_ref: str | None = None,
        reason: str | None = None,
    ) -> None:
        await self._audit.record(
            AuditEventInput(
                user_id=issue.user_id,
                matter_id=issue.matter_id,
                actor=actor_id,
                action=action.value,
                target_type=AuditTargetType.ISSUE.value,
                target_id=issue.id,
                before_ref=before_ref,
                after_ref=after_ref,
                reason=reason,
                correlation_id=correlation_id,
            )
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _latest_by_type(issues: list[LegalIssue]) -> dict[str, LegalIssue]:
    """The most recent issue per type, which is the one a rerun reconciles with."""
    latest: dict[str, LegalIssue] = {}
    for issue in issues:
        current = latest.get(issue.issue_type_id)
        if current is None or issue.created_at >= current.created_at:
            latest[issue.issue_type_id] = issue
    return latest


def _merge(existing: tuple[str, ...], additional: tuple[str, ...]) -> tuple[str, ...]:
    """Union preserving order. Evidence is only ever added to an issue."""
    return tuple(dict.fromkeys((*existing, *additional)))


def _run_fingerprint(evaluations: tuple[CheckEvaluation, ...]) -> str:
    """Compact ``id:OUTCOME`` list, so the audit row shows what the run decided."""
    return ";".join(f"{e.check_definition_id}:{e.outcome.value}" for e in evaluations)


__all__ = ["CheckRunResult", "CheckService"]

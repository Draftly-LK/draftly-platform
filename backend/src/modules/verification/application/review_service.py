"""Canonical fact register and human decisions over immutable fact versions."""

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from src.modules.auth.ports import AuditEventInput, AuditPort
from src.modules.content_governance.contracts import (
    CAP_AUDIT_READ,
    CAP_FACT_CONFIRM_CRITICAL,
    CAP_FACT_CONFIRM_NONCRITICAL,
    FactStatus,
    FactSubject,
    ReviewTargetType,
    fact_type_for_field,
    get_fact_type,
)
from src.modules.document.contracts import (
    CandidateObservation,
    DocumentFactPort,
    FactEvidenceLocator,
)
from src.modules.matter.contracts import (
    MatterReadPort,
    MatterScopePort,
    SubjectKind,
    require_rta_capability,
)
from src.modules.verification.contracts import ConfirmedFactReadPort
from src.modules.verification.domain.errors import EvidenceRequiredError, FactNotFoundError
from src.modules.verification.domain.models import EvidenceReference, ExtractedFact, ReviewDecision
from src.modules.verification.domain.policies import guard_negative_conclusion
from src.modules.verification.ports import FactReviewRepository, PractisingNotaryPort
from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    NotFoundError,
    PreconditionFailedError,
)
from src.platform.idempotency import IdempotencyPort, fingerprint
from src.platform.ids import new_id
from src.platform.request_context import RequestContext


@dataclass(frozen=True)
class ManualFactInput:
    fact_type_id: str
    value: Any
    reason: str
    transaction_id: str | None = None
    subject_id: str | None = None
    evidence: FactEvidenceLocator | None = None


@dataclass(frozen=True)
class ReviewFactInput:
    action: Literal["accept", "correct", "reject", "associate", "edit"]
    expected_version: int
    reason: str | None = None
    value: Any = None
    transaction_id: str | None = None
    subject_id: str | None = None
    expected_scope_token: str | None = None
    resolve_fact_ids: tuple[str, ...] = ()
    evidence: FactEvidenceLocator | None = None


@dataclass(frozen=True)
class RegisterFactView:
    fact: ExtractedFact
    evidence: tuple[EvidenceReference, ...]
    scope_token: str
    conflict_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class FactHistory:
    facts: tuple[ExtractedFact, ...]
    decisions: tuple[ReviewDecision, ...]
    has_more: bool = False


def scope_token(facts: list[ExtractedFact]) -> str:
    return fingerprint(
        {"facts": sorted((f.id, f.version, f.status.value, f.evidence_stale) for f in facts)}
    )


class FactReviewService:
    def __init__(
        self,
        repository: FactReviewRepository,
        matters: MatterReadPort,
        scopes: MatterScopePort,
        documents: DocumentFactPort,
        practising: PractisingNotaryPort,
        replay: IdempotencyPort,
        audit: AuditPort,
        confirmed: ConfirmedFactReadPort,
    ) -> None:
        self._repo, self._matters, self._scopes = repository, matters, scopes
        self._documents, self._practising, self._replay = documents, practising, replay
        self._audit, self._confirmed = audit, confirmed

    async def _authorize(
        self, ctx: RequestContext, matter_id: str, fact_type_id: str | None = None
    ) -> None:
        matter = await self._matters.get_access_summary(ctx.actor_id, matter_id)
        if matter is None:
            raise NotFoundError()
        capability = CAP_AUDIT_READ
        if fact_type_id is not None:
            definition = get_fact_type(fact_type_id)
            if definition is None:
                raise DomainRuleError("Unknown governed fact type.")
            capability = (
                CAP_FACT_CONFIRM_CRITICAL if definition.critical else CAP_FACT_CONFIRM_NONCRITICAL
            )
        require_rta_capability(
            account_role=ctx.account_role.value,
            actor_id=ctx.actor_id,
            matter=matter,
            capability=capability,
        )
        if fact_type_id is not None:
            await self._practising.assert_practising(ctx)

    async def _scope(
        self,
        ctx: RequestContext,
        matter_id: str,
        fact_type_id: str,
        transaction_id: str | None,
        subject_id: str | None,
    ) -> str:
        definition = get_fact_type(fact_type_id)
        if definition is None:
            raise DomainRuleError("Unknown governed fact type.")
        kind: SubjectKind | None = None
        if definition.subject is FactSubject.PARTY:
            kind = "party"
        elif definition.subject in (FactSubject.PARCEL, FactSubject.TITLE):
            kind = "parcel"
        await self._scopes.validate_scope(
            ctx, matter_id, transaction_id=transaction_id, subject_id=subject_id, subject_kind=kind
        )
        return "assigned" if transaction_id and (subject_id or kind is None) else "unassigned"

    def _observation_fact(self, candidate: CandidateObservation) -> ExtractedFact | None:
        definition = fact_type_for_field(candidate.field_key)
        if definition is None:
            return None
        return ExtractedFact(
            id=candidate.id,
            user_id=candidate.user_id,
            matter_id=candidate.matter_id,
            fact_type_id=definition.id,
            value=candidate.value,
            original_value=candidate.original_value,
            status=FactStatus.EXTRACTED_CANDIDATE,
            created_at=candidate.created_at,
            version=candidate.version,
            source_candidate_id=candidate.id,
            source_candidate_version=candidate.version,
            origin="machine",
            scope_status="unassigned",
            evidence_stale=not candidate.current,
            model_reported_confidence=candidate.confidence,
            lineage_id=candidate.id,
        )

    async def _find(
        self, ctx: RequestContext, matter_id: str, fact_id: str
    ) -> tuple[ExtractedFact, CandidateObservation | None]:
        fact = await self._repo.get_fact(ctx.actor_id, fact_id)
        if fact is not None:
            if fact.matter_id != matter_id:
                raise FactNotFoundError()
            return await self._observational_alias(fact), None
        candidate = await self._documents.get_candidate(ctx.actor_id, matter_id, fact_id)
        if candidate is None:
            raise FactNotFoundError()
        existing = await self._repo.by_candidate(ctx.actor_id, matter_id, candidate.id)
        if existing:
            # A candidate id never silently follows a reviewed successor.
            raise PreconditionFailedError(
                currentFactId=existing.id, currentVersion=existing.version
            )
        fact = self._observation_fact(candidate)
        if fact is None:
            raise FactNotFoundError()
        return fact, candidate

    async def _observational_alias(self, fact: ExtractedFact) -> ExtractedFact:
        # The stored historical type remains unchanged. The source owner's
        # observational alias prevents the register presenting an inferred role.
        if (
            fact.origin == "legacy"
            and fact.source_candidate_id
            and fact.fact_type_id == "rta.party.transferee_nic"
        ):
            candidate = await self._documents.get_candidate(
                fact.user_id, fact.matter_id, fact.source_candidate_id
            )
            if candidate and candidate.field_key == "holderNic":
                return replace(fact, fact_type_id="rta.party.holder_nic", scope_status="unassigned")
        return fact

    async def _peers(self, fact: ExtractedFact) -> list[ExtractedFact]:
        peers = await self._repo.list_scope(
            fact.user_id, fact.matter_id, fact.fact_type_id, fact.transaction_id, fact.subject_id
        )
        if (
            not any(f.id == fact.id for f in peers)
            and fact.is_live
            and fact.status is not FactStatus.REJECTED
        ):
            peers.append(fact)
        return peers

    async def _evidence(
        self, ctx: RequestContext, matter_id: str, locator: FactEvidenceLocator
    ) -> EvidenceReference:
        source = await self._documents.validate_evidence(ctx.actor_id, matter_id, locator)
        return EvidenceReference(
            id=new_id("evidence"),
            user_id=ctx.actor_id,
            matter_id=matter_id,
            source_file_id=locator.source_file_id,
            page_number=locator.page_number,
            source_sha256=locator.source_sha256,
            created_at=datetime.now(UTC),
            extraction_run_id=locator.extraction_run_id,
            detected_document_id=locator.detected_document_id,
            text_span=source.supporting_text,
            page_text=source.page_text,
            precision=source.precision,
            candidate_version=locator.candidate_version,
            candidate_id=locator.candidate_id,
            interpretation_generation=source.locator.interpretation_generation,
        )

    async def list_facts(
        self, ctx: RequestContext, matter_id: str, *, limit: int = 50, after: str | None = None
    ) -> tuple[list[RegisterFactView], bool]:
        await self._authorize(ctx, matter_id)
        if not 1 <= limit <= 100:
            raise DomainRuleError()
        facts = await self._repo.list_page(ctx.actor_id, matter_id, after=after, limit=limit + 1)
        candidates: dict[str, CandidateObservation] = {}
        cursor = after
        while len(candidates) < limit + 1:
            batch = await self._documents.list_candidates(
                ctx.actor_id, matter_id, after=cursor, limit=100
            )
            for candidate in batch:
                if candidate.approved_fact_id or await self._repo.has_candidate_history(
                    ctx.actor_id, matter_id, candidate.id
                ):
                    continue
                fact = self._observation_fact(candidate)
                if fact:
                    candidates[fact.id] = candidate
                    facts.append(fact)
            if len(batch) < 100:
                break
            cursor = batch[-1].id
        facts.sort(key=lambda f: f.id)
        selected = facts[:limit]
        views = []
        for fact in selected:
            fact = await self._observational_alias(fact)
            evidence = tuple(
                await self._repo.list_evidence(ctx.actor_id, fact.evidence_reference_ids)
            )
            if fact.id in candidates:
                candidate = candidates[fact.id]
                try:
                    reference = await self._evidence(ctx, matter_id, candidate.evidence)
                    evidence = (replace(reference, id=f"candidate:{candidate.id}"),)
                except DomainRuleError:
                    fact = replace(fact, evidence_stale=True)
            peers = await self._peers(fact)
            views.append(
                RegisterFactView(
                    fact,
                    evidence,
                    scope_token(peers),
                    tuple(f.id for f in peers if f.id != fact.id and f.value != fact.value),
                )
            )
        return views, len(facts) > limit

    async def get_view(self, ctx: RequestContext, matter_id: str, fact_id: str) -> RegisterFactView:
        await self._authorize(ctx, matter_id)
        fact, candidate = await self._find(ctx, matter_id, fact_id)
        evidence = tuple(await self._repo.list_evidence(ctx.actor_id, fact.evidence_reference_ids))
        if candidate:
            try:
                evidence = (
                    replace(
                        await self._evidence(ctx, matter_id, candidate.evidence),
                        id=f"candidate:{candidate.id}",
                    ),
                )
            except DomainRuleError:
                fact = replace(fact, evidence_stale=True)
        peers = await self._peers(fact)
        return RegisterFactView(
            fact,
            evidence,
            scope_token(peers),
            tuple(f.id for f in peers if f.id != fact.id and f.value != fact.value),
        )

    async def add_manual(
        self, ctx: RequestContext, matter_id: str, data: ManualFactInput, *, key: str
    ) -> ExtractedFact:
        await self._authorize(ctx, matter_id, data.fact_type_id)
        await self._scopes.lock(ctx, matter_id)
        scope = await self._scope(
            ctx, matter_id, data.fact_type_id, data.transaction_id, data.subject_id
        )
        if not data.reason.strip() or not key:
            raise DomainRuleError("A reason and idempotency key are required.")
        route = f"/matters/{matter_id}/facts"
        request_hash = fingerprint(asdict(data))
        replay = await self._replay.find(
            user_id=ctx.actor_id, route=route, key=key, request_hash=request_hash
        )
        if replay:
            return await self._replayed(ctx, matter_id, str(replay["factId"]))
        fact_id = new_id("fact")
        evidence = await self._evidence(ctx, matter_id, data.evidence) if data.evidence else None
        if evidence:
            await self._repo.create_evidence(evidence)
        now = datetime.now(UTC)
        fact = ExtractedFact(
            id=fact_id,
            user_id=ctx.actor_id,
            matter_id=matter_id,
            fact_type_id=data.fact_type_id,
            value=data.value,
            status=FactStatus.REVIEW_REQUIRED,
            created_at=now,
            transaction_id=data.transaction_id,
            subject_id=data.subject_id,
            scope_status=scope,
            origin="lawyer",
            lineage_id=fact_id,
            manual_reason=data.reason,
            reviewed_by=ctx.actor_id,
            reviewed_at=now,
            evidence_reference_ids=(evidence.id,) if evidence else (),
            version=await self._repo.next_version(
                ctx.actor_id,
                matter_id,
                data.fact_type_id,
                transaction_id=data.transaction_id,
                subject_id=data.subject_id,
            ),
        )
        fact = await self._record(ctx, fact, action="manual", before=None, reason=data.reason)
        await self._replay.store(
            record_id=new_id("idem"),
            user_id=ctx.actor_id,
            route=route,
            key=key,
            request_hash=request_hash,
            response={"factId": fact.id},
        )
        return fact

    async def _replayed(self, ctx: RequestContext, matter_id: str, fact_id: str) -> ExtractedFact:
        fact = await self._repo.get_fact(ctx.actor_id, fact_id)
        if fact is None or fact.matter_id != matter_id:
            raise FactNotFoundError()
        await self._authorize(ctx, matter_id, fact.fact_type_id)
        return fact

    async def decide(
        self, ctx: RequestContext, matter_id: str, fact_id: str, data: ReviewFactInput, *, key: str
    ) -> ExtractedFact:
        await self._authorize(ctx, matter_id)
        await self._scopes.lock(ctx, matter_id)
        if data.action not in ("accept", "correct", "reject", "associate", "edit") or not key:
            raise DomainRuleError()
        if data.action != "associate" and (
            data.transaction_id is not None or data.subject_id is not None
        ):
            raise DomainRuleError("Scope fields are allowed only for associate decisions.")
        route = f"/matters/{matter_id}/facts/{fact_id}/{data.action}"
        request_hash = fingerprint(asdict(data))
        replay = await self._replay.find(
            user_id=ctx.actor_id, route=route, key=key, request_hash=request_hash
        )
        if replay:
            return await self._replayed(ctx, matter_id, str(replay["factId"]))
        fact, candidate = await self._find(ctx, matter_id, fact_id)
        await self._authorize(ctx, matter_id, fact.fact_type_id)
        if fact.version != data.expected_version or not fact.is_live:
            raise PreconditionFailedError(
                currentVersion=fact.version, currentFactId=fact.superseded_by_fact_id or fact.id
            )
        if data.action in ("correct", "reject", "associate") and not (
            data.reason and data.reason.strip()
        ):
            raise DomainRuleError("This decision requires a reason.")
        transaction_id = data.transaction_id if data.action == "associate" else fact.transaction_id
        subject_id = data.subject_id if data.action == "associate" else fact.subject_id
        scope = await self._scope(ctx, matter_id, fact.fact_type_id, transaction_id, subject_id)
        peers = await self._peers(fact)
        resolving: tuple[str, ...] = ()
        value = data.value if data.action in ("correct", "edit") else fact.value
        evidence: list[EvidenceReference] = []
        if data.action in ("accept", "correct"):
            if scope != "assigned":
                raise DomainRuleError(
                    "Associate this fact with its transaction and subject before accepting it."
                )
            if fact.evidence_stale:
                raise DomainRuleError("This fact's evidence is stale.")
            if data.expected_scope_token != scope_token(peers):
                raise PreconditionFailedError(
                    "The scope changed since review. Reload the alternatives."
                )
            conflicts = {f.id for f in peers if f.id != fact.id and f.value != value}
            if conflicts != set(data.resolve_fact_ids) or (
                conflicts and not (data.reason and data.reason.strip())
            ):
                raise ConflictError(
                    "Explicitly resolve all competing facts with a reason.",
                    conflictFactIds=sorted(conflicts),
                )
            resolving = tuple(sorted(conflicts))
            summary = await self._confirmed.summarise(ctx.actor_id, matter_id)
            guard_negative_conclusion(
                fact.fact_type_id,
                value,
                has_current_search_evidence=any(
                    search.fact_type_id == "rta.title.register_search_datetime"
                    and search.transaction_id == transaction_id
                    and search.subject_id == subject_id
                    for search in summary.scoped_confirmed
                ),
                confirmed_by_human=True,
            )
            locator = data.evidence or (candidate.evidence if candidate else None)
            if locator is None:
                references = await self._repo.list_evidence(
                    ctx.actor_id, fact.evidence_reference_ids
                )
                if (
                    not references
                    or len(references) != len(fact.evidence_reference_ids)
                    or any(r.matter_id != matter_id for r in references)
                ):
                    raise EvidenceRequiredError()
                # Revalidate every linked source, not merely the first one.
                for ref in references:
                    locator = FactEvidenceLocator(
                        ref.source_file_id,
                        ref.page_number,
                        ref.source_sha256,
                        ref.extraction_run_id,
                        ref.detected_document_id,
                        ref.candidate_id,
                        ref.candidate_version,
                        ref.text_span,
                        ref.interpretation_generation,
                    )
                    evidence.append(await self._evidence(ctx, matter_id, locator))
            else:
                evidence.append(await self._evidence(ctx, matter_id, locator))
        elif candidate:
            # Association/rejection remains actionable when extraction is stale.
            try:
                evidence.append(await self._evidence(ctx, matter_id, candidate.evidence))
            except DomainRuleError:
                fact = replace(fact, evidence_stale=True)
        for reference in evidence:
            await self._repo.create_evidence(reference)
        if candidate:
            fact = replace(fact, evidence_reference_ids=tuple(r.id for r in evidence))
            await self._repo.create_fact(fact)
        now = datetime.now(UTC)
        status = (
            FactStatus.REJECTED
            if data.action == "reject"
            else (
                FactStatus.LAWYER_CONFIRMED
                if data.action in ("accept", "correct")
                else FactStatus.REVIEW_REQUIRED
            )
        )
        version = await self._repo.next_version(
            ctx.actor_id,
            matter_id,
            fact.fact_type_id,
            transaction_id=transaction_id,
            subject_id=subject_id,
        )
        successor = replace(
            fact,
            id=new_id("fact"),
            value=value,
            normalized_value=None if data.action in ("correct", "edit") else fact.normalized_value,
            status=status,
            created_at=now,
            reviewed_by=ctx.actor_id,
            reviewed_at=now,
            transaction_id=transaction_id,
            subject_id=subject_id,
            scope_status=scope,
            version=version,
            supersedes_fact_id=fact.id,
            superseded_by_fact_id=None,
            locked_by_form_id=None,
            lineage_id=fact.lineage_id or fact.id,
            evidence_reference_ids=tuple(r.id for r in evidence) or fact.evidence_reference_ids,
        )
        successor = await self._record(
            ctx, successor, action=data.action, before=fact, reason=data.reason, resolved=resolving
        )
        for previous in (fact.id, *resolving):
            await self._repo.mark_superseded(
                ctx.actor_id, previous, superseded_by_fact_id=successor.id
            )
        await self._replay.store(
            record_id=new_id("idem"),
            user_id=ctx.actor_id,
            route=route,
            key=key,
            request_hash=request_hash,
            response={"factId": successor.id},
        )
        return successor

    async def decide_candidate(
        self,
        ctx: RequestContext,
        matter_id: str,
        candidate_id: str,
        *,
        action: Literal["accept", "edit"],
        expected_version: int,
        value: str | None = None,
    ) -> ExtractedFact:
        """Legacy document commands use a stable candidate route for replay.

        The projection may advance to a canonical successor; retries must still
        address the original request, with current authorization on every replay.
        """
        await self._authorize(ctx, matter_id)
        await self._scopes.lock(ctx, matter_id)
        route = f"/matters/{matter_id}/candidates/{candidate_id}/{action}"
        key = f"document:{candidate_id}:{expected_version}"
        request_hash = fingerprint({"version": expected_version, "value": value})
        replay = await self._replay.find(
            user_id=ctx.actor_id, route=route, key=key, request_hash=request_hash
        )
        if replay:
            return await self._replayed(ctx, matter_id, str(replay["factId"]))
        current = await self._repo.by_candidate(ctx.actor_id, matter_id, candidate_id)
        if action == "edit" and current and current.is_confirmed:
            raise CapabilityDeniedError("Use the canonical correction command for a reviewed fact.")
        target_id = current.id if current else candidate_id
        view = await self.get_view(ctx, matter_id, target_id)
        saved = await self.decide(
            ctx,
            matter_id,
            target_id,
            ReviewFactInput(
                action,
                expected_version,
                reason="Document candidate edit" if action == "edit" else None,
                value=value,
                expected_scope_token=view.scope_token,
            ),
            key=key,
        )
        await self._replay.store(
            record_id=new_id("idem"),
            user_id=ctx.actor_id,
            route=route,
            key=key,
            request_hash=request_hash,
            response={"factId": saved.id},
        )
        return saved

    async def _record(
        self,
        ctx: RequestContext,
        fact: ExtractedFact,
        *,
        action: str,
        before: ExtractedFact | None,
        reason: str | None,
        resolved: tuple[str, ...] = (),
    ) -> ExtractedFact:
        decision = ReviewDecision(
            id=new_id("review"),
            user_id=ctx.actor_id,
            matter_id=fact.matter_id,
            target_type=ReviewTargetType.FACT,
            target_id=fact.id,
            decision=action,
            reviewer_id=ctx.actor_id,
            reviewer_role=ctx.account_role.value,
            created_at=fact.created_at,
            previous_value=before.value if before else None,
            new_value=fact.value,
            reason=reason,
            resolved_fact_ids=resolved,
        )
        await self._repo.create_decision(decision)
        saved = await self._repo.create_fact(replace(fact, review_decision_id=decision.id))
        actions = {
            "manual": "rta.fact.added",
            "edit": "rta.fact.corrected",
            "accept": "rta.fact.confirmed",
            "correct": "rta.fact.corrected",
            "reject": "rta.fact.rejected",
            "associate": "rta.fact.associated",
        }
        await self._audit.record(
            AuditEventInput(
                user_id=ctx.actor_id,
                matter_id=fact.matter_id,
                actor=ctx.actor_id,
                action=actions[action],
                target_type="fact",
                target_id=fact.id,
                before_ref=before.id if before else None,
                after_ref=fact.id,
                reason=f"decision:{decision.id}",
                correlation_id=ctx.correlation_id,
            )
        )
        return saved

    async def history(
        self,
        ctx: RequestContext,
        matter_id: str,
        fact_id: str,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> FactHistory:
        await self._authorize(ctx, matter_id)
        if not 1 <= limit <= 100:
            raise DomainRuleError()
        fact, candidate = await self._find(ctx, matter_id, fact_id)
        if candidate:
            return FactHistory((fact,), ())
        facts = await self._repo.history(
            ctx.actor_id, matter_id, fact.lineage_id or fact.id, limit + 1, after=after
        )
        selected = facts[:limit]
        decisions = await self._repo.decisions_for(
            ctx.actor_id, matter_id, tuple(f.id for f in selected), limit
        )
        return FactHistory(tuple(selected), tuple(decisions), len(facts) > limit)

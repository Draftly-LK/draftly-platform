"""SQLAlchemy repositories for the fact tier, plus the read adapters.

`SqlConfirmedFactReader` implements `verification.contracts.ConfirmedFactReadPort`
and is what the matter's eligibility gates read. It reports what is *not*
confirmed as carefully as what is: a critical fact type with no live confirmed
row appears in ``unconfirmed_critical_fact_type_ids``, which is what keeps the
V0 predicate honest about evidence it has never seen.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    CRITICAL_FACT_TYPE_IDS,
    EvidenceRegionType,
    FactStatus,
    ReviewTargetType,
)
from src.modules.document.contracts import FactEvidenceLocator
from src.modules.verification.contracts import (
    ConfirmedFactValue,
    FactTierSummary,
)
from src.modules.verification.domain.models import (
    BoundingBox,
    EvidenceReference,
    ExtractedFact,
    ReviewDecision,
)
from src.modules.verification.infrastructure.orm import (
    EvidenceReferenceRow,
    ExtractedFactRow,
    ReviewDecisionRow,
)

#: The fact type whose confirmation means a dated register search exists.
SEARCH_EVIDENCE_FACT_TYPE_ID = "rta.title.register_search_datetime"


def _to_evidence(row: EvidenceReferenceRow) -> EvidenceReference:
    box = row.bounding_box
    return EvidenceReference(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        source_file_id=row.source_file_id,
        detected_document_id=row.detected_document_id,
        page_number=row.page_number,
        source_sha256=row.source_sha256,
        bounding_box=(
            BoundingBox(
                x=float(box["x"]),
                y=float(box["y"]),
                width=float(box["width"]),
                height=float(box["height"]),
                coordinate_space=str(box["coordinateSpace"]),
            )
            if isinstance(box, dict)
            else None
        ),
        text_span=row.text_span,
        region_type=EvidenceRegionType(row.region_type) if row.region_type else None,
        extraction_run_id=row.extraction_run_id,
        created_at=row.created_at,
        page_text=row.page_text,
        precision=row.precision or "page",
        candidate_version=row.candidate_version,
        candidate_id=row.candidate_id,
        interpretation_generation=row.interpretation_generation,
    )


def _to_fact(row: ExtractedFactRow) -> ExtractedFact:
    return ExtractedFact(
        id=row.id,
        user_id=row.user_id,
        matter_id=row.matter_id,
        fact_type_id=row.fact_type_id,
        subject_id=row.subject_id,
        transaction_id=row.transaction_id,
        scope_status=row.scope_status or "legacy-unassigned",
        evidence_stale=bool(row.evidence_stale),
        original_value=row.original_value,
        origin=row.origin or "legacy",
        source_candidate_id=row.source_candidate_id,
        source_candidate_version=row.source_candidate_version,
        lineage_id=row.lineage_id,
        manual_reason=row.manual_reason,
        value=row.value,
        normalized_value=row.normalized_value,
        status=FactStatus(row.status),
        model_reported_confidence=row.model_reported_confidence,
        evidence_reference_ids=tuple(row.evidence_reference_ids),
        derivation_kind=row.derivation_kind,
        derivation_input_fact_ids=tuple(row.derivation_input_fact_ids),
        derivation_formula_version=row.derivation_formula_version,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_decision_id=row.review_decision_id,
        supersedes_fact_id=row.supersedes_fact_id,
        superseded_by_fact_id=row.superseded_by_fact_id,
        locked_by_form_id=row.locked_by_form_id,
        version=row.version,
        created_at=row.created_at,
    )


class SqlVerificationRepository:
    """Evidence references, fact versions, and review decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_scope(
        self,
        user_id: str,
        matter_id: str,
        fact_type_id: str,
        transaction_id: str | None,
        subject_id: str | None,
    ) -> list[ExtractedFact]:
        rows = (
            await self._session.execute(
                select(ExtractedFactRow)
                .where(
                    ExtractedFactRow.user_id == user_id,
                    ExtractedFactRow.matter_id == matter_id,
                    ExtractedFactRow.fact_type_id == fact_type_id,
                    ExtractedFactRow.transaction_id == transaction_id,
                    ExtractedFactRow.subject_id == subject_id,
                    ExtractedFactRow.superseded_by_fact_id.is_(None),
                    ExtractedFactRow.status.not_in(("SUPERSEDED", "REJECTED")),
                )
                .order_by(ExtractedFactRow.id)
            )
        ).scalars()
        return [_to_fact(row) for row in rows]

    async def list_page(
        self, user_id: str, matter_id: str, *, after: str | None, limit: int
    ) -> list[ExtractedFact]:
        query = select(ExtractedFactRow).where(
            ExtractedFactRow.user_id == user_id,
            ExtractedFactRow.matter_id == matter_id,
            ExtractedFactRow.superseded_by_fact_id.is_(None),
        )
        if after:
            query = query.where(ExtractedFactRow.id > after)
        return [
            _to_fact(row)
            for row in (
                await self._session.execute(query.order_by(ExtractedFactRow.id).limit(limit))
            ).scalars()
        ]

    async def by_candidate(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> ExtractedFact | None:
        row = (
            await self._session.execute(
                select(ExtractedFactRow)
                .where(
                    ExtractedFactRow.user_id == user_id,
                    ExtractedFactRow.matter_id == matter_id,
                    ExtractedFactRow.source_candidate_id == candidate_id,
                    ExtractedFactRow.superseded_by_fact_id.is_(None),
                )
                .order_by(ExtractedFactRow.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _to_fact(row) if row else None

    async def has_candidate_history(self, user_id: str, matter_id: str, candidate_id: str) -> bool:
        # A resolved loser may have no live successor in its own candidate
        # lineage. Its immutable materialization still suppresses the bridge.
        return (
            await self._session.execute(
                select(ExtractedFactRow.id)
                .where(
                    ExtractedFactRow.user_id == user_id,
                    ExtractedFactRow.matter_id == matter_id,
                    ExtractedFactRow.source_candidate_id == candidate_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none() is not None

    async def history(
        self, user_id: str, matter_id: str, lineage_id: str, limit: int, *, after: str | None = None
    ) -> list[ExtractedFact]:
        query = select(ExtractedFactRow).where(
            ExtractedFactRow.user_id == user_id,
            ExtractedFactRow.matter_id == matter_id,
            or_(ExtractedFactRow.lineage_id == lineage_id, ExtractedFactRow.id == lineage_id),
        )
        if after:
            anchor = (
                await self._session.execute(query.where(ExtractedFactRow.id == after))
            ).scalar_one_or_none()
            if anchor is None:
                from src.platform.api.pagination import InvalidCursorError

                raise InvalidCursorError()
            query = query.where(
                tuple_(ExtractedFactRow.created_at, ExtractedFactRow.id)
                > (anchor.created_at, anchor.id)
            )
        rows = (
            await self._session.execute(
                query.order_by(ExtractedFactRow.created_at, ExtractedFactRow.id).limit(limit)
            )
        ).scalars()
        return [_to_fact(row) for row in rows]

    async def decisions_for(
        self, user_id: str, matter_id: str, fact_ids: tuple[str, ...], limit: int
    ) -> list[ReviewDecision]:
        rows = (
            await self._session.execute(
                select(ReviewDecisionRow)
                .where(
                    ReviewDecisionRow.user_id == user_id,
                    ReviewDecisionRow.matter_id == matter_id,
                    ReviewDecisionRow.target_type == "FACT",
                    ReviewDecisionRow.target_id.in_(fact_ids),
                )
                .order_by(ReviewDecisionRow.created_at, ReviewDecisionRow.id)
                .limit(limit)
            )
        ).scalars()
        return [
            ReviewDecision(
                id=row.id,
                user_id=row.user_id,
                matter_id=row.matter_id,
                target_type=ReviewTargetType.FACT,
                target_id=row.target_id,
                decision=row.decision,
                reviewer_id=row.reviewer_id,
                reviewer_role=row.reviewer_role,
                created_at=row.created_at,
                previous_value=row.previous_value,
                new_value=row.new_value,
                reason=row.reason,
                resolved_fact_ids=tuple(row.resolved_fact_ids),
            )
            for row in rows
        ]

    async def create_evidence(self, evidence: EvidenceReference) -> EvidenceReference:
        box = evidence.bounding_box
        row = EvidenceReferenceRow(
            id=evidence.id,
            user_id=evidence.user_id,
            matter_id=evidence.matter_id,
            source_file_id=evidence.source_file_id,
            detected_document_id=evidence.detected_document_id,
            page_number=evidence.page_number,
            source_sha256=evidence.source_sha256,
            bounding_box=(
                {
                    "x": box.x,
                    "y": box.y,
                    "width": box.width,
                    "height": box.height,
                    "coordinateSpace": box.coordinate_space,
                }
                if box
                else None
            ),
            text_span=evidence.text_span,
            region_type=evidence.region_type.value if evidence.region_type else None,
            extraction_run_id=evidence.extraction_run_id,
            created_at=evidence.created_at,
            page_text=evidence.page_text,
            precision=evidence.precision,
            candidate_version=evidence.candidate_version,
            candidate_id=evidence.candidate_id,
            interpretation_generation=evidence.interpretation_generation,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_evidence(row)

    async def list_evidence(
        self, user_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> list[EvidenceReference]:
        if not evidence_reference_ids:
            return []
        result = await self._session.execute(
            select(EvidenceReferenceRow).where(
                EvidenceReferenceRow.user_id == user_id,
                EvidenceReferenceRow.id.in_(evidence_reference_ids),
            )
        )
        by_id = {row.id: row for row in result.scalars().all()}
        return [_to_evidence(by_id[rid]) for rid in evidence_reference_ids if rid in by_id]

    async def create_fact(self, fact: ExtractedFact) -> ExtractedFact:
        row = ExtractedFactRow(
            id=fact.id,
            user_id=fact.user_id,
            matter_id=fact.matter_id,
            fact_type_id=fact.fact_type_id,
            subject_id=fact.subject_id,
            transaction_id=fact.transaction_id,
            scope_status=fact.scope_status,
            evidence_stale=fact.evidence_stale,
            original_value=fact.original_value,
            origin=fact.origin,
            source_candidate_id=fact.source_candidate_id,
            source_candidate_version=fact.source_candidate_version,
            lineage_id=fact.lineage_id,
            manual_reason=fact.manual_reason,
            value=fact.value,
            normalized_value=fact.normalized_value,
            status=fact.status.value,
            model_reported_confidence=fact.model_reported_confidence,
            evidence_reference_ids=list(fact.evidence_reference_ids),
            derivation_kind=fact.derivation_kind,
            derivation_input_fact_ids=list(fact.derivation_input_fact_ids),
            derivation_formula_version=fact.derivation_formula_version,
            reviewed_by=fact.reviewed_by,
            reviewed_at=fact.reviewed_at,
            review_decision_id=fact.review_decision_id,
            supersedes_fact_id=fact.supersedes_fact_id,
            locked_by_form_id=fact.locked_by_form_id,
            version=fact.version,
            created_at=fact.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_fact(row)

    async def get_fact(self, user_id: str, fact_id: str) -> ExtractedFact | None:
        row = await self._fact_row(user_id, fact_id)
        return _to_fact(row) if row is not None else None

    async def _fact_row(self, user_id: str, fact_id: str) -> ExtractedFactRow | None:
        result = await self._session.execute(
            select(ExtractedFactRow).where(
                ExtractedFactRow.user_id == user_id, ExtractedFactRow.id == fact_id
            )
        )
        return result.scalar_one_or_none()

    async def mark_superseded(
        self, user_id: str, fact_id: str, *, superseded_by_fact_id: str
    ) -> None:
        """The only mutation on a fact row, and it never touches ``value``."""
        row = await self._fact_row(user_id, fact_id)
        if row is None:
            return
        row.superseded_by_fact_id = superseded_by_fact_id
        row.status = FactStatus.SUPERSEDED.value
        await self._session.flush()

    async def lock_for_form(self, user_id: str, fact_id: str, *, form_id: str) -> None:
        row = await self._fact_row(user_id, fact_id)
        if row is None:
            return
        row.locked_by_form_id = form_id
        row.status = FactStatus.LOCKED_FOR_FORM.value
        await self._session.flush()

    async def list_live_facts(self, user_id: str, matter_id: str) -> list[ExtractedFact]:
        result = await self._session.execute(
            select(ExtractedFactRow)
            .where(
                ExtractedFactRow.user_id == user_id,
                ExtractedFactRow.matter_id == matter_id,
                ExtractedFactRow.superseded_by_fact_id.is_(None),
            )
            .order_by(ExtractedFactRow.fact_type_id.asc(), ExtractedFactRow.created_at.asc())
        )
        return [_to_fact(row) for row in result.scalars().all()]

    async def list_all_facts(self, user_id: str, matter_id: str) -> list[ExtractedFact]:
        """Includes superseded versions: history is part of the record."""
        result = await self._session.execute(
            select(ExtractedFactRow)
            .where(
                ExtractedFactRow.user_id == user_id,
                ExtractedFactRow.matter_id == matter_id,
            )
            .order_by(ExtractedFactRow.fact_type_id.asc(), ExtractedFactRow.created_at.asc())
        )
        return [_to_fact(row) for row in result.scalars().all()]

    async def next_version(
        self,
        user_id: str,
        matter_id: str,
        fact_type_id: str,
        *,
        transaction_id: str | None = None,
        subject_id: str | None = None,
    ) -> int:
        result = await self._session.execute(
            select(ExtractedFactRow.version)
            .where(
                ExtractedFactRow.user_id == user_id,
                ExtractedFactRow.matter_id == matter_id,
                ExtractedFactRow.fact_type_id == fact_type_id,
                ExtractedFactRow.transaction_id == transaction_id,
                ExtractedFactRow.subject_id == subject_id,
            )
            .order_by(ExtractedFactRow.version.desc())
            .limit(1)
        )
        return (result.scalar_one_or_none() or 0) + 1

    async def create_decision(
        self, decision: ReviewDecision, *, human: bool = True
    ) -> ReviewDecision:
        row = ReviewDecisionRow(
            id=decision.id,
            user_id=decision.user_id,
            matter_id=decision.matter_id,
            target_type=decision.target_type.value,
            target_id=decision.target_id,
            decision=decision.decision,
            previous_value=decision.previous_value,
            new_value=decision.new_value,
            reason=decision.reason,
            reviewer_id=decision.reviewer_id,
            reviewer_role=decision.reviewer_role,
            human_decision=human,
            created_at=decision.created_at,
            resolved_fact_ids=list(decision.resolved_fact_ids),
        )
        self._session.add(row)
        await self._session.flush()
        return decision

    async def list_decisions(
        self, user_id: str, matter_id: str, *, target_type: ReviewTargetType | None = None
    ) -> list[ReviewDecision]:
        query = select(ReviewDecisionRow).where(
            ReviewDecisionRow.user_id == user_id, ReviewDecisionRow.matter_id == matter_id
        )
        if target_type is not None:
            query = query.where(ReviewDecisionRow.target_type == target_type.value)
        result = await self._session.execute(query.order_by(ReviewDecisionRow.created_at.asc()))
        return [
            ReviewDecision(
                id=row.id,
                user_id=row.user_id,
                matter_id=row.matter_id,
                target_type=ReviewTargetType(row.target_type),
                target_id=row.target_id,
                decision=row.decision,
                previous_value=row.previous_value,
                new_value=row.new_value,
                reason=row.reason,
                reviewer_id=row.reviewer_id,
                reviewer_role=row.reviewer_role,
                created_at=row.created_at,
                resolved_fact_ids=tuple(row.resolved_fact_ids or ()),
            )
            for row in result.scalars().all()
        ]


class SqlConfirmedFactReader:
    """Implements ``ConfirmedFactReadPort`` for the matter's eligibility gates."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SqlVerificationRepository(session)
        self._session = session

    async def fact_ids_for_transaction(
        self, user_id: str, matter_id: str, transaction_id: str
    ) -> tuple[str, ...]:
        return tuple(
            (
                await self._session.execute(
                    select(ExtractedFactRow.id).where(
                        ExtractedFactRow.user_id == user_id,
                        ExtractedFactRow.matter_id == matter_id,
                        ExtractedFactRow.transaction_id == transaction_id,
                    )
                )
            ).scalars()
        )

    async def summarise(self, user_id: str, matter_id: str) -> FactTierSummary:
        facts = await self._repo.list_live_facts(user_id, matter_id)
        groups: dict[tuple[str | None, str | None, str], list[ExtractedFact]] = defaultdict(list)
        for fact in facts:
            if not fact.is_live or fact.status.value == "REJECTED":
                continue
            groups[(fact.transaction_id, fact.subject_id, fact.fact_type_id)].append(fact)
        scoped: list[ConfirmedFactValue] = []
        conflicted: set[str] = set()
        scoped_conflicts = []
        for (transaction_id, subject_id, fact_type_id), group in groups.items():
            # A later version alone is never a conflict-resolution decision.
            if any(f.status is FactStatus.CONFLICTED for f in group) or any(
                f.value != group[0].value for f in group[1:]
            ):
                conflicted.add(fact_type_id)
                scoped_conflicts.append((transaction_id, subject_id, fact_type_id))
                continue
            eligible = [
                f
                for f in group
                if f.is_confirmed and not f.evidence_stale and f.scope_status != "unassigned"
            ]
            if not eligible:
                continue
            fact = max(eligible, key=lambda f: (f.version, f.id))
            scoped.append(
                ConfirmedFactValue(
                    fact_id=fact.id,
                    fact_type_id=fact.fact_type_id,
                    value=fact.value,
                    version=fact.version,
                    evidence_reference_ids=fact.evidence_reference_ids,
                    transaction_id=fact.transaction_id,
                    subject_id=fact.subject_id,
                    scope_status=fact.scope_status,
                )
            )
        confirmed = {
            value.fact_type_id: value
            for value in scoped
            if value.fact_type_id not in conflicted
            and sum(1 for key in groups if key[2] == value.fact_type_id) == 1
        }
        # Current consumers do not select a transaction/subject. Uniqueness
        # within each type is insufficient: different types can still form an
        # unreviewed composite. Preserve the lossless projection for explicit
        # scoped consumers and withhold the whole compatibility map meanwhile.
        if len({(value.transaction_id, value.subject_id) for value in scoped}) > 1:
            confirmed = {}
        unconfirmed_critical = tuple(
            sorted(
                fact_type_id
                for fact_type_id in CRITICAL_FACT_TYPE_IDS
                if fact_type_id not in confirmed
            )
        )
        return FactTierSummary(
            confirmed=confirmed,
            unconfirmed_critical_fact_type_ids=unconfirmed_critical,
            conflicted_fact_type_ids=tuple(sorted(set(conflicted))),
            has_current_search_evidence=SEARCH_EVIDENCE_FACT_TYPE_ID in confirmed,
            scoped_confirmed=tuple(scoped),
            scoped_conflicts=tuple(scoped_conflicts),
        )


class SqlEvidenceReader:
    """Implements ``EvidenceReadPort``."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SqlVerificationRepository(session)

    async def source_pages(
        self, user_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> tuple[tuple[str, int], ...]:
        references = await self._repo.list_evidence(user_id, evidence_reference_ids)
        return tuple((ref.source_file_id, ref.page_number) for ref in references)

    async def requirement_locators(
        self, user_id: str, matter_id: str, evidence_reference_ids: tuple[str, ...]
    ) -> tuple[FactEvidenceLocator, ...]:
        from src.platform.errors import NotFoundError

        references = await self._repo.list_evidence(user_id, evidence_reference_ids)
        if {ref.id for ref in references} != set(evidence_reference_ids) or any(
            ref.matter_id != matter_id for ref in references
        ):
            raise NotFoundError()
        return tuple(
            FactEvidenceLocator(
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
            for ref in references
        )


def utc_now() -> datetime:
    from datetime import UTC

    return datetime.now(tz=UTC)


def as_json(value: Any) -> Any:
    """Values are stored as JSON; enums arrive as their ``.value``."""
    return getattr(value, "value", value)

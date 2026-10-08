"""Document-owned validation of immutable evidence and processing observations."""

import hashlib
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.document.contracts import (
    CandidateObservation,
    FactEvidenceLocator,
    FactEvidenceSource,
)
from src.modules.document.domain.registry import observational_field_key
from src.modules.document.infrastructure.orm import (
    DetectedDocumentRow,
    DocumentFragmentRow,
    DocumentProcessingPageRow,
    ProcessingCandidateFieldRow,
    ProcessingLogicalDocumentRow,
    SourceFileRow,
)
from src.modules.document.ports import SourceFileStoragePort
from src.platform.errors import DomainRuleError, NotFoundError, PreconditionFailedError


class SqlDocumentFactReader:
    def __init__(self, session: AsyncSession, storage: SourceFileStoragePort) -> None:
        self._session, self._storage = session, storage

    async def list_candidates(
        self, user_id: str, matter_id: str, *, after: str | None = None, limit: int = 100
    ) -> list[CandidateObservation]:
        query = select(ProcessingCandidateFieldRow.id).where(
            ProcessingCandidateFieldRow.user_id == user_id,
            ProcessingCandidateFieldRow.matter_id == matter_id,
        )
        if after:
            query = query.where(ProcessingCandidateFieldRow.id > after)
        result = []
        for candidate_id in (
            await self._session.execute(query.order_by(ProcessingCandidateFieldRow.id).limit(limit))
        ).scalars():
            candidate = await self.get_candidate(user_id, matter_id, candidate_id)
            if candidate:
                result.append(candidate)
        return result

    async def get_candidate(
        self, user_id: str, matter_id: str, candidate_id: str
    ) -> CandidateObservation | None:
        result = (
            await self._session.execute(
                select(ProcessingCandidateFieldRow, ProcessingLogicalDocumentRow, SourceFileRow)
                .join(
                    ProcessingLogicalDocumentRow,
                    ProcessingLogicalDocumentRow.id
                    == ProcessingCandidateFieldRow.logical_document_id,
                )
                .join(
                    SourceFileRow, SourceFileRow.id == ProcessingLogicalDocumentRow.source_file_id
                )
                .where(
                    ProcessingCandidateFieldRow.user_id == user_id,
                    ProcessingCandidateFieldRow.matter_id == matter_id,
                    ProcessingCandidateFieldRow.id == candidate_id,
                    ProcessingLogicalDocumentRow.user_id == user_id,
                    ProcessingLogicalDocumentRow.matter_id == matter_id,
                    SourceFileRow.user_id == user_id,
                    SourceFileRow.matter_id == matter_id,
                )
            )
        ).one_or_none()
        if result is None:
            return None
        candidate, logical, source = result
        # Earlier NIC extraction used the form-role key. A holder observation
        # is not evidence of a transferee role, including on legacy candidates.
        key = observational_field_key(logical.type_id, candidate.key)
        value = (
            candidate.edited_value
            if candidate.edited_value is not None
            else candidate.candidate_value
        )
        locator = FactEvidenceLocator(
            source.id,
            candidate.page_no,
            source.sha256,
            logical.processing_run_id,
            logical.detected_document_id,
            candidate.id,
            candidate.version,
            candidate.candidate_value,
        )
        current = source.state == "PROCESSED" and source.superseded_by_source_file_id is None
        return CandidateObservation(
            candidate.id,
            user_id,
            matter_id,
            key,
            candidate.candidate_value,
            value,
            candidate.model_reported_confidence,
            candidate.version,
            source.created_at,
            locator,
            current,
            candidate.approved_fact_id,
        )

    async def validate_evidence(
        self, user_id: str, matter_id: str, evidence: FactEvidenceLocator
    ) -> FactEvidenceSource:
        source = (
            await self._session.execute(
                select(SourceFileRow)
                .where(
                    SourceFileRow.user_id == user_id,
                    SourceFileRow.matter_id == matter_id,
                    SourceFileRow.id == evidence.source_file_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if source is None:
            raise NotFoundError()
        if (
            source.sha256 != evidence.source_sha256
            or source.state
            in ("SUPERSEDED", "REJECTED", "QUARANTINED", "UPLOAD_INITIATED", "PROCESSING")
            or source.superseded_by_source_file_id
        ):
            raise DomainRuleError("The evidence source is not current and readable.")
        if source.page_count is None or not 1 <= evidence.page_number <= source.page_count:
            raise DomainRuleError("The evidence page is outside the source.")
        if evidence.candidate_id:
            candidate = await self.get_candidate(user_id, matter_id, evidence.candidate_id)
            if candidate is None:
                raise NotFoundError()
            if candidate.version != evidence.candidate_version:
                raise PreconditionFailedError(currentVersion=candidate.version)
            if (
                not candidate.current
                or candidate.evidence.source_file_id != source.id
                or candidate.evidence.extraction_run_id != evidence.extraction_run_id
                or candidate.evidence.detected_document_id != evidence.detected_document_id
                or candidate.evidence.page_number != evidence.page_number
            ):
                raise DomainRuleError("The candidate evidence is stale.")
        if evidence.detected_document_id:
            document = (
                await self._session.execute(
                    select(DetectedDocumentRow)
                    .where(
                        DetectedDocumentRow.user_id == user_id,
                        DetectedDocumentRow.matter_id == matter_id,
                        DetectedDocumentRow.id == evidence.detected_document_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if document is None:
                raise NotFoundError()
            if document.class_status == "REJECTED" or document.version_relationship == "SUPERSEDED":
                raise DomainRuleError("The evidence interpretation is stale.")
            fragments = list(
                (
                    await self._session.execute(
                        select(DocumentFragmentRow).where(
                            DocumentFragmentRow.user_id == user_id,
                            DocumentFragmentRow.matter_id == matter_id,
                            DocumentFragmentRow.detected_document_id == document.id,
                        )
                    )
                ).scalars()
            )
            if not any(
                f.source_file_id == source.id and f.page_start <= evidence.page_number <= f.page_end
                for f in fragments
            ):
                raise DomainRuleError("The evidence page is outside the document.")
            if evidence.extraction_run_id:
                logical = (
                    await self._session.execute(
                        select(ProcessingLogicalDocumentRow).where(
                            ProcessingLogicalDocumentRow.user_id == user_id,
                            ProcessingLogicalDocumentRow.matter_id == matter_id,
                            ProcessingLogicalDocumentRow.detected_document_id == document.id,
                            ProcessingLogicalDocumentRow.processing_run_id
                            == evidence.extraction_run_id,
                        )
                    )
                ).scalar_one_or_none()
                if (
                    logical is None
                    or logical.type_id != document.class_id
                    or set(logical.page_numbers)
                    != {
                        page
                        for f in fragments
                        if f.source_file_id == source.id
                        for page in range(f.page_start, f.page_end + 1)
                    }
                ):
                    raise DomainRuleError(
                        "The evidence interpretation requires refreshed extraction."
                    )
        try:
            original = await self._storage.get(
                source.storage_object_key, version=source.storage_object_version
            )
            if hashlib.sha256(original).hexdigest() != evidence.source_sha256:
                raise DomainRuleError("The evidence hash does not match its original.")
            page_text = ""
            if evidence.extraction_run_id:
                page = (
                    await self._session.execute(
                        select(DocumentProcessingPageRow).where(
                            DocumentProcessingPageRow.user_id == user_id,
                            DocumentProcessingPageRow.matter_id == matter_id,
                            DocumentProcessingPageRow.source_file_id == source.id,
                            DocumentProcessingPageRow.processing_run_id
                            == evidence.extraction_run_id,
                            DocumentProcessingPageRow.page_no == evidence.page_number,
                        )
                    )
                ).scalar_one_or_none()
                if page is None:
                    raise DomainRuleError("The evidence page artifact is unavailable.")
                await self._storage.get(
                    page.corrected_webp_key, version=page.corrected_webp_version
                )
                page_text = (
                    await self._storage.get(page.plain_text_key, version=page.plain_text_version)
                ).decode("utf-8")
        except (OSError, ValueError, KeyError) as exc:
            raise DomainRuleError("The evidence artifact is unavailable.") from exc
        snippet = evidence.snippet if evidence.snippet and evidence.snippet in page_text else None
        return FactEvidenceSource(
            replace(evidence, snippet=snippet), page_text, snippet, "text" if snippet else "page"
        )

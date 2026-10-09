"""Document-owned validation of immutable evidence and processing observations."""

import hashlib
from dataclasses import replace

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.document.contracts import (
    CandidateObservation,
    FactEvidenceLocator,
    FactEvidenceSource,
)
from src.modules.document.domain.errors import (
    SourceObjectIntegrityError,
    SourceObjectNotFoundError,
    SourceObjectUnavailableError,
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

_ARTIFACT_ERRORS = (
    SourceObjectNotFoundError,
    SourceObjectIntegrityError,
    SourceObjectUnavailableError,
    OSError,
    ValueError,
    KeyError,
)


class SqlDocumentFactReader:
    def __init__(self, session: AsyncSession, storage: SourceFileStoragePort) -> None:
        self._session, self._storage = session, storage
        # This reader is constructed for one request/session. Cache successful
        # immutable artifact validation only; every call still checks current SQL
        # ownership, source state, candidate version and interpretation membership.
        self._validated: set[tuple[str, str, str, str, str]] = set()
        self._texts: dict[tuple[str, str, str, str, str], str] = {}
        self._text_bytes = 0

    async def _validate_artifact(
        self, user_id: str, matter_id: str, key: str, version: str, sha256: str = ""
    ) -> None:
        pin = (user_id, matter_id, key, version, sha256)
        if pin in self._validated:
            return
        data = await self._storage.get(key, version=version)
        if sha256 and hashlib.sha256(data).hexdigest() != sha256:
            raise DomainRuleError("The evidence hash does not match its original.")
        # Do not retain original/image bytes or failures. Bound metadata too.
        if len(self._validated) < 2048:
            self._validated.add(pin)

    async def _read_text(
        self, user_id: str, matter_id: str, key: str, version: str, source_hash: str
    ) -> str:
        pin = (user_id, matter_id, key, version, source_hash)
        if pin in self._texts:
            return self._texts[pin]
        data = await self._storage.get(key, version=version)
        text = data.decode("utf-8")
        if self._text_bytes + len(data) <= 8 * 1024 * 1024 and len(self._texts) < 2048:
            self._texts[pin] = text
            self._text_bytes += len(data)
        return text

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
                    SourceFileRow,
                    SourceFileRow.id
                    == func.coalesce(
                        ProcessingCandidateFieldRow.source_file_id,
                        ProcessingLogicalDocumentRow.source_file_id,
                    ),
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
            logical.interpretation_generation,
        )
        current = source.state == "PROCESSED" and source.superseded_by_source_file_id is None
        document = (
            await self._session.get(DetectedDocumentRow, logical.detected_document_id)
            if logical.detected_document_id
            else None
        )
        current = bool(
            current
            and document
            and document.user_id == user_id
            and document.matter_id == matter_id
            and document.interpretation_generation == logical.interpretation_generation
            and document.class_id == logical.type_id
            and document.extraction_state == "current"
            and document.version_relationship != "SUPERSEDED"
        )
        if current and document:
            fragments = list(
                (
                    await self._session.execute(
                        select(DocumentFragmentRow)
                        .where(
                            DocumentFragmentRow.user_id == user_id,
                            DocumentFragmentRow.matter_id == matter_id,
                            DocumentFragmentRow.detected_document_id == document.id,
                        )
                        .order_by(DocumentFragmentRow.order_in_document)
                    )
                ).scalars()
            )
            expected_pages = [
                (fragment.source_file_id, page)
                for fragment in fragments
                for page in range(fragment.page_start, fragment.page_end + 1)
            ]
            actual_pages = (
                [(page["source_file_id"], page["page_number"]) for page in logical.page_sources]
                if logical.page_sources is not None
                else [(logical.source_file_id, page) for page in logical.page_numbers]
            )
            current = expected_pages == actual_pages
            for source_id in {fragment.source_file_id for fragment in fragments}:
                original = await self._session.get(SourceFileRow, source_id)
                if (
                    original is None
                    or original.user_id != user_id
                    or original.matter_id != matter_id
                    or original.state != "PROCESSED"
                    or original.superseded_by_source_file_id
                ):
                    current = False
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
            generation = evidence.interpretation_generation
            # Legacy pins belong to the initial interpretation only. Omitting a
            # generation must never resurrect an old extraction after a correction.
            if generation is None and evidence.extraction_run_id:
                generation = 1
            if generation is not None and generation != document.interpretation_generation:
                raise DomainRuleError("The evidence interpretation is stale.")
            evidence = replace(
                evidence, interpretation_generation=document.interpretation_generation
            )
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
                    or logical.interpretation_generation != document.interpretation_generation
                    or document.extraction_state != "current"
                    or logical.type_id != document.class_id
                    or (
                        [(p["source_file_id"], p["page_number"]) for p in logical.page_sources]
                        if logical.page_sources is not None
                        else [(logical.source_file_id, page) for page in logical.page_numbers]
                    )
                    != [
                        (f.source_file_id, page)
                        for f in sorted(fragments, key=lambda item: item.order_in_document)
                        for page in range(f.page_start, f.page_end + 1)
                    ]
                ):
                    raise DomainRuleError(
                        "The evidence interpretation requires refreshed extraction."
                    )
        try:
            await self._validate_artifact(
                user_id,
                matter_id,
                source.storage_object_key,
                source.storage_object_version,
                evidence.source_sha256,
            )
            page_text = ""
            if evidence.extraction_run_id:
                page_id = None
                if evidence.detected_document_id and logical is not None and logical.page_sources:
                    page_id = next(
                        (
                            p["page_id"]
                            for p in logical.page_sources
                            if p["source_file_id"] == source.id
                            and p["page_number"] == evidence.page_number
                        ),
                        None,
                    )
                page_query = select(DocumentProcessingPageRow).where(
                    DocumentProcessingPageRow.user_id == user_id,
                    DocumentProcessingPageRow.matter_id == matter_id,
                    DocumentProcessingPageRow.source_file_id == source.id,
                    DocumentProcessingPageRow.page_no == evidence.page_number,
                )
                page_query = (
                    page_query.where(DocumentProcessingPageRow.id == page_id)
                    if page_id
                    else page_query.where(
                        DocumentProcessingPageRow.processing_run_id == evidence.extraction_run_id
                    )
                )
                page = (await self._session.execute(page_query)).scalar_one_or_none()
                if page is None:
                    raise DomainRuleError("The evidence page artifact is unavailable.")
                await self._validate_artifact(
                    user_id, matter_id, page.corrected_webp_key, page.corrected_webp_version
                )
                try:
                    page_text = await self._read_text(
                        user_id,
                        matter_id,
                        page.plain_text_key,
                        page.plain_text_version,
                        evidence.source_sha256,
                    )
                except _ARTIFACT_ERRORS:
                    # OCR is optional. The pinned original and page remain
                    # readable; no text/span authority is invented on fallback.
                    page_text = ""
        except _ARTIFACT_ERRORS as exc:
            raise DomainRuleError("The evidence artifact is unavailable.") from exc
        snippet = evidence.snippet if evidence.snippet and evidence.snippet in page_text else None
        return FactEvidenceSource(
            replace(evidence, snippet=snippet), page_text, snippet, "text" if snippet else "page"
        )

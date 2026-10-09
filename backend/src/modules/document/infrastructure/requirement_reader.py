"""Document-owned current interpretation and immutable-original binding checks."""

from sqlalchemy import select

from src.modules.document.contracts import (
    FactEvidenceLocator,
    OriginalSourcePin,
    RequirementDocument,
)
from src.modules.document.infrastructure.fact_reader import SqlDocumentFactReader
from src.modules.document.infrastructure.orm import (
    DetectedDocumentRow,
    DocumentFragmentRow,
    SourceFileRow,
)
from src.platform.errors import DomainRuleError, NotFoundError


class SqlRequirementDocumentReader(SqlDocumentFactReader):
    async def requirement_document(
        self, user_id: str, matter_id: str, document_id: str
    ) -> RequirementDocument:
        document = (
            await self._session.execute(
                select(DetectedDocumentRow)
                .where(
                    DetectedDocumentRow.user_id == user_id,
                    DetectedDocumentRow.matter_id == matter_id,
                    DetectedDocumentRow.id == document_id,
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if document is None:
            raise NotFoundError()
        if document.version_relationship == "SUPERSEDED" or document.class_status == "REJECTED":
            raise DomainRuleError("The offered document is no longer current.")
        fragments = (
            (
                await self._session.execute(
                    select(DocumentFragmentRow)
                    .where(
                        DocumentFragmentRow.user_id == user_id,
                        DocumentFragmentRow.matter_id == matter_id,
                        DocumentFragmentRow.detected_document_id == document_id,
                    )
                    .order_by(DocumentFragmentRow.order_in_document)
                )
            )
            .scalars()
            .all()
        )
        if not fragments:
            raise DomainRuleError("The offered document has no bound original pages.")
        pins = set()
        pages = []
        for fragment in fragments:
            source = (
                await self._session.execute(
                    select(SourceFileRow).where(
                        SourceFileRow.id == fragment.source_file_id,
                        SourceFileRow.user_id == user_id,
                        SourceFileRow.matter_id == matter_id,
                    )
                )
            ).scalar_one_or_none()
            if source is None:
                raise NotFoundError()
            for page in range(fragment.page_start, fragment.page_end + 1):
                locator = FactEvidenceLocator(
                    source.id,
                    page,
                    source.sha256,
                    detected_document_id=document_id,
                    interpretation_generation=document.interpretation_generation,
                )
                # A manually readable original does not require successful automated extraction.
                await self.validate_evidence(user_id, matter_id, locator)
                pages.append(locator)
            pins.add(OriginalSourcePin(source.id, source.sha256, source.storage_object_version))
        return RequirementDocument(
            document.id,
            document.version,
            document.interpretation_generation,
            document.class_id,
            document.class_status == "LAWYER_CONFIRMED"
            and document.boundary_status == "CONFIRMED"
            and all(fragment.boundary_status == "CONFIRMED" for fragment in fragments),
            tuple(sorted(pins)),
            tuple(pages),
        )

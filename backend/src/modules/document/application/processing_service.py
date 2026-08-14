"""Document processing orchestration (document-processing.md §2).

Coordinates rasterize → classify → extract → validate through ports; imports
no provider SDK. The same service will be called by the ``document.process``
worker job once the outbox/worker runtime exists (jobs-and-workers.md §5) —
the interim synchronous API route and the future worker share this exact code.

Honesty rules implemented here (§8):
- everything produced is a candidate; nothing is auto-accepted;
- model-reported confidence routes to review, it never validates;
- each field records which provider produced it;
- provenance is page-level and never fabricated.
"""

from __future__ import annotations

import structlog

from src.modules.document.domain.models import ProcessingOutcome, ProcessingReport
from src.modules.document.domain.registry import get_template
from src.modules.document.ports import (
    CandidateField,
    ClassifierPort,
    OcrExtractorPort,
    RasterizerPort,
)
from src.platform.config import get_settings

log = structlog.get_logger(__name__)

#: Reason codes carried on manual_review outcomes — machine-readable so the
#: UI and later the worker can branch without parsing prose.
REASON_DATA_APPROVAL = "provider-data-approval-missing"
REASON_LOW_CONFIDENCE = "classification-below-threshold"
REASON_UNREGISTERED_KIND = "no-template-for-kind"


class DocumentProcessingService:
    """The pipeline behind DocumentProcessingPort."""

    def __init__(
        self,
        *,
        rasterizer: RasterizerPort,
        classifier: ClassifierPort,
        extractor: OcrExtractorPort,
        provider_name: str,
    ) -> None:
        self._rasterizer = rasterizer
        self._classifier = classifier
        self._extractor = extractor
        self._provider_name = provider_name

    async def process(
        self,
        data: bytes,
        mime_type: str,
        *,
        synthetic: bool,
        correlation_id: str = "",
    ) -> ProcessingReport:
        settings = get_settings()

        # §10A data-protection gate: while provider approval is unrecorded,
        # real client documents never reach a cloud provider. Routing to
        # manual review is a legitimate state, not an error — and it happens
        # BEFORE rasterization so no derivative of a refused document exists.
        if not settings.provider_data_approval and not synthetic:
            log.info(
                "document.processing.refused",
                reason=REASON_DATA_APPROVAL,
                correlation_id=correlation_id,
            )
            return ProcessingReport(
                outcome=ProcessingOutcome.MANUAL_REVIEW,
                kind="other",
                kind_model_confidence=0.0,
                page_count=0,
                provider=self._provider_name,
                reasons=[REASON_DATA_APPROVAL],
            )

        pages = self._rasterizer.rasterize(data, mime_type)

        classification = await self._classifier.classify(pages[0])
        ai_calls = 1

        template = get_template(classification.kind)
        below_threshold = classification.model_reported_confidence < settings.confidence_threshold
        if template is None or below_threshold:
            # Never guess (§5 Level 3): an unknown or uncertain kind goes to a
            # human with the page shown, not to an extractor.
            reasons = []
            if below_threshold:
                reasons.append(REASON_LOW_CONFIDENCE)
            if template is None:
                reasons.append(REASON_UNREGISTERED_KIND)
            self._log_meters(ai_calls, len(pages), correlation_id)
            return ProcessingReport(
                outcome=ProcessingOutcome.MANUAL_REVIEW,
                kind=classification.kind,
                kind_model_confidence=classification.model_reported_confidence,
                page_count=len(pages),
                provider=self._provider_name,
                reasons=reasons,
                ai_extraction_calls=ai_calls,
                pages_processed=len(pages),
            )

        # Extract page by page so every candidate carries a true page number —
        # the only provenance a boxless engine can honestly claim.
        merged: dict[str, CandidateField] = {}
        transcripts: dict[int, str] = {}
        for page in pages:
            result = await self._extractor.extract(page, template.kind)
            ai_calls += 1
            transcripts[page.page_no] = result.transcript
            normalized = template.normalize_fields(dict(result.fields))
            for key, value in normalized.items():
                if value is None or key in merged:
                    continue  # first non-null reading wins; conflicts are
                    # a reconciliation feature that needs a second engine
                merged[key] = CandidateField(
                    key=key,
                    value=value,
                    page_no=page.page_no,
                    source=self._provider_name,
                    model_reported_confidence=result.model_reported_confidence,
                    format_valid=template.validate_field(key, value),
                )

        self._log_meters(ai_calls, len(pages), correlation_id)
        return ProcessingReport(
            outcome=ProcessingOutcome.EXTRACTED,
            kind=template.kind,
            kind_model_confidence=classification.model_reported_confidence,
            page_count=len(pages),
            provider=self._provider_name,
            fields=list(merged.values()),
            transcripts=transcripts,
            ai_extraction_calls=ai_calls,
            pages_processed=len(pages),
        )

    def _log_meters(self, ai_calls: int, pages: int, correlation_id: str) -> None:
        # §10A metering, v1 interim: the billing module does not exist yet, so
        # this structured log line IS the meter. When billing lands these
        # become ai_extraction_calls.monthly / document_pages.monthly consumes.
        log.info(
            "document.processing.metering",
            ai_extraction_calls=ai_calls,
            pages_processed=pages,
            provider=self._provider_name,
            correlation_id=correlation_id,
        )

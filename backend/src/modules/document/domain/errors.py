"""Domain errors for document processing."""

from __future__ import annotations

from src.platform.errors import DomainRuleError

__all__ = [
    "ExtractionProviderError",
    "UnsupportedDocumentError",
]


class UnsupportedDocumentError(DomainRuleError):
    """The file type cannot be read by the pipeline (rejected to manual entry)."""

    code = "document_unsupported"
    http_status = 422
    message = "This file type is not supported for automatic extraction."


class ExtractionProviderError(DomainRuleError):
    """The extraction provider failed after retries.

    Deliberately carries no provider response text: raw provider errors can
    embed request payload fragments, and error envelopes reach the client.
    """

    code = "extraction_provider_failed"
    http_status = 502
    message = "The document extraction provider is unavailable."

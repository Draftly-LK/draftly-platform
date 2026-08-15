"""Composition root — wires ports to their infrastructure adapters.

This is the only place in the codebase that imports both a port and its
concrete adapter. Application services depend on protocols (ports), never on
specific adapters (infrastructure.md §Principle: provider-neutral behind ports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from src.modules.auth.ports import IdentityPort
from src.platform.config import get_settings

if TYPE_CHECKING:
    from src.modules.document.application.processing_service import (
        DocumentProcessingService,
    )


def register_routers(app: FastAPI) -> None:
    """Mount all module routers under /api/v1."""
    from src.modules.auth.api.router import router as auth_router
    from src.modules.document.api.router import router as document_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(document_router, prefix="/api/v1")


"""Environments where stub adapters may be selected at all.

Stubs bypass real providers (any bearer token becomes a fixed identity; canned
extraction results), so they are confined to developer machines and CI.
Anywhere else, incomplete provider configuration is a startup failure rather
than an open door.
"""
STUB_IDENTITY_ENVIRONMENTS = frozenset({"local", "test", "ci"})
STUB_EXTRACTION_ENVIRONMENTS = STUB_IDENTITY_ENVIRONMENTS


def build_identity_adapter() -> IdentityPort:
    """Return the appropriate IdentityPort implementation for this environment."""
    settings = get_settings()
    stub_allowed = settings.environment in STUB_IDENTITY_ENVIRONMENTS

    if settings.use_stub_identity:
        if not stub_allowed:
            raise RuntimeError(
                f"USE_STUB_IDENTITY is not permitted in environment "
                f"'{settings.environment}'. The stub adapter accepts any bearer "
                f"token as a fixed identity and is limited to "
                f"{sorted(STUB_IDENTITY_ENVIRONMENTS)}."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    if not settings.clerk_configured:
        if not stub_allowed:
            raise RuntimeError(
                f"Clerk identity is not configured and environment "
                f"'{settings.environment}' does not permit the stub adapter. "
                f"Set CLERK_ISSUER, CLERK_SECRET_KEY and CLERK_AUTHORIZED_PARTY."
            )
        from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

        return StubIdentityAdapter()

    from src.modules.auth.infrastructure.clerk_adapter import ClerkIdentityAdapter

    if not settings.clerk_authorized_party:
        raise RuntimeError("CLERK_AUTHORIZED_PARTY is required when Clerk identity is enabled.")
    return ClerkIdentityAdapter(
        issuer=settings.clerk_issuer,
        secret_key=settings.clerk_secret_key,
        audience=settings.clerk_audience or None,
        authorized_party=settings.clerk_authorized_party,
    )


def build_processing_service() -> DocumentProcessingService:
    """Assemble the document-processing pipeline for this environment.

    Same fail-closed posture as identity: the stub is confined to
    local/test/ci, and selecting Gemini without an API key fails at once
    rather than at the first document.
    """
    from src.modules.document.application.processing_service import (
        DocumentProcessingService,
    )
    from src.modules.document.infrastructure.rasterizer_pypdfium import (
        PypdfiumRasterizer,
    )

    settings = get_settings()
    rasterizer = PypdfiumRasterizer(dpi=settings.raster_dpi)

    if settings.extraction_provider == "stub":
        if settings.environment not in STUB_EXTRACTION_ENVIRONMENTS:
            raise RuntimeError(
                f"EXTRACTION_PROVIDER=stub is not permitted in environment "
                f"'{settings.environment}'. The stub returns canned candidate "
                f"fields and is limited to {sorted(STUB_EXTRACTION_ENVIRONMENTS)}."
            )
        from src.modules.document.infrastructure.stub_adapter import (
            StubExtractionAdapter,
        )

        stub = StubExtractionAdapter()
        return DocumentProcessingService(
            rasterizer=rasterizer,
            classifier=stub,
            extractor=stub,
            provider_name="stub",
        )

    if settings.extraction_provider != "gemini":
        raise RuntimeError(
            f"Unknown EXTRACTION_PROVIDER '{settings.extraction_provider}'. Valid: gemini, stub."
        )
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required when EXTRACTION_PROVIDER=gemini.")

    from google import genai

    from src.modules.document.infrastructure.gemini_adapter import (
        GeminiExtractionAdapter,
    )

    adapter = GeminiExtractionAdapter(
        client=genai.Client(api_key=settings.gemini_api_key),
        classify_model=settings.gemini_classify_model,
        extract_model=settings.gemini_extract_model,
    )
    return DocumentProcessingService(
        rasterizer=rasterizer,
        classifier=adapter,
        extractor=adapter,
        provider_name="gemini",
    )

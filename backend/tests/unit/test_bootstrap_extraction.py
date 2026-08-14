"""The extraction stub must never be reachable outside local/test/ci, and a
Gemini selection without an API key must fail at startup — same posture as
the identity adapter (test_bootstrap_identity.py)."""

from __future__ import annotations

import pytest

import src.platform.config as config
from src.bootstrap import STUB_EXTRACTION_ENVIRONMENTS, build_processing_service
from src.modules.document.infrastructure.stub_adapter import StubExtractionAdapter

DEPLOYED_ENVIRONMENTS = ["staging", "production"]


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    config._settings = None


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_stub_extraction_is_refused_when_deployed(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, EXTRACTION_PROVIDER="stub")
    with pytest.raises(RuntimeError, match="EXTRACTION_PROVIDER=stub"):
        build_processing_service()


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS + ["local"])
def test_gemini_without_api_key_fails_startup(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT=environment,
        EXTRACTION_PROVIDER="gemini",
        GEMINI_API_KEY="",
    )
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_processing_service()


def test_unknown_provider_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, ENVIRONMENT="local", EXTRACTION_PROVIDER="tesseract")
    with pytest.raises(RuntimeError, match="Unknown EXTRACTION_PROVIDER"):
        build_processing_service()


@pytest.mark.parametrize("environment", sorted(STUB_EXTRACTION_ENVIRONMENTS))
def test_stub_is_permitted_in_local_and_ci(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, EXTRACTION_PROVIDER="stub")
    service = build_processing_service()
    assert isinstance(service._classifier, StubExtractionAdapter)  # noqa: SLF001

"""Unit tests for the Gemini adapter with a faked client — no network.

The reverted d0fbd00 pipeline never tested its retry policy; these close that
gap: 429 with a retry hint retries and succeeds, daily quota fails fast,
non-quota errors raise immediately, and unparseable output is a typed error.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from google.genai.errors import ClientError

from src.modules.document.domain.errors import ExtractionProviderError
from src.modules.document.infrastructure.gemini_adapter import (
    GeminiExtractionAdapter,
    _ClassifyResponse,
    _ExtractResponse,
)
from src.modules.document.ports import PageRaster

PAGE = PageRaster(page_no=1, png_bytes=b"png", width_px=100, height_px=140, dpi=200)


def _client_error(message: str, status: int = 429) -> ClientError:
    error = ClientError.__new__(ClientError)
    Exception.__init__(error, message)
    error.status_code = status  # type: ignore[attr-defined]
    return error


class FakeModels:
    """Scripted generate_content: raises queued errors, then returns."""

    def __init__(self, *, errors: list[Exception] | None = None, parsed: object = None) -> None:
        self._errors = list(errors or [])
        self._parsed = parsed
        self.calls = 0

    def generate_content(self, **_kwargs: object) -> SimpleNamespace:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        return SimpleNamespace(parsed=self._parsed)


def make_adapter(models: FakeModels) -> GeminiExtractionAdapter:
    client = SimpleNamespace(models=models)
    return GeminiExtractionAdapter(
        client=client,  # type: ignore[arg-type]
        classify_model="test-classify",
        extract_model="test-extract",
    )


@pytest.fixture(autouse=True)
def _no_sleep():
    async def instant(_seconds: float) -> None:
        return None

    with patch(
        "src.modules.document.infrastructure.gemini_adapter.asyncio.sleep",
        new=instant,
    ):
        yield


class TestClassify:
    async def test_happy_path_parses_schema(self):
        models = FakeModels(parsed=_ClassifyResponse(kind="form8-instrument", confidence=0.92))
        result = await make_adapter(models).classify(PAGE)
        assert result.kind == "form8-instrument"
        assert result.model_reported_confidence == pytest.approx(0.92)

    async def test_unknown_kind_collapses_to_other(self):
        models = FakeModels(parsed=_ClassifyResponse(kind="martian-deed", confidence=0.9))
        result = await make_adapter(models).classify(PAGE)
        assert result.kind == "other"

    async def test_unparseable_response_is_a_typed_error(self):
        models = FakeModels(parsed=None)
        with pytest.raises(ExtractionProviderError):
            await make_adapter(models).classify(PAGE)


class TestExtract:
    async def test_happy_path(self):
        models = FakeModels(
            parsed=_ExtractResponse(
                transcript="text",
                confidence=0.8,
                fields={"district": "Colombo", "extent": None},
            )
        )
        result = await make_adapter(models).extract(PAGE, "form8-instrument")
        assert result.fields["district"] == "Colombo"
        assert result.transcript == "text"

    async def test_unregistered_kind_is_refused_without_a_call(self):
        models = FakeModels(parsed=None)
        with pytest.raises(ExtractionProviderError):
            await make_adapter(models).extract(PAGE, "unknown-kind")
        assert models.calls == 0


class TestRetryPolicy:
    async def test_rate_limit_retries_then_succeeds(self):
        models = FakeModels(
            errors=[
                _client_error("RESOURCE_EXHAUSTED: retry in 2s"),
                _client_error("RESOURCE_EXHAUSTED: retry in 2s"),
            ],
            parsed=_ClassifyResponse(kind="survey-plan", confidence=0.7),
        )
        result = await make_adapter(models).classify(PAGE)
        assert result.kind == "survey-plan"
        assert models.calls == 3

    async def test_exhausted_attempts_raise_typed_error(self):
        models = FakeModels(errors=[_client_error("RESOURCE_EXHAUSTED") for _ in range(3)])
        with pytest.raises(ExtractionProviderError):
            await make_adapter(models).classify(PAGE)
        assert models.calls == 3

    async def test_daily_quota_fails_fast_without_retry(self):
        models = FakeModels(
            errors=[
                _client_error(
                    "RESOURCE_EXHAUSTED: GenerateRequestsPerDayPerProject "
                    "quotaValue exceeded, retry in 43000s"
                )
            ],
            parsed=_ClassifyResponse(kind="survey-plan", confidence=0.7),
        )
        with pytest.raises(ExtractionProviderError):
            await make_adapter(models).classify(PAGE)
        assert models.calls == 1

    async def test_non_quota_client_error_raises_immediately(self):
        models = FakeModels(
            errors=[_client_error("invalid model id", status=404)],
            parsed=_ClassifyResponse(kind="survey-plan", confidence=0.7),
        )
        with pytest.raises(ExtractionProviderError):
            await make_adapter(models).classify(PAGE)
        assert models.calls == 1

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
    _BatchClassificationResponse,
    _CandidateItem,
    _ClassifyResponse,
    _DocumentExtractionResponse,
    _ExtractFieldItem,
    _ExtractResponse,
    _PageClassificationItem,
)
from src.modules.document.ports import ClassificationPageInput, ExtractionFieldSchema, PageRaster

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
        self.last_kwargs: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls += 1
        self.last_kwargs = kwargs
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
                fields=[
                    _ExtractFieldItem(key="district", value="Colombo"),
                    _ExtractFieldItem(key="extent", value=None),
                ],
            )
        )
        result = await make_adapter(models).extract(PAGE, "form8-instrument")
        assert result.fields["district"] == "Colombo"
        assert result.transcript == "text"

    def test_schema_avoids_developer_api_additional_properties(self):
        assert "additionalProperties" not in str(_ExtractResponse.model_json_schema())

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

    async def test_local_schema_value_error_is_a_typed_provider_failure(self):
        models = FakeModels(errors=[ValueError("unsupported schema detail")])
        with pytest.raises(ExtractionProviderError):
            await make_adapter(models).extract(PAGE, "form8-instrument")
        assert models.calls == 1


async def test_v1_classification_is_one_structured_call() -> None:
    models = FakeModels(
        parsed=_BatchClassificationResponse(
            pages=[
                _PageClassificationItem(
                    page_no=1,
                    type_id="rta.doc.title_certificate",
                    starts_new_document=True,
                    model_reported_confidence=0.9,
                ),
                _PageClassificationItem(
                    page_no=2,
                    type_id="other",
                    suggested_name="Cover letter",
                    starts_new_document=True,
                    model_reported_confidence=0.7,
                ),
            ]
        )
    )
    result = await make_adapter(models).classify_pages(
        [
            ClassificationPageInput(1, "title", "normal"),
            ClassificationPageInput(2, "letter", "ocr_sparse"),
        ],
        allowed_type_ids=("rta.doc.title_certificate",),
        text_limit=300,
    )
    assert models.calls == 1
    assert [item.type_id for item in result] == ["rta.doc.title_certificate", "other"]
    assert result[1].suggested_name == "Cover letter"
    assert "Registration of Title Act certificate" in str(models.last_kwargs["contents"])


async def test_v1_extraction_preserves_exact_strings_and_filters_schema() -> None:
    models = FakeModels(
        parsed=_DocumentExtractionResponse(
            fields=[
                _CandidateItem(
                    key="parcelNo",
                    value="0020-A",
                    page_no=2,
                    model_reported_confidence=0.83,
                ),
                _CandidateItem(
                    key="invented",
                    value="drop me",
                    page_no=2,
                    model_reported_confidence=0.99,
                ),
            ]
        )
    )
    result = await make_adapter(models).extract_document(
        type_id="rta.doc.title_certificate",
        text="<<<PAGE 2>>>\nParcel: 0020-A",
        page_numbers=(2,),
        fields=(ExtractionFieldSchema("parcelNo", "Parcel number"),),
    )
    assert models.calls == 1
    assert len(result) == 1
    assert result[0].value == "0020-A"

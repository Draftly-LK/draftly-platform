"""Unit tests for two-stage Gemini classify → extract pipeline (mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from draftly_api.pipeline.gemini import (
    ClassificationResult,
    ExtractionResult,
    classify_document,
    extract_document,
)
from draftly_api.pipeline.registry import (
    classification_prompt,
    get_template,
    identity_template,
    registered_kinds,
    side_from_filename,
)
from draftly_api.settings import Settings


def _settings() -> Settings:
    return Settings(
        gemini_api_key="test-key",
        gemini_classify_model="gemini-3.1-flash-lite",
        gemini_extract_model="gemini-2.5-flash",
        confidence_threshold=0.55,
    )


def _fake_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


class TestRegistry:
    def test_registered_kinds_identity_only(self) -> None:
        assert registered_kinds() == ["identity"]
        assert get_template("identity") is not None
        assert get_template("deed") is None

    def test_classification_prompt_lists_identity(self) -> None:
        prompt = classification_prompt()
        assert '"identity"' in prompt
        assert '"other"' in prompt
        assert "National Identity Card" in prompt

    def test_identity_normalize_fields_rejects_undetected(self) -> None:
        template = identity_template()
        fields = template.normalize_fields(
            {
                "nicNumber": "123456789V",
                "nameEn": "undetected",
                "sex": "null",
                "dateOfBirth": "  ",
            }
        )
        assert fields["nicNumber"] == "123456789V"
        assert fields["nameEn"] is None
        assert fields["sex"] is None
        assert fields["dateOfBirth"] is None

    def test_side_from_filename(self) -> None:
        assert side_from_filename("nic1f.jpg") == "front"
        assert side_from_filename("nic2b.jpeg") == "back"
        assert side_from_filename("mystery.png") == "unknown"


class TestClassifyDocument:
    @patch("draftly_api.pipeline.gemini._generate_with_retry")
    @patch("draftly_api.pipeline.gemini.genai.Client")
    def test_parses_identity_classification(
        self,
        mock_client: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = _fake_response(
            '{"kind":"identity","side":"front","confidence":0.91}'
        )
        result = classify_document(
            image_bytes=b"fake",
            mime_type="image/jpeg",
            settings=_settings(),
        )
        assert result.kind == "identity"
        assert result.side == "front"
        assert result.confidence == pytest.approx(0.91)

    @patch("draftly_api.pipeline.gemini._generate_with_retry")
    @patch("draftly_api.pipeline.gemini.genai.Client")
    def test_unknown_kind_becomes_other(
        self,
        mock_client: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = _fake_response(
            '{"kind":"deed","side":"front","confidence":0.99}'
        )
        result = classify_document(
            image_bytes=b"fake",
            mime_type="image/jpeg",
            settings=_settings(),
        )
        assert result.kind == "other"
        assert result.side == "unknown"

    @patch("draftly_api.pipeline.gemini._generate_with_retry")
    @patch("draftly_api.pipeline.gemini.genai.Client")
    def test_malformed_json_returns_other(
        self,
        mock_client: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = _fake_response("not-json")
        result = classify_document(
            image_bytes=b"fake",
            mime_type="image/jpeg",
            settings=_settings(),
        )
        assert result == ClassificationResult(
            kind="other",
            side="unknown",
            confidence=0.0,
            raw_text="not-json",
        )


class TestExtractDocument:
    @patch("draftly_api.pipeline.gemini._generate_with_retry")
    @patch("draftly_api.pipeline.gemini.genai.Client")
    def test_parses_identity_extraction(
        self,
        mock_client: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = _fake_response(
            """
            {
              "side": "front",
              "confidence": 0.88,
              "extracted_text": "NATIONAL IDENTITY CARD",
              "fields": {
                "nicNumber": "SYNTHETIC-001",
                "nameEn": "Synthetic Person",
                "nameSi": null,
                "sex": "Male",
                "dateOfBirth": null,
                "addressEn": null,
                "serialNumber": null,
                "dateOfIssue": null,
                "placeOfBirthEn": null
              }
            }
            """
        )
        result = extract_document(
            image_bytes=b"fake",
            mime_type="image/jpeg",
            template=identity_template(),
            settings=_settings(),
        )
        assert result.side == "front"
        assert result.confidence == pytest.approx(0.88)
        assert result.extracted_text == "NATIONAL IDENTITY CARD"
        assert result.fields["nicNumber"] == "SYNTHETIC-001"
        assert result.fields["nameEn"] == "Synthetic Person"
        assert result.fields["dateOfBirth"] is None

    @patch("draftly_api.pipeline.gemini._generate_with_retry")
    @patch("draftly_api.pipeline.gemini.genai.Client")
    def test_malformed_json_returns_empty_fields(
        self,
        mock_client: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_generate.return_value = _fake_response("{broken")
        result = extract_document(
            image_bytes=b"fake",
            mime_type="image/jpeg",
            template=identity_template(),
            settings=_settings(),
        )
        assert isinstance(result, ExtractionResult)
        assert result.extracted_text == ""
        assert result.fields["nicNumber"] is None
        assert result.confidence == 0.0


class TestProcessEndpoint:
    @patch("draftly_api.main.extract_document")
    @patch("draftly_api.main.classify_document")
    def test_other_skips_extraction(
        self,
        mock_classify: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient

        from draftly_api.main import app

        mock_classify.return_value = ClassificationResult(
            kind="other",
            side="unknown",
            confidence=0.9,
        )
        client = TestClient(app)
        response = client.post(
            "/api/documents/process",
            files={"file": ("mystery.jpg", b"fake-bytes", "image/jpeg")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["kind"] == "other"
        assert body["relation"] == "unclassified"
        assert body["extracted_fields"] == {}
        mock_extract.assert_not_called()

    @patch("draftly_api.main.extract_document")
    @patch("draftly_api.main.classify_document")
    def test_low_confidence_skips_extraction(
        self,
        mock_classify: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient

        from draftly_api.main import app

        mock_classify.return_value = ClassificationResult(
            kind="identity",
            side="front",
            confidence=0.2,
        )
        client = TestClient(app)
        response = client.post(
            "/api/documents/process",
            files={"file": ("nic1f.jpg", b"fake-bytes", "image/jpeg")},
        )
        assert response.status_code == 200
        assert response.json()["kind"] == "other"
        mock_extract.assert_not_called()

    @patch("draftly_api.main.extract_document")
    @patch("draftly_api.main.classify_document")
    def test_identity_pipeline_merges_filename_side(
        self,
        mock_classify: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        from fastapi.testclient import TestClient

        from draftly_api.main import app

        mock_classify.return_value = ClassificationResult(
            kind="identity",
            side="unknown",
            confidence=0.9,
        )
        mock_extract.return_value = ExtractionResult(
            side="front",
            confidence=0.85,
            extracted_text="NATIONAL IDENTITY CARD",
            fields=identity_template().normalize_fields(
                {"nicNumber": "SYNTH-1", "nameEn": "Synthetic Person"}
            ),
        )
        client = TestClient(app)
        response = client.post(
            "/api/documents/process",
            files={"file": ("nic2b.jpeg", b"fake-bytes", "image/jpeg")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["kind"] == "identity"
        assert body["relation"] == "authorized"
        assert body["identity_side"] == "back"  # filename hint wins
        assert body["display_name"] == "Synthetic Person's identity card"
        assert "ocr_confidence" not in body
        mock_extract.assert_called_once()

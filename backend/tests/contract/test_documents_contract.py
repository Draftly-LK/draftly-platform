"""Contract tests: POST /api/v1/documents/process wire shape and gates.

Runs the real FastAPI app with the stub extraction adapter and an overridden
auth context — no network, no database, no Gemini.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_request_context
from src.main import create_app
from src.modules.auth.domain.models import Role
from src.modules.document.api.router import get_processing_service
from src.modules.document.application.processing_service import (
    DocumentProcessingService,
)
from src.modules.document.infrastructure.rasterizer_pypdfium import (
    PypdfiumRasterizer,
)
from src.modules.document.infrastructure.stub_adapter import StubExtractionAdapter
from src.platform.request_context import RequestContext

#: PNG-mime bytes carrying the stub's classification marker. The rasterizer
#: passes images through untouched, so the marker survives to the stub.
FORM8_BYTES = b"\x89PNG-fake STUB-KIND:form8-instrument\n rest"
UNKNOWN_BYTES = b"\x89PNG-fake no marker here"


def _ctx() -> RequestContext:
    return RequestContext(
        actor_id="usr_test",
        account_role=Role.APPROVER,
        correlation_id="corr_docs",
    )


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    stub = StubExtractionAdapter()
    service = DocumentProcessingService(
        rasterizer=PypdfiumRasterizer(dpi=200),
        classifier=stub,
        extractor=stub,
        provider_name="stub",
    )
    app.dependency_overrides[get_request_context] = _ctx
    app.dependency_overrides[get_processing_service] = lambda: service
    return TestClient(app)


class TestDocumentsProcessContract:
    def test_requires_authentication(self):
        app = create_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("a.png", FORM8_BYTES, "image/png")},
        )
        assert response.status_code == 401

    def test_happy_path_returns_camel_case_report(self, client: TestClient):
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("form8.png", FORM8_BYTES, "image/png")},
            data={"synthetic": "true"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "extracted"
        assert body["kind"] == "form8-instrument"
        assert body["provider"] == "stub"
        assert body["pageCount"] == 1
        assert body["aiExtractionCalls"] == 2  # classify + 1 page extract
        fields = {f["key"]: f for f in body["fields"]}
        assert fields["district"]["value"] == "Colombo"
        assert fields["district"]["pageNo"] == 1
        assert fields["district"]["source"] == "stub"
        assert "modelReportedConfidence" in fields["district"]
        assert "formatValid" in fields["extent"]
        # Provenance honesty on the wire: no region key exists at all.
        assert "region" not in fields["district"]

    def test_non_synthetic_without_approval_is_manual_review(self, client: TestClient):
        """§10A end to end: a real document under default settings is refused
        into manual review — a 200 state, not an error."""
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("real.png", FORM8_BYTES, "image/png")},
            data={"synthetic": "false"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "manual_review"
        assert body["reasons"] == ["provider-data-approval-missing"]
        assert body["fields"] == []

    def test_unknown_kind_routes_to_manual_review(self, client: TestClient):
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("mystery.png", UNKNOWN_BYTES, "image/png")},
            data={"synthetic": "true"},
        )
        body = response.json()
        assert body["outcome"] == "manual_review"
        assert set(body["reasons"]) == {
            "classification-below-threshold",
            "no-template-for-kind",
        }

    def test_unsupported_mime_is_a_typed_422(self, client: TestClient):
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("doc.docx", b"PK...", "application/vnd.ms-word")},
            data={"synthetic": "true"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "document_unsupported"

    def test_empty_file_is_a_typed_422(self, client: TestClient):
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("empty.png", b"", "image/png")},
            data={"synthetic": "true"},
        )
        assert response.status_code == 422

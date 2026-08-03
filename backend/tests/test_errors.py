"""Tests for the repository-wide privacy-safe error envelope."""

from __future__ import annotations

import pytest
from fastapi import Query
from fastapi.testclient import TestClient
from src.main import create_app
from src.platform.errors import ApiError


def test_validation_error_uses_safe_400_envelope() -> None:
    app = create_app()

    @app.get("/test/validation")
    async def validation_route(limit: int = Query(ge=1, le=10)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get(
            "/test/validation?limit=private-invalid-value",
            headers={"X-Correlation-Id": "corr-validation"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "request_invalid",
            "message": "The request is invalid.",
            "details": {"fields": ["limit"]},
            "correlationId": "corr-validation",
        }
    }
    assert "private-invalid-value" not in response.text


def test_not_found_and_method_not_allowed_use_stable_codes() -> None:
    app = create_app()

    with TestClient(app) as client:
        missing = client.get("/does-not-exist")
        wrong_method = client.post("/health/live")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"


def test_expected_application_error_preserves_safe_details() -> None:
    app = create_app()

    @app.get("/test/refusal")
    async def refusal_route() -> None:
        raise ApiError(
            status_code=403,
            code="capability_denied",
            message="This action requires the draft.approve capability.",
            details={"capability": "draft.approve"},
        )

    with TestClient(app) as client:
        response = client.get("/test/refusal")

    assert response.status_code == 403
    assert response.json()["error"]["details"] == {"capability": "draft.approve"}


def test_unexpected_exception_does_not_leak_message_or_trace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app()

    @app.get("/test/crash")
    async def crash_route() -> None:
        raise RuntimeError("private-secret-value")

    with TestClient(app) as client:
        response = client.get(
            "/test/crash?token=private-query-value",
            headers={"X-Correlation-Id": "corr-crash"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
            "correlationId": "corr-crash",
        }
    }
    captured = capsys.readouterr()
    assert "private-secret-value" not in response.text
    assert "private-secret-value" not in captured.out
    assert "private-query-value" not in captured.out

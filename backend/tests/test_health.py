"""Phase 0 health, readiness, correlation, and request-log tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from src.main import _correlation_id, create_app


def test_liveness_works_without_external_dependencies() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Correlation-Id"].startswith("corr-")


def test_readiness_is_ready_with_no_registered_dependencies() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {}}


def test_readiness_reports_only_safe_dependency_states() -> None:
    async def database_check() -> bool:
        raise RuntimeError("postgresql://user:secret@private-host/database")

    with TestClient(create_app(readiness_checks={"database": database_check})) as client:
        response = client.get("/health/ready", headers={"X-Correlation-Id": "corr-test-ready"})

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "dependency_unavailable",
            "message": "One or more required dependencies are unavailable.",
            "details": {"checks": {"database": "unavailable"}},
            "correlationId": "corr-test-ready",
        }
    }
    assert "private-host" not in response.text
    assert "secret" not in response.text


def test_valid_correlation_id_is_echoed() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/health/live",
            headers={"X-Correlation-Id": "corr-client_123:test"},
        )

    assert response.headers["X-Correlation-Id"] == "corr-client_123:test"


def test_unsafe_correlation_ids_are_replaced() -> None:
    assert _correlation_id("corr-safe") == "corr-safe"
    assert _correlation_id("corr-bad\nforged").startswith("corr-")
    assert _correlation_id("x" * 129).startswith("corr-")
    assert _correlation_id(None).startswith("corr-")


def test_request_log_uses_route_template_and_omits_query_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live?token=private-query-value")

    assert response.status_code == 200
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.splitlines() if line.startswith("{")]
    request_log = next(json.loads(line) for line in log_lines if "http_request_completed" in line)
    assert request_log["route"] == "/health/live"
    assert request_log["method"] == "GET"
    assert request_log["status"] == 200
    assert "private-query-value" not in captured.out

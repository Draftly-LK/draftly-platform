"""SW-3: a fail-closed deployment guard is a 503, not a generic 500.

A deployed environment with no identity provider must refuse every request and
must never fall back to the stub adapter. It should also say so in the typed
error envelope without describing its own configuration to the caller; the
reason belongs in the server log.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator

import pytest
import structlog
from fastapi.testclient import TestClient

import src.platform.config as config
from src.bootstrap import build_identity_adapter
from src.platform.db.session import get_db
from src.platform.errors import DraftlyError, ServiceMisconfiguredError, make_error_response

LEAK_MARKERS = ("CLERK", "USE_STUB", "environment", "production", "stub", "adapter")


async def _no_database() -> AsyncGenerator[object, None]:
    yield object()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from src.main import app

    app.dependency_overrides[get_db] = _no_database
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _deploy_without_clerk(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    env = {
        "ENVIRONMENT": "production",
        "USE_STUB_IDENTITY": "false",
        "CLERK_ISSUER": "",
        "CLERK_SECRET_KEY": "",
        **extra,
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    config._settings = None


def test_error_type_is_typed_503_and_still_a_runtime_error() -> None:
    error = ServiceMisconfiguredError("CLERK_ISSUER is missing")
    assert isinstance(error, DraftlyError)
    assert isinstance(error, RuntimeError)
    assert error.http_status == 503
    assert error.code == "service_misconfigured"
    assert error.reason == "CLERK_ISSUER is missing"
    assert str(error) == "CLERK_ISSUER is missing"
    assert "CLERK" not in error.message


def test_envelope_never_carries_the_reason() -> None:
    response = make_error_response(
        ServiceMisconfiguredError("CLERK_SECRET_KEY is missing"), correlation_id="corr-1"
    )
    assert response.status_code == 503
    body = bytes(response.body).decode()
    assert "CLERK_SECRET_KEY" not in body
    assert '"correlation_id":"corr-1"' in body


def test_missing_clerk_in_production_returns_503_envelope(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _deploy_without_clerk(monkeypatch)

    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer x", "X-Correlation-Id": "corr-sw3"},
    )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "service_misconfigured"
    assert error["correlation_id"] == "corr-sw3"
    assert error["details"] == {}
    assert response.headers["X-Correlation-Id"] == "corr-sw3"
    for marker in LEAK_MARKERS:
        assert marker.lower() not in response.text.lower().replace("service_misconfigured", "")


def test_explicit_stub_in_production_returns_503_not_a_stub_identity(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _deploy_without_clerk(monkeypatch, USE_STUB_IDENTITY="true")

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer anything"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_misconfigured"
    assert "USE_STUB_IDENTITY" not in response.text


def test_detailed_reason_is_logged_server_side(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _deploy_without_clerk(monkeypatch)

    with structlog.testing.capture_logs() as logs:
        client.get("/api/v1/me", headers={"Authorization": "Bearer x"})

    entries = [entry for entry in logs if entry["event"] == "service_misconfigured"]
    assert len(entries) == 1
    assert entries[0]["log_level"] == "error"
    assert entries[0]["path"] == "/api/v1/me"
    assert "Clerk identity is not configured" in entries[0]["reason"]


def test_guard_still_fails_closed_outside_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _deploy_without_clerk(monkeypatch)
    with pytest.raises(ServiceMisconfiguredError, match="Clerk identity is not configured"):
        build_identity_adapter()


def test_unauthenticated_request_is_still_401_when_misconfigured(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """No credentials is the caller's fault and is answered before any adapter is built."""
    _deploy_without_clerk(monkeypatch)
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"

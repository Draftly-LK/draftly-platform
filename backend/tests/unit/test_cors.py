"""CORS allowlist accepts only the exact origins configured by the environment."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import src.platform.config as config
from src.main import create_app

VERCEL = "https://draftly-demo.vercel.app"


def _settings(allowed_origins: str | None = None) -> config.Settings:
    kwargs = {} if allowed_origins is None else {"allowed_origins": allowed_origins}
    return config.Settings(
        database_url="postgresql+psycopg://u:p@localhost/db",
        database_url_direct="postgresql+psycopg://u:p@localhost/db",
        **kwargs,
    )


@pytest.fixture
def use_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(config, "_settings", None)
    yield


def _preflight(client: TestClient, origin: str) -> str | None:
    reply = client.options(
        "/api/v1/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    return reply.headers.get("access-control-allow-origin")


def test_default_allowlist_is_the_local_dev_servers_only() -> None:
    assert _settings().cors_origins == (
        "http://localhost:3000",
        "http://localhost:4310",
    )


def test_allowed_origins_are_trimmed_deduplicated_and_appended() -> None:
    settings = _settings(f" {VERCEL}/ , http://localhost:3000,,https://other.example ")
    assert settings.cors_origins == (
        VERCEL,
        "http://localhost:3000",
        "https://other.example",
    )


def test_configured_origin_passes_preflight(
    use_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "_settings", _settings(VERCEL))
    with TestClient(create_app()) as client:
        assert _preflight(client, VERCEL) == VERCEL


def test_unlisted_origin_gets_no_cors_grant(
    use_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "_settings", _settings(VERCEL))
    with TestClient(create_app()) as client:
        assert _preflight(client, "https://attacker.example") is None
        assert _preflight(client, "https://draftly-demo-git-branch.vercel.app") is None

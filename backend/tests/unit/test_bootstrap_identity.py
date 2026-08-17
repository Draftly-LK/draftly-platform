"""The stub identity adapter must never be reachable outside local/CI.

It accepts any bearer token as one fixed identity, so selecting it in staging
or production would leave the API open. These tests pin that boundary.
"""

from __future__ import annotations

import pytest

import src.platform.config as config
from src.bootstrap import STUB_IDENTITY_ENVIRONMENTS, build_identity_adapter
from src.modules.auth.infrastructure.stub_adapter import StubIdentityAdapter

DEPLOYED_ENVIRONMENTS = ["staging", "production"]


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    config._settings = None


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_explicit_stub_is_refused_when_deployed(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, USE_STUB_IDENTITY="true")
    with pytest.raises(RuntimeError, match="USE_STUB_IDENTITY"):
        build_identity_adapter()


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_missing_clerk_config_fails_startup_when_deployed(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    # Blanked rather than deleted. Settings reads backend/.env directly, so an
    # *unset* variable still falls through to whatever real Clerk credentials a
    # developer has in that file and the test passes vacuously on CI while
    # failing on their machine. An explicit empty value overrides the file and
    # is falsy, which is exactly what `clerk_configured` checks.
    _configure(
        monkeypatch,
        ENVIRONMENT=environment,
        USE_STUB_IDENTITY="false",
        CLERK_ISSUER="",
        CLERK_SECRET_KEY="",
    )
    with pytest.raises(RuntimeError, match="Clerk identity is not configured"):
        build_identity_adapter()


@pytest.mark.parametrize("environment", sorted(STUB_IDENTITY_ENVIRONMENTS))
def test_stub_is_permitted_in_local_and_ci(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, USE_STUB_IDENTITY="true")
    assert isinstance(build_identity_adapter(), StubIdentityAdapter)

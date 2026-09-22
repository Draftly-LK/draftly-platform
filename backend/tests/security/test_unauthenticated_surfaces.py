"""The routes that take no bearer token, each with its own guard (§8.4).

Nothing upstream of these checks a session, so each one has to hold on its
own terms: the health probes carry no data, and a webhook trusts only its
signature.
"""

from __future__ import annotations

import pytest

import src.platform.config as settings_module
import src.platform.db.session as session_module
from src.main import create_app
from tests.security.harness import Harness

#: Every operation the public contract serves without a bearer token. A new
#: one fails this suite until someone has reviewed why it needs no session.
REVIEWED_OPEN_OPERATIONS = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("POST", "/api/v1/billing/webhooks/payhere"),
}

RESEND_WEBHOOK = "/api/v1/notifications/provider-webhooks/resend"
UNREACHABLE_PASSWORD = "synthetic-password-never-logged"


def test_only_reviewed_operations_are_open() -> None:
    spec = create_app().openapi()
    open_operations = {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if not operation.get("security")
    }

    assert open_operations == REVIEWED_OPEN_OPERATIONS


def test_the_resend_webhook_stays_out_of_the_public_contract() -> None:
    assert RESEND_WEBHOOK not in create_app().openapi()["paths"]


async def test_liveness_needs_no_token(harness: Harness) -> None:
    response = await harness.client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture
def unreachable_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the app's own engine at a port nothing listens on.

    ``connect_timeout`` keeps the test quick: Windows retries a refused
    connection for about two minutes. The probe itself sets no timeout, so a
    database that drops packets rather than refusing can hold readiness open
    for as long; how long it may wait is an open operational decision.
    """
    url = (
        f"postgresql+psycopg://synthetic:{UNREACHABLE_PASSWORD}@127.0.0.1:1/draftly"
        "?connect_timeout=1"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    settings_module._settings = None
    monkeypatch.setattr(session_module, "_engine", None)
    monkeypatch.setattr(session_module, "_session_maker", None)


async def test_readiness_is_503_when_the_database_is_unreachable(
    harness: Harness, unreachable_database: None
) -> None:
    """The load balancer ejects an instance on exactly this answer."""
    response = await harness.client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "unreachable"}
    assert UNREACHABLE_PASSWORD not in response.text


@pytest.fixture
def resend_webhook_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "whsec_c3ludGhldGljLXdlYmhvb2stc2VjcmV0")
    settings_module._settings = None


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="unsigned"),
        pytest.param(
            {
                "svix-id": "msg_synthetic",
                "svix-timestamp": "1700000000",
                "svix-signature": "v1,c3ludGhldGljLWZvcmdlZA==",
            },
            id="forged-and-stale",
        ),
    ],
)
async def test_an_unverified_resend_webhook_is_refused_before_any_write(
    harness: Harness, resend_webhook_configured: None, headers: dict[str, str]
) -> None:
    """The harness database fails the test on any query, so a 401 here also
    proves the request was turned away before the service touched storage."""
    response = await harness.client.post(
        RESEND_WEBHOOK,
        content=b'{"type": "email.delivered", "data": {"email_id": "synthetic"}}',
        headers={"Content-Type": "application/json", **headers},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "webhook_verification_failed"

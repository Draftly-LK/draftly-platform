"""L3 service wiring: routers take services from DI, one per request.

The party, notification, obligations, and notarial-register routers used to
read services from module-level globals that were reassigned on every request.
Under concurrency that hands request A the service — and therefore the
AsyncSession — belonging to request B, which breaks the server-side isolation
these modules exist to enforce. These tests pin the request-scoped wiring.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.deps import (
    get_notarial_register_service,
    get_notification_service,
    get_obligations_service,
    get_party_service,
    get_request_context,
)
from src.main import create_app
from src.modules.auth.domain.models import Role
from src.modules.party.application.party_service import PartyListPage
from src.platform.pagination import Page
from src.platform.request_context import RequestContext

L3_ROUTES = [
    "/api/v1/parties",
    "/api/v1/notification-preferences",
]


def _ctx() -> RequestContext:
    return RequestContext(
        actor_id="usr_scoping",
        account_role=Role.APPROVER,
        correlation_id="corr_scoping",
    )


class _FakePartyService:
    """Stands in for PartyService; records the calls the route makes."""

    def __init__(self) -> None:
        self.calls = 0

    async def list_parties(self, ctx, filter_=None):  # noqa: ANN001, ANN202
        self.calls += 1
        return PartyListPage(items=[], page=Page(next_cursor=None, has_more=False, limit=50))


class TestL3RouterRegistration:
    def test_app_boots_with_l3_routers_mounted(self):
        """Registration failures here mean the whole app fails to start."""
        app = create_app()
        paths = set(app.openapi()["paths"])
        for path in L3_ROUTES:
            assert path in paths, f"{path} is not mounted"


class TestServicesComeFromDependencyInjection:
    def test_party_route_uses_the_injected_service(self):
        """A dependency_overrides swap must reach the handler.

        With a module-level global the handler ignored the override and used
        whichever instance the last request left behind.
        """
        app = create_app()
        fake = _FakePartyService()
        app.dependency_overrides[get_request_context] = _ctx
        app.dependency_overrides[get_party_service] = lambda: fake

        response = TestClient(app).get("/api/v1/parties")

        assert response.status_code == 200, response.text
        assert fake.calls == 1
        assert response.json() == {
            "items": [],
            "page": {"nextCursor": None, "hasMore": False, "limit": 50},
        }

    @pytest.mark.parametrize(
        "provider",
        [
            get_party_service,
            get_notification_service,
            get_notarial_register_service,
            get_obligations_service,
        ],
    )
    def test_provider_takes_the_request_session(self, provider):  # noqa: ANN001
        """Each provider must accept the session, not close over a shared one."""
        params = inspect.signature(provider).parameters
        assert "session" in params, f"{provider.__name__} does not take a session"


class TestNoModuleLevelServiceState:
    def test_deps_holds_no_service_singletons(self):
        """Guards against reintroducing cross-request service caching."""
        leaked = [
            name
            for name in vars(deps)
            if name.startswith("_") and name.endswith(("_instance", "_stub", "_org_id"))
        ]
        assert leaked == [], f"module-level service state in api.deps: {leaked}"

"""Fact metadata uses the production authentication chain and no database."""

from src.modules.content_governance.application.rule_pack_export import fact_types_contract
from tests.factories.constants import USER_A
from tests.security.harness import Harness


async def test_catalogue_requires_authentication(harness: Harness) -> None:
    response = await harness.client.get("/api/v1/rta/fact-types")
    assert response.status_code == 401


async def test_catalogue_serializes_existing_metadata_only(harness: Harness) -> None:
    await harness.link("synthetic_catalogue", USER_A)
    response = await harness.client.get(
        "/api/v1/rta/fact-types", headers=harness.signed_in("synthetic_catalogue")
    )
    assert response.status_code == 200
    assert response.json() == fact_types_contract()
    assert "post" not in harness.app.openapi()["paths"]["/api/v1/rta/fact-types"]

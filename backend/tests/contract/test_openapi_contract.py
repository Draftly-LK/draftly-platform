"""The committed OpenAPI schema must match the running app.

``api-conventions.md`` §9: the contract is generated on every build and
committed, so a removed or renamed field fails CI instead of reaching the
frontend. Regenerate with ``uv run python scripts/export_openapi.py``.
"""

from __future__ import annotations

import json

from scripts.export_openapi import CONTRACT_PATH, build_schema, serialise

AGENT_PATHS = {
    "/api/v1/matters/{matter_id}/agent",
    "/api/v1/matters/{matter_id}/agent/messages",
    "/api/v1/agent-jobs/{job_id}",
    "/api/v1/agent-jobs/{job_id}/events",
    "/api/v1/matters/{matter_id}/agent/actions/{action_id}/confirm",
    "/api/v1/matters/{matter_id}/agent/actions/{action_id}/reject",
}


def test_the_committed_schema_matches_the_app() -> None:
    assert CONTRACT_PATH.exists(), "run scripts/export_openapi.py and commit the result"
    committed = CONTRACT_PATH.read_text(encoding="utf-8")
    assert committed == serialise(build_schema()), (
        "contracts/openapi.v1.json is stale — regenerate it with "
        "`uv run python scripts/export_openapi.py`"
    )


def test_every_agent_route_is_published() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    missing = AGENT_PATHS - set(schema["paths"])
    assert not missing, f"agent routes absent from the contract: {sorted(missing)}"


def test_the_message_post_returns_a_job_envelope() -> None:
    """No route holds the request open for a model call (§6)."""
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    post = schema["paths"]["/api/v1/matters/{matter_id}/agent/messages"]["post"]
    assert "202" in post["responses"]


def test_the_transcript_list_is_paginated() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    get = schema["paths"]["/api/v1/matters/{matter_id}/agent/messages"]["get"]
    names = {param["name"] for param in get.get("parameters", [])}
    assert {"limit", "cursor"} <= names

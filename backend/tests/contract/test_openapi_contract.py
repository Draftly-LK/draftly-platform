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


def test_document_correction_contract_publishes_pins_history_and_command_headers() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    paths = schema["paths"]
    document = "/api/v1/detected-documents/{document_id}"
    assert {f"{document}/interpretations", f"{document}/refresh-extraction"} <= paths.keys()
    schemas = schema["components"]["schemas"]
    assert {"interpretationGeneration", "extractionState"} <= schemas["DetectedDocumentRead"][
        "properties"
    ].keys()
    assert {"interpretationGeneration", "current"} <= schemas["DocumentReviewRead"][
        "properties"
    ].keys()
    assert "interpretationGeneration" in schemas["FactEvidenceRead"]["properties"]
    for path in (
        f"{document}/refresh-extraction",
        f"{document}/classification-decisions",
        f"{document}/boundary-decisions",
        "/api/v1/source-files/{source_file_id}/page-dispositions",
    ):
        parameters = paths[path]["post"]["parameters"]
        # Runtime dependencies preserve the documented 428/400 errors for
        # absent headers instead of FastAPI's required-parameter 422.
        headers = {item["name"].lower() for item in parameters if item["in"] == "header"}
        assert {"if-match", "idempotency-key"} <= headers


def test_requirement_readiness_and_scoped_check_contracts_publish_pins_and_headers() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    paths, models = schema["paths"], schema["components"]["schemas"]
    base = "/api/v1/matters/{matter_id}/checklist-items/{item_id}"
    for action in ("decisions", "links", "original-inspection"):
        headers = {
            p["name"].lower(): p
            for p in paths[f"{base}/{action}"]["post"]["parameters"]
            if p["in"] == "header"
        }
        assert {"if-match", "idempotency-key"} <= headers.keys()
        assert not headers["if-match"]["required"] and not headers["idempotency-key"]["required"]
    assert {"documentVersion", "interpretationGeneration"} <= set(
        models["LinkDocumentRequest"]["required"]
    )
    assert {"originals"} <= models["OriginalInspectionRead"]["properties"].keys()
    item_model = paths[f"{base}/decisions"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].rsplit("/", 1)[-1]
    assert {"inspectionHistory", "version"} <= models[item_model]["properties"].keys()
    assert {"transactionId", "associationVersion"} <= set(models["RunChecksRequest"]["required"])
    assert {"transactionId", "subjectId", "associationVersion"} <= models["CheckResultRead"][
        "properties"
    ].keys()
    assert "/api/v1/matters/{matter_id}/readiness" in paths
    assert {"state", "nextAction", "dependencies", "evaluatedAt"} <= models["MatterReadinessRead"][
        "properties"
    ].keys()

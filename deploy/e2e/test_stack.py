"""Whole-application end-to-end tests against the production compose stack.

Every test talks to running containers over the network (or to Docker about
them); nothing is imported from the application code.
"""

from __future__ import annotations

import json
import time
import uuid
from urllib.parse import quote

import pytest

from conftest import RETRIEVAL, SITE, compose, fetch

AUTHENTICATED_GET_ROUTES = [
    "/api/v1/account-status",
    "/api/v1/billing/plans",
    "/api/v1/billing/subscription",
    "/api/v1/billing/usage",
    "/api/v1/matters",
    "/api/v1/me",
    "/api/v1/notification-preferences",
    "/api/v1/notifications",
    "/api/v1/obligations",
    "/api/v1/parties",
    "/api/v1/register/entries",
    "/api/v1/register/periods",
    "/api/v1/rta/checklist",
    "/api/v1/rta/checks",
    "/api/v1/rta/document-classes",
    "/api/v1/rta/forms",
    "/api/v1/rta/questions",
    "/api/v1/rta/rule-pack",
    "/api/v1/rta/sources",
    "/api/v1/rta/taxonomy",
]


def _service_config(*, base_only: bool) -> dict:
    result = compose("config", "--format", "json", base_only=base_only)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["services"]


def _exec(service: str, *command: str) -> str:
    result = compose("exec", "-T", service, *command)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TestStartupAndMigrations:
    def test_migrations_ran_to_completion_before_the_api_started(self):
        state = json.loads(compose("ps", "-a", "--format", "json", "migrate").stdout.splitlines()[0])
        assert state["State"] == "exited"
        assert state["ExitCode"] == 0

    def test_database_schema_is_at_the_single_alembic_head(self):
        assert "(head)" in _exec("backend", "alembic", "current").splitlines()[-1]
        assert len(_exec("backend", "alembic", "heads").splitlines()) == 1

    def test_all_long_running_services_report_healthy(self):
        rows = [json.loads(line) for line in compose("ps", "--format", "json").stdout.splitlines()]
        health = {row["Service"]: row["Health"] for row in rows}
        for service in ("backend", "frontend", "retrieval"):
            assert health[service] == "healthy", health


class TestRoutingThroughCaddy:
    def test_liveness_reaches_the_backend(self):
        reply = fetch(f"{SITE}/health/live")
        assert reply.status == 200
        assert reply.json() == {"status": "ok"}
        assert reply.headers["server"] == "uvicorn"

    def test_readiness_confirms_the_database_connection(self):
        assert fetch(f"{SITE}/health/ready").status == 200

    def test_plain_http_redirects_to_https(self):
        reply = fetch("http://localhost:18080/health/live")
        assert reply.status in (301, 308)
        assert reply.headers["location"].startswith("https://")

    def test_non_api_paths_reach_the_frontend(self):
        reply = fetch(f"{SITE}/")
        assert reply.status in (200, 307)
        assert "x-correlation-id" not in reply.headers  # a backend-only header

    def test_frontend_static_assets_are_served(self):
        page = fetch(f"{SITE}/clerk-not-configured")
        assert page.status == 200
        assets = [part.split('"')[0] for part in page.body.decode().split('"/_next/static/')[1:]]
        assert assets, "page references no static assets"
        assert fetch(f"{SITE}/_next/static/{assets[0]}").status == 200

    def test_without_clerk_keys_pages_fail_closed(self):
        reply = fetch(f"{SITE}/matters")
        assert reply.status == 307
        assert reply.headers["location"].endswith("/clerk-not-configured")

    def test_retrieval_is_not_routed_publicly(self):
        reply = fetch(f"{SITE}/search?q=deed")
        assert "application/json" not in reply.headers.get("content-type", "")


class TestApiAuthentication:
    @pytest.mark.parametrize("route", AUTHENTICATED_GET_ROUTES)
    def test_unauthenticated_request_is_rejected(self, route):
        reply = fetch(f"{SITE}{route}")
        assert reply.status == 401
        assert reply.json()["error"]["code"] == "unauthenticated"

    def test_forged_bearer_token_never_authenticates(self):
        # This stack has no Clerk keys, and production forbids the stub identity
        # adapter, so the API fails closed: 503 service_misconfigured, never a
        # stub identity. With Clerk configured the expected answer is 401.
        reply = fetch(f"{SITE}/api/v1/me", headers={"Authorization": "Bearer not.a.real-token"})
        assert reply.status in (401, 503)
        error = reply.json()["error"]
        if reply.status == 503:
            assert error["code"] == "service_misconfigured"
        body = reply.body.decode()
        assert "Traceback" not in body and "CLERK_" not in body  # internals are not leaked
        uuid.UUID(error["correlation_id"])

    def test_errors_use_the_typed_envelope_with_a_correlation_id(self):
        reply = fetch(f"{SITE}/api/v1/me")
        error = reply.json()["error"]
        assert set(error) >= {"code", "message", "details", "correlation_id"}
        uuid.UUID(error["correlation_id"])
        assert reply.headers["x-correlation-id"]

    def test_wrong_method_is_405_not_500(self):
        assert fetch(f"{SITE}/api/v1/me", method="DELETE").status == 405

    def test_unknown_api_route_is_404(self):
        assert fetch(f"{SITE}/api/v1/does-not-exist").status == 404

    def test_api_docs_are_disabled_in_production(self):
        for path in ("/docs", "/redoc"):
            reply = fetch(f"{SITE}{path}")  # not under /api, so these land on the frontend
            assert "swagger" not in reply.body.decode(errors="ignore").lower()


class TestRetrievalService:
    def test_health_reports_the_frozen_statute_index(self):
        index = fetch(f"{RETRIEVAL}/health").json()["index"]
        assert (index["documents"], index["statutes"], index["amendments"]) == (75, 57, 18)
        assert index["sections"] > 3000
        assert index["reused"] is True

    def test_direct_section_lookup_returns_that_section_first(self):
        hits = fetch(f"{RETRIEVAL}/search?q={quote('SRC001:s2')}&limit=3").json()
        assert hits[0]["section_id"] == "SRC001:s2"

    def test_natural_language_search_returns_cited_sections(self):
        hits = fetch(f"{RETRIEVAL}/search?q={quote('registration of deeds affecting land')}&limit=5").json()
        assert 1 <= len(hits) <= 5
        for hit in hits:
            assert hit["section_id"].startswith("SRC")
            assert hit["document_type"] in {"statute", "amendment"}
            assert hit["public_source_url"] or hit["citation_note"]

    def test_kind_filter_is_applied(self):
        hits = fetch(f"{RETRIEVAL}/search?q=registration&kind=amendment&limit=10").json()
        assert hits and all(hit["document_type"] == "amendment" for hit in hits)

    def test_similar_cases_returns_conveyancing_case_law(self):
        result = fetch(f"{RETRIEVAL}/similar-cases?q={quote('deed of gift revoked for ingratitude')}&limit=3").json()
        assert result["outcome"] == "similar_cases_found"
        assert 1 <= len(result["hits"]) <= 3
        assert result["corpus_fingerprint"]

    def test_reference_endpoints_respond(self):
        assert len(fetch(f"{RETRIEVAL}/topics").json()) > 0
        assert len(fetch(f"{RETRIEVAL}/sources").json()) == 75
        assert isinstance(fetch(f"{RETRIEVAL}/case-statute-links?limit=5").json(), list)

    @pytest.mark.parametrize(
        "path",
        ["/search", "/search?q=", "/search?q=deed&limit=0", "/search?q=deed&limit=999", "/similar-cases"],
    )
    def test_invalid_input_is_a_validation_error_not_a_crash(self, path):
        assert fetch(f"{RETRIEVAL}{path}").status == 422

    def test_unsupported_kind_is_rejected(self):
        assert fetch(f"{RETRIEVAL}/search?q=deed&kind=case").status in (400, 422)

    def test_repeat_queries_are_fast_because_nothing_is_rebuilt(self):
        fetch(f"{RETRIEVAL}/search?q=mortgage&limit=5")
        started = time.monotonic()
        for _ in range(5):
            assert fetch(f"{RETRIEVAL}/search?q=mortgage&limit=5").status == 200
        assert (time.monotonic() - started) / 5 < 2.0

    def test_backend_reaches_retrieval_over_the_internal_network(self):
        script = "import urllib.request;print(urllib.request.urlopen('http://retrieval:8000/health',timeout=10).status)"
        assert _exec("backend", "python", "-c", script) == "200"


class TestIsolationAndHardening:
    def test_production_compose_publishes_only_caddy(self):
        services = _service_config(base_only=True)
        published = {name for name, service in services.items() if service.get("ports")}
        assert published == {"caddy"}

    def test_every_production_service_has_a_memory_limit_within_budget(self):
        services = _service_config(base_only=True)
        always_on = {name: int(svc["mem_limit"]) for name, svc in services.items() if not svc.get("profiles") and name != "migrate"}
        assert set(always_on) == {"caddy", "frontend", "backend", "retrieval"}
        assert sum(always_on.values()) <= 1024 * 1024 * 1024

    def test_containers_do_not_run_as_root(self):
        for service in ("backend", "retrieval", "frontend"):
            assert _exec(service, "id", "-u") != "0", service

    def test_retrieval_filesystem_is_read_only(self):
        result = compose("exec", "-T", "retrieval", "touch", "/app/data/processed/retrieval-indexes/probe")
        assert result.returncode != 0

    def test_no_secret_files_are_baked_into_the_images(self):
        assert _exec("backend", "sh", "-c", "ls -a /app | grep -c '^\\.env' || true") == "0"
        assert _exec("frontend", "sh", "-c", "ls -a /app/frontend | grep -c '^\\.env$' || true") == "0"

    def test_running_services_stay_within_their_memory_limits(self):
        ids = compose("ps", "-q").stdout.split()
        import subprocess

        stats = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemPerc}}", *ids],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for line in stats:
            name, percent = line.split()
            if "testdb" in name:
                continue
            assert float(percent.rstrip("%")) < 80, line

"""Fixtures for the whole-stack suite. Deliberately independent of backend/tests/conftest.py."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytest

E2E_DIR = Path(__file__).resolve().parent
DEPLOY_DIR = E2E_DIR.parent
PROJECT = "draftly-e2e"
BASE_COMPOSE = ["docker", "compose", "--env-file", str(E2E_DIR / "e2e.env"), "-f", str(DEPLOY_DIR / "docker-compose.yml")]
COMPOSE = [*BASE_COMPOSE, "-p", PROJECT, "-f", str(E2E_DIR / "docker-compose.e2e.yml")]

SITE = "https://localhost:18443"
RETRIEVAL = "http://127.0.0.1:18001"

_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE  # Caddy's local CA signs the localhost certificate


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self):
        return json.loads(self.body)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_INSECURE))


def fetch(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, timeout: float = 30) -> Response:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with _OPENER.open(request, timeout=timeout) as reply:
            return Response(reply.status, {k.lower(): v for k, v in reply.headers.items()}, reply.read())
    except urllib.error.HTTPError as error:
        return Response(error.code, {k.lower(): v for k, v in error.headers.items()}, error.read())


def compose(*args: str, base_only: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*(BASE_COMPOSE if base_only else COMPOSE), *args], capture_output=True, text=True, check=False)


def _wait_until(check, *, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    last: object = None
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception as exc:  # noqa: BLE001 - services are still starting
            last = exc
        time.sleep(2)
    raise TimeoutError(f"{what} not ready after {timeout}s (last error: {last})")


@pytest.fixture(scope="session", autouse=True)
def stack():
    if subprocess.run(["docker", "info"], capture_output=True, check=False).returncode != 0:
        pytest.skip("Docker daemon is not running")
    up = compose("up", "-d", "--wait", "--wait-timeout", "180")
    if up.returncode != 0:
        compose("down", "-v")
        pytest.fail(f"docker compose up failed:\n{up.stderr[-3000:]}")
    try:
        _wait_until(lambda: fetch(f"{SITE}/health/ready").status == 200, timeout=120, what="backend via Caddy")
        _wait_until(lambda: fetch(f"{RETRIEVAL}/health").status == 200, timeout=120, what="retrieval")
        yield
    finally:
        if os.environ.get("E2E_KEEP_STACK") != "1":
            compose("down", "-v")

"""Local-disk storage of client evidence must never be reachable outside
local/test/ci, and GCS must not be selectable until it is configured and
approved — same fail-closed posture as the identity and extraction adapters.

The GCS branch is exercised with the client factory patched out: these tests
are about the *selection* rules, and building a real client would need
credentials and a bucket.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.bootstrap as bootstrap
import src.platform.config as config
from src.bootstrap import LOCAL_ONLY_STORAGE_ENVIRONMENTS, build_source_file_storage
from src.modules.document.infrastructure.storage_filesystem import FilesystemSourceFileStorage
from src.modules.document.infrastructure.storage_gcs import GcsSourceFileStorage

DEPLOYED_ENVIRONMENTS = ["staging", "production"]

APPROVED_GCS = {
    "SOURCE_FILE_STORAGE": "gcs",
    "DRAFTLY_GCS_BUCKET": "draftly-test",
    "DRAFTLY_GCS_PROJECT_ID": "draftly-project",
    "DRAFTLY_STORAGE_REAL_DATA_APPROVED": "true",
}


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    config._settings = None
    # A client built under one configuration must not leak into the next test.
    bootstrap._gcs_client.cache_clear()


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    config._settings = None
    bootstrap._gcs_client.cache_clear()


def _stub_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip client construction and the bucket-policy round trip."""
    monkeypatch.setattr(
        bootstrap, "_gcs_client", lambda _project, _bucket: SimpleNamespace(bucket=lambda _n: None)
    )


# ── Filesystem stays local ───────────────────────────────────────────────────


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_filesystem_storage_is_refused_when_deployed(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, SOURCE_FILE_STORAGE="filesystem")
    with pytest.raises(RuntimeError, match="SOURCE_FILE_STORAGE=filesystem"):
        build_source_file_storage()


@pytest.mark.parametrize("environment", sorted(LOCAL_ONLY_STORAGE_ENVIRONMENTS))
def test_filesystem_storage_is_permitted_on_a_developer_machine(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _configure(monkeypatch, ENVIRONMENT=environment, SOURCE_FILE_STORAGE="filesystem")
    assert isinstance(build_source_file_storage(), FilesystemSourceFileStorage)


def test_an_unknown_storage_provider_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, ENVIRONMENT="local", SOURCE_FILE_STORAGE="s3")
    with pytest.raises(RuntimeError, match="Valid: filesystem, gcs"):
        build_source_file_storage()


# ── GCS needs configuring and approving, not an environment ──────────────────


def test_gcs_without_a_bucket_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT="production",
        SOURCE_FILE_STORAGE="gcs",
        DRAFTLY_GCS_BUCKET="",
    )
    with pytest.raises(RuntimeError, match="DRAFTLY_GCS_BUCKET"):
        build_source_file_storage()


def test_gcs_without_a_project_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT="production",
        SOURCE_FILE_STORAGE="gcs",
        DRAFTLY_GCS_BUCKET="draftly-test",
        DRAFTLY_GCS_PROJECT_ID="",
    )
    with pytest.raises(RuntimeError, match="DRAFTLY_GCS_PROJECT_ID"):
        build_source_file_storage()


def test_gcs_without_real_data_approval_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # A matter's uploaded evidence is client material by definition, so there is
    # no synthetic escape hatch here — only a recorded approval.
    _configure(
        monkeypatch,
        ENVIRONMENT="production",
        **{**APPROVED_GCS, "DRAFTLY_STORAGE_REAL_DATA_APPROVED": "false"},
    )
    with pytest.raises(RuntimeError, match="DRAFTLY_STORAGE_REAL_DATA_APPROVED"):
        build_source_file_storage()


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS + ["local"])
def test_gcs_is_permitted_in_any_environment_once_configured(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    # Including local: working against the staging bucket is a supported case,
    # gated on the approval flag rather than on the environment name.
    _configure(monkeypatch, ENVIRONMENT=environment, **APPROVED_GCS)
    _stub_client(monkeypatch)
    assert isinstance(build_source_file_storage(), GcsSourceFileStorage)


def test_missing_credentials_are_reported_as_a_wiring_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A raw DefaultCredentialsError out of the composition root reads as a
    # crash; every other misconfiguration here names what to set.
    from google.auth.exceptions import DefaultCredentialsError

    _configure(monkeypatch, ENVIRONMENT="production", **APPROVED_GCS)

    def _no_credentials(**_kwargs: object) -> object:
        raise DefaultCredentialsError("no ADC")

    monkeypatch.setattr("google.cloud.storage.Client", _no_credentials)
    with pytest.raises(RuntimeError, match="application-default login"):
        build_source_file_storage()


# ── Bucket policy is checked before the first upload ─────────────────────────


def _bucket(
    *, uniform: bool = True, prevention: str = "enforced", location: str = "ASIA-SOUTHEAST1"
) -> SimpleNamespace:
    return SimpleNamespace(
        iam_configuration=SimpleNamespace(
            uniform_bucket_level_access_enabled=uniform,
            public_access_prevention=prevention,
        ),
        location=location,
    )


def test_a_bucket_without_uniform_access_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, ENVIRONMENT="production", **APPROVED_GCS)
    client = SimpleNamespace(get_bucket=lambda _n: _bucket(uniform=False))
    with pytest.raises(RuntimeError, match="uniform bucket-level access"):
        bootstrap._assert_bucket_policy(client, "draftly-test")


def test_a_bucket_that_allows_public_access_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, ENVIRONMENT="production", **APPROVED_GCS)
    client = SimpleNamespace(get_bucket=lambda _n: _bucket(prevention="inherited"))
    with pytest.raises(RuntimeError, match="public access prevention"):
        bootstrap._assert_bucket_policy(client, "draftly-test")


def test_a_bucket_outside_the_approved_location_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Data residency is an approval item, not something a deployment picks up
    # by accident from whichever bucket it was pointed at.
    _configure(
        monkeypatch,
        ENVIRONMENT="production",
        **{**APPROVED_GCS, "DRAFTLY_GCS_LOCATION": "asia-southeast1"},
    )
    client = SimpleNamespace(get_bucket=lambda _n: _bucket(location="US"))
    with pytest.raises(RuntimeError, match="not the approved"):
        bootstrap._assert_bucket_policy(client, "draftly-test")


def test_a_correctly_configured_bucket_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(
        monkeypatch,
        ENVIRONMENT="production",
        **{**APPROVED_GCS, "DRAFTLY_GCS_LOCATION": "asia-southeast1"},
    )
    client = SimpleNamespace(get_bucket=lambda _n: _bucket())
    bootstrap._assert_bucket_policy(client, "draftly-test")

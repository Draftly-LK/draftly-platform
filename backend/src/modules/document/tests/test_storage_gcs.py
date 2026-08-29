"""Unit tests for the GCS storage adapter with a faked client — no network.

Fakes only: no credentials, no bucket, no request ever leaves the process. Every
byte string here is synthetic test material, not client evidence.

The load-bearing test is
``test_an_upload_is_always_conditional_on_the_key_being_free``: if that
precondition is ever dropped, GCS will silently replace an original, which is
the "silent original loss" release blocker in
``docs/service-definition-of-done.md`` §7.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest
from google.api_core.exceptions import Conflict, Forbidden, NotFound, PreconditionFailed

from src.modules.document.domain.errors import (
    SourceObjectImmutableError,
    SourceObjectNotFoundError,
    SourceObjectUnavailableError,
    SourceStorageNotApprovedError,
)
from src.modules.document.infrastructure.storage_gcs import GcsSourceFileStorage

KEY = "sources/usr_1/mat_1/src_1"
BYTES = b"%PDF-1.7\nsynthetic\n"
#: sha256 of BYTES, computed by the adapter — the fakes only need to agree.
OTHER_BYTES = b"%PDF-1.7\ndifferent\n"


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeBlob:
    def __init__(
        self,
        key: str,
        *,
        generation: int | None = None,
        data: bytes | None = None,
        metadata: dict[str, str] | None = None,
        upload_error: Exception | None = None,
        download_error: Exception | None = None,
        generation_after_upload: int | None = 101,
    ) -> None:
        self.name = key
        self.generation = generation
        self.metadata = metadata
        self._data = data
        self._upload_error = upload_error
        self._download_error = download_error
        self._generation_after_upload = generation_after_upload
        self.upload_kwargs: dict[str, Any] | None = None
        self.download_kwargs: dict[str, Any] | None = None
        self.uploads = 0
        self.reloads = 0
        self.upload_thread: threading.Thread | None = None

    def upload_from_string(self, data: bytes, **kwargs: Any) -> None:
        self.uploads += 1
        self.upload_kwargs = kwargs
        self.upload_thread = threading.current_thread()
        if self._upload_error is not None:
            raise self._upload_error
        self._data = data
        self.generation = self._generation_after_upload

    def download_as_bytes(self, **kwargs: Any) -> bytes:
        self.download_kwargs = kwargs
        if self._download_error is not None:
            raise self._download_error
        assert self._data is not None
        return self._data

    def reload(self, **_kwargs: Any) -> None:
        self.reloads += 1
        self.generation = 202

    def exists(self, **_kwargs: Any) -> bool:
        return self._data is not None


class FakeBucket:
    """Records what the adapter asked for, and hands back scripted blobs."""

    def __init__(
        self,
        *,
        new_blob: FakeBlob | None = None,
        existing: FakeBlob | None = None,
        get_blob_error: Exception | None = None,
    ) -> None:
        self._new_blob = new_blob
        self._existing = existing
        self._get_blob_error = get_blob_error
        self.requested_generations: list[int | None] = []
        self.get_blob_calls = 0

    def blob(self, key: str, generation: int | None = None) -> FakeBlob:
        self.requested_generations.append(generation)
        if self._new_blob is not None:
            return self._new_blob
        return FakeBlob(key, generation=generation, data=BYTES)

    def get_blob(self, key: str, **_kwargs: Any) -> FakeBlob | None:
        self.get_blob_calls += 1
        if self._get_blob_error is not None:
            raise self._get_blob_error
        return self._existing


def make_adapter(bucket: FakeBucket, *, approved: bool = True) -> GcsSourceFileStorage:
    client = SimpleNamespace(bucket=lambda _name: bucket)
    return GcsSourceFileStorage(
        client=client,  # type: ignore[arg-type]
        bucket_name="draftly-test",
        real_data_approved=approved,
    )


def sha256_of(data: bytes) -> str:
    from src.modules.document.infrastructure.object_store_support import content_sha256

    return content_sha256(data)


# ── Upload (storage-service.md §5) ───────────────────────────────────────────


async def test_an_upload_returns_the_object_generation_as_the_version() -> None:
    blob = FakeBlob(KEY, generation_after_upload=77)
    storage = make_adapter(FakeBucket(new_blob=blob))

    assert await storage.put(KEY, BYTES) == "77"


async def test_an_upload_is_always_conditional_on_the_key_being_free() -> None:
    blob = FakeBlob(KEY)
    storage = make_adapter(FakeBucket(new_blob=blob))

    await storage.put(KEY, BYTES)

    assert blob.upload_kwargs is not None
    # Without this, GCS replaces the original instead of refusing.
    assert blob.upload_kwargs["if_generation_match"] == 0


async def test_an_upload_records_the_evidence_hash_as_object_metadata() -> None:
    blob = FakeBlob(KEY)
    storage = make_adapter(FakeBucket(new_blob=blob))

    await storage.put(KEY, BYTES)

    # CRC32C protects the transfer; this is the hash a later read is checked
    # against, and a retried upload is recognised by.
    assert blob.metadata == {"sha256": sha256_of(BYTES)}
    assert blob.upload_kwargs is not None
    assert blob.upload_kwargs["checksum"] == "crc32c"


async def test_the_generation_is_fetched_when_the_upload_response_did_not_carry_one() -> None:
    blob = FakeBlob(KEY, generation_after_upload=None)
    storage = make_adapter(FakeBucket(new_blob=blob))

    assert await storage.put(KEY, BYTES) == "202"
    assert blob.reloads == 1


async def test_the_blocking_sdk_call_does_not_run_on_the_event_loop() -> None:
    blob = FakeBlob(KEY)
    storage = make_adapter(FakeBucket(new_blob=blob))

    await storage.put(KEY, BYTES)

    assert blob.upload_thread is not threading.main_thread()


# ── A key that is already occupied (§5, the retry path) ──────────────────────


async def test_a_retried_upload_of_identical_bytes_returns_the_existing_generation() -> None:
    # ingestion_service writes bytes before the row commits, so a retry after a
    # failed commit lands here. It is an ordinary retry, not a conflict.
    refused = FakeBlob(KEY, upload_error=PreconditionFailed("exists"))
    existing = FakeBlob(KEY, generation=55, data=BYTES, metadata={"sha256": sha256_of(BYTES)})
    storage = make_adapter(FakeBucket(new_blob=refused, existing=existing))

    assert await storage.put(KEY, BYTES) == "55"


async def test_different_bytes_under_an_occupied_key_are_refused() -> None:
    refused = FakeBlob(KEY, upload_error=PreconditionFailed("exists"))
    existing = FakeBlob(KEY, generation=55, data=BYTES, metadata={"sha256": sha256_of(BYTES)})
    storage = make_adapter(FakeBucket(new_blob=refused, existing=existing))

    with pytest.raises(SourceObjectImmutableError):
        await storage.put(KEY, OTHER_BYTES)


async def test_a_conflict_is_treated_exactly_like_a_precondition_failure() -> None:
    # 412 is the documented answer; 409 is handled so a path that returns it
    # instead cannot turn a retry into a user-visible error.
    refused = FakeBlob(KEY, upload_error=Conflict("exists"))
    existing = FakeBlob(KEY, generation=55, data=BYTES, metadata={"sha256": sha256_of(BYTES)})
    storage = make_adapter(FakeBucket(new_blob=refused, existing=existing))

    assert await storage.put(KEY, BYTES) == "55"


async def test_an_occupied_key_with_no_hash_metadata_is_settled_by_comparing_bytes() -> None:
    refused = FakeBlob(KEY, upload_error=PreconditionFailed("exists"))
    existing = FakeBlob(KEY, generation=55, data=OTHER_BYTES, metadata=None)
    storage = make_adapter(FakeBucket(new_blob=refused, existing=existing))

    with pytest.raises(SourceObjectImmutableError):
        await storage.put(KEY, BYTES)


# ── Reads resolve the exact object (§11) ─────────────────────────────────────


async def test_a_read_pins_the_recorded_generation() -> None:
    blob = FakeBlob(KEY, generation=42, data=BYTES)
    bucket = FakeBucket(new_blob=blob)
    storage = make_adapter(bucket)

    assert await storage.get(KEY, version="42") == BYTES

    # Pinned on the object handle and again as a precondition.
    assert bucket.requested_generations == [42]
    assert blob.download_kwargs is not None
    assert blob.download_kwargs["if_generation_match"] == 42


async def test_a_missing_object_is_a_typed_not_found() -> None:
    blob = FakeBlob(KEY, download_error=NotFound("gone"))
    storage = make_adapter(FakeBucket(new_blob=blob))

    with pytest.raises(SourceObjectNotFoundError):
        await storage.get(KEY, version="42")


async def test_a_generation_that_is_no_longer_live_is_a_typed_not_found() -> None:
    blob = FakeBlob(KEY, download_error=PreconditionFailed("superseded"))
    storage = make_adapter(FakeBucket(new_blob=blob))

    with pytest.raises(SourceObjectNotFoundError):
        await storage.get(KEY, version="42")


async def test_a_version_written_by_the_filesystem_adapter_is_a_miss_not_a_crash() -> None:
    # Rows predating GCS hold "sha256:<hex>". That names no GCS object, but it
    # must not reach int() and become a 500.
    storage = make_adapter(FakeBucket())

    with pytest.raises(SourceObjectNotFoundError):
        await storage.get(KEY, version="sha256:" + "a" * 64)


# ── Refusals and provider failures ───────────────────────────────────────────


async def test_uploads_are_refused_while_the_real_data_gate_is_closed() -> None:
    blob = FakeBlob(KEY)
    storage = make_adapter(FakeBucket(new_blob=blob), approved=False)

    with pytest.raises(SourceStorageNotApprovedError):
        await storage.put(KEY, BYTES)
    # The refusal happens before the bytes leave the process.
    assert blob.uploads == 0


async def test_a_key_that_is_not_a_server_generated_path_is_refused() -> None:
    blob = FakeBlob(KEY)
    storage = make_adapter(FakeBucket(new_blob=blob))

    with pytest.raises(ValueError):
        await storage.put("../outside/src_1", BYTES)
    assert blob.uploads == 0


async def test_a_provider_failure_carries_no_provider_text_into_the_envelope() -> None:
    secret = "bucket draftly-test quota detail for sources/usr_1/mat_1"
    blob = FakeBlob(KEY, upload_error=Forbidden(secret))
    storage = make_adapter(FakeBucket(new_blob=blob))

    with pytest.raises(SourceObjectUnavailableError) as raised:
        await storage.put(KEY, BYTES)

    # Provider messages embed keys and request fragments, and error envelopes
    # reach the client.
    assert secret not in str(raised.value)
    assert secret not in str(raised.value.details)

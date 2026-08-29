"""The named release-blocker test for silent original loss.

`docs/service-definition-of-done.md` §7 maps the "silent original loss" blocker
to `documents/test_immutability.py::test_put_immutable_rejects_existing_key`.
That path is what release engineering greps for, so the name here is fixed by
the document rather than chosen.

Both adapters are covered by the same test: an invariant that holds only on the
adapter a developer happens to run locally is not an invariant. §8 forbids
skipping, `xfail`ing, or quarantining anything in this file — a flaky
release-blocker is fixed, not muted.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

import pytest
from google.api_core.exceptions import PreconditionFailed

from src.modules.document.domain.errors import SourceObjectImmutableError
from src.modules.document.infrastructure.storage_filesystem import FilesystemSourceFileStorage
from src.modules.document.infrastructure.storage_gcs import GcsSourceFileStorage

KEY = "sources/usr_1/mat_1/src_1"
ORIGINAL = b"%PDF-1.7\nthe original\n"
REPLACEMENT = b"%PDF-1.7\nsomething else\n"


class _StoredBlob:
    """The object already in the bucket. Reads return the original bytes."""

    def __init__(self) -> None:
        self.generation = 55
        self.metadata = {"sha256": hashlib.sha256(ORIGINAL).hexdigest()}

    def download_as_bytes(self, **_kwargs: Any) -> bytes:
        return ORIGINAL


class _WriteHandle:
    """A fresh handle for a write, which GCS refuses because the key is taken.

    Deliberately a *different* object from `_StoredBlob`: `bucket.blob()`
    returns a new handle in the real SDK, so metadata staged for the incoming
    write is not visible to `get_blob`. Sharing one object here would let the
    incoming hash masquerade as the stored one and the test would pass on a
    bug.
    """

    def __init__(self) -> None:
        self.metadata: dict[str, str] | None = None
        self.generation: int | None = None

    def upload_from_string(self, _data: bytes, **_kwargs: Any) -> None:
        raise PreconditionFailed("object already exists")


def _gcs_adapter() -> GcsSourceFileStorage:
    stored = _StoredBlob()
    bucket = SimpleNamespace(
        blob=lambda _key, generation=None: stored if generation is not None else _WriteHandle(),
        get_blob=lambda _key, **_kwargs: stored,
    )
    return GcsSourceFileStorage(
        client=SimpleNamespace(bucket=lambda _name: bucket),  # type: ignore[arg-type]
        bucket_name="draftly-test",
        real_data_approved=True,
    )


async def _filesystem_adapter(tmp_path: Any) -> FilesystemSourceFileStorage:
    storage = FilesystemSourceFileStorage(tmp_path)
    await storage.put(KEY, ORIGINAL)
    return storage


@pytest.mark.parametrize("adapter_name", ["filesystem", "gcs"])
async def test_put_immutable_rejects_existing_key(adapter_name: str, tmp_path: Any) -> None:
    storage: Any = (
        await _filesystem_adapter(tmp_path) if adapter_name == "filesystem" else _gcs_adapter()
    )

    with pytest.raises(SourceObjectImmutableError):
        await storage.put(KEY, REPLACEMENT)


@pytest.mark.parametrize("adapter_name", ["filesystem", "gcs"])
async def test_a_refused_replacement_leaves_the_original_readable(
    adapter_name: str, tmp_path: Any
) -> None:
    # Refusing the write is only half of it. If the original were damaged on the
    # way to refusing, the evidence would still be lost.
    if adapter_name == "filesystem":
        storage: Any = await _filesystem_adapter(tmp_path)
        version = f"sha256:{hashlib.sha256(ORIGINAL).hexdigest()}"
    else:
        storage = _gcs_adapter()
        version = "55"

    with pytest.raises(SourceObjectImmutableError):
        await storage.put(KEY, REPLACEMENT)

    assert await storage.get(KEY, version=version) == ORIGINAL

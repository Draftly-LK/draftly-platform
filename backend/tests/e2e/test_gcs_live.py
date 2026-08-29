"""Live GCS smoke test — opt-in, and it writes to a real bucket.

Skipped unless ``RUN_LIVE_TESTS=1`` and ``DRAFTLY_GCS_BUCKET`` are set, in the
same shape as ``test_gemini_live.py``. Needs Application Default Credentials:
``gcloud auth application-default login``.

**This leaves objects behind.** The port has no ``delete`` by design — original
evidence is immutable — so these objects persist until something outside the
application removes them. Keys go under a ``livetest/`` prefix so a lifecycle
rule can expire them; add that rule, or point this at a throwaway bucket,
before making this part of a routine run.

It exists to answer two questions the fakes cannot: whether a duplicate key
comes back as 412 or 409, and whether ``blob.generation`` is populated without a
reload. Both are handled defensively in the adapter; this reports what actually
happens.
"""

from __future__ import annotations

import os
import uuid

import pytest

from src.modules.document.domain.errors import (
    SourceObjectImmutableError,
    SourceObjectNotFoundError,
)

pytestmark = pytest.mark.skipif(
    not (os.environ.get("RUN_LIVE_TESTS") == "1" and os.environ.get("DRAFTLY_GCS_BUCKET")),
    reason="live GCS smoke runs only with RUN_LIVE_TESTS=1 and DRAFTLY_GCS_BUCKET set",
)

SYNTHETIC = b"%PDF-1.7\nsynthetic live-test material, not client evidence\n"


def _adapter() -> object:
    from google.cloud import storage

    from src.modules.document.infrastructure.storage_gcs import GcsSourceFileStorage

    bucket = os.environ["DRAFTLY_GCS_BUCKET"]
    project = os.environ.get("DRAFTLY_GCS_PROJECT_ID") or None
    return GcsSourceFileStorage(
        client=storage.Client(project=project),
        bucket_name=bucket,
        real_data_approved=True,
    )


async def test_a_real_upload_returns_a_generation_and_reads_back_identically() -> None:
    storage = _adapter()
    key = f"livetest/{uuid.uuid4().hex}/src_1"

    version = await storage.put(key, SYNTHETIC)  # type: ignore[attr-defined]

    # A GCS generation is a decimal integer, not the filesystem hash format.
    assert version.isdigit()
    assert await storage.get(key, version=version) == SYNTHETIC  # type: ignore[attr-defined]


async def test_a_real_duplicate_key_behaves_as_the_adapter_assumes() -> None:
    storage = _adapter()
    key = f"livetest/{uuid.uuid4().hex}/src_1"

    version = await storage.put(key, SYNTHETIC)  # type: ignore[attr-defined]
    # Identical bytes: an ordinary retry, so the same generation comes back.
    assert await storage.put(key, SYNTHETIC) == version  # type: ignore[attr-defined]
    # Different bytes: refused, whichever status the API chose to report.
    with pytest.raises(SourceObjectImmutableError):
        await storage.put(key, SYNTHETIC + b"altered\n")  # type: ignore[attr-defined]


async def test_a_generation_that_was_never_written_is_a_typed_not_found() -> None:
    storage = _adapter()
    key = f"livetest/{uuid.uuid4().hex}/src_1"
    await storage.put(key, SYNTHETIC)  # type: ignore[attr-defined]

    with pytest.raises(SourceObjectNotFoundError):
        await storage.get(key, version="1")  # type: ignore[attr-defined]

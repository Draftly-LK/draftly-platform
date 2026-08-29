"""Google Cloud Storage implementation of `SourceFileStoragePort`.

The write is conditional on absence — `if_generation_match=0` — so GCS itself
refuses to overwrite an original rather than the application asking politely
first (`storage-service.md` §5). The read pins the generation recorded at
upload, so a read cannot quietly return "whatever is at this key now".

GCS is not S3-compatible and is deliberately not reached through an S3
emulation layer (`infrastructure.md`): this adapter uses native generation
preconditions and native checksum metadata.

What this adapter does *not* do is verify the evidence hash. It guarantees the
bytes came from the recorded object; proving they are the recorded bytes needs
`SourceFile.sha256`, which lives in the application layer. `processing_job`
does that check before any bytes reach an extraction provider.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NoReturn

import structlog
from google.api_core.exceptions import (
    Conflict,
    Forbidden,
    GoogleAPIError,
    NotFound,
    PreconditionFailed,
    TooManyRequests,
)
from google.cloud.storage.retry import DEFAULT_RETRY, DEFAULT_RETRY_IF_GENERATION_SPECIFIED

from src.modules.document.domain.errors import (
    SourceObjectImmutableError,
    SourceObjectNotFoundError,
    SourceObjectUnavailableError,
    SourceStorageNotApprovedError,
)
from src.modules.document.infrastructure.object_store_support import (
    content_sha256,
    validate_object_key,
)

if TYPE_CHECKING:
    from google.cloud import storage  # type: ignore[attr-defined]

log = structlog.get_logger(__name__)

#: Recorded on the object so a retried upload can be recognised as the same
#: bytes without downloading them again. GCS CRC32C protects the transfer; this
#: is Draftly's evidence hash and the two are not interchangeable
#: (`storage-service.md` §5).
_SHA256_METADATA_KEY = "sha256"

#: Uploads are capped well below this by `max_source_file_bytes`, but a stalled
#: connection must not hold a request open indefinitely.
_DEFAULT_TIMEOUT_S = 60.0


def _translate(exc: GoogleAPIError, *, key: str, version: str = "") -> NoReturn:
    """Turn any provider failure into a typed domain error carrying no provider text.

    Kept as one function rather than inline ``except`` bodies so a future
    `storage_service` lifts a single mapping. Provider messages embed object
    keys and request fragments and error envelopes reach the client, so only a
    stable machine code and the exception type are logged — never ``str(exc)``.
    """
    if isinstance(exc, Forbidden):
        reason = "permission_denied"
    elif isinstance(exc, TooManyRequests):
        reason = "rate_limited"
    else:
        reason = "provider_unavailable"
    log.error(
        "source_file.storage.provider_failed",
        storage_object_key=key,
        reason=reason,
        exc_type=type(exc).__name__,
    )
    raise SourceObjectUnavailableError(storageObjectKey=key, storageObjectVersion=version) from exc


class GcsSourceFileStorage:
    """Stores each object once, under a generation precondition, in one bucket."""

    def __init__(
        self,
        *,
        client: storage.Client,
        bucket_name: str,
        real_data_approved: bool,
        timeout_seconds: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._client = client
        self._bucket_name = bucket_name
        self._real_data_approved = real_data_approved
        self._timeout = timeout_seconds

    def _bucket(self) -> Any:
        # ``bucket()`` builds a handle without an API call, unlike ``get_bucket``.
        return self._client.bucket(self._bucket_name)

    async def put(self, key: str, data: bytes) -> str:
        return await asyncio.to_thread(self._put_sync, key, data)

    def _put_sync(self, key: str, data: bytes, *, reconciling: bool = False) -> str:
        validate_object_key(key)
        if not self._real_data_approved:
            # Refused before the bytes leave the process, not after.
            raise SourceStorageNotApprovedError(storageObjectKey=key)

        digest = content_sha256(data)
        bucket = self._bucket()
        blob = bucket.blob(key)
        blob.metadata = {_SHA256_METADATA_KEY: digest}
        try:
            blob.upload_from_string(
                data,
                # Set explicitly so GCS never infers a type from the key.
                content_type="application/octet-stream",
                # The whole point: an existing live object fails the
                # precondition instead of being replaced.
                if_generation_match=0,
                checksum="crc32c",
                timeout=self._timeout,
                retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
            )
        except (PreconditionFailed, Conflict) as exc:
            # 412 is the documented answer; 409 is caught because it costs
            # nothing and closes the gap if a code path returns it instead.
            return self._reconcile_existing(
                bucket, key=key, data=data, digest=digest, reconciling=reconciling, cause=exc
            )
        except GoogleAPIError as exc:
            _translate(exc, key=key)

        generation = blob.generation
        if generation is None:
            # The single-shot upload response populates this; the resumable path
            # is the one worth a fallback rather than an assumption.
            blob.reload(timeout=self._timeout, retry=DEFAULT_RETRY)
            generation = blob.generation
        if generation is None:
            log.error("source_file.storage.no_generation", storage_object_key=key)
            raise SourceObjectUnavailableError(storageObjectKey=key)

        log.info(
            "source_file.storage.stored",
            storage_object_key=key,
            byte_length=len(data),
            generation=generation,
        )
        return str(generation)

    def _reconcile_existing(
        self,
        bucket: Any,
        *,
        key: str,
        data: bytes,
        digest: str,
        reconciling: bool,
        cause: GoogleAPIError,
    ) -> str:
        """Decide whether an occupied key is a retry of this upload or a collision.

        This is not an edge case. `ingestion_service` writes bytes *before* the
        row commits, on the reasoning that an object with no row is safer than a
        row promising bytes that were never written. So every retry of a request
        that failed after the upload lands here, and treating it as a conflict
        would turn ordinary retries into user-visible errors.
        """
        try:
            existing = bucket.get_blob(key, timeout=self._timeout, retry=DEFAULT_RETRY)
        except GoogleAPIError as exc:
            _translate(exc, key=key)

        if existing is None:
            # The object went away between the refused write and this read.
            # Try once more; do not loop.
            if reconciling:
                log.error("source_file.storage.reconcile_failed", storage_object_key=key)
                raise SourceObjectUnavailableError(storageObjectKey=key) from cause
            return self._put_sync(key, data, reconciling=True)

        recorded = (existing.metadata or {}).get(_SHA256_METADATA_KEY)
        if recorded is None:
            # Written before the metadata convention, or by something else.
            # Bounded by the upload size cap, so comparing bytes is affordable.
            try:
                recorded = content_sha256(
                    existing.download_as_bytes(
                        if_generation_match=existing.generation,
                        timeout=self._timeout,
                        retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
                    )
                )
            except GoogleAPIError as exc:
                _translate(exc, key=key)

        if recorded != digest:
            raise SourceObjectImmutableError(storageObjectKey=key) from cause

        log.info(
            "source_file.storage.retry_idempotent",
            storage_object_key=key,
            generation=existing.generation,
        )
        return str(existing.generation)

    async def get(self, key: str, *, version: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, key, version)

    def _get_sync(self, key: str, version: str) -> bytes:
        validate_object_key(key)
        try:
            generation = int(version)
        except (TypeError, ValueError) as exc:
            # A row written by the filesystem adapter holds ``sha256:<hex>``.
            # That names no GCS object, so it is a miss rather than a crash.
            log.warning(
                "source_file.storage.unreadable_version",
                storage_object_key=key,
                storage_object_version=version,
            )
            raise SourceObjectNotFoundError(
                storageObjectKey=key, storageObjectVersion=version
            ) from exc

        blob = self._bucket().blob(key, generation=generation)
        try:
            return bytes(
                blob.download_as_bytes(
                    # Pinned twice: on the object handle and as a precondition.
                    if_generation_match=generation,
                    timeout=self._timeout,
                    retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
                )
            )
        except (NotFound, PreconditionFailed) as exc:
            # Either the key is gone or the recorded generation is no longer
            # live. Both mean the evidence of record cannot be produced.
            raise SourceObjectNotFoundError(
                storageObjectKey=key, storageObjectVersion=version
            ) from exc
        except GoogleAPIError as exc:
            _translate(exc, key=key, version=version)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, key)

    def _exists_sync(self, key: str) -> bool:
        validate_object_key(key)
        try:
            result: bool = (
                self._bucket().blob(key).exists(timeout=self._timeout, retry=DEFAULT_RETRY)
            )
        except GoogleAPIError as exc:
            _translate(exc, key=key)
        return result

"""Local-filesystem implementation of `SourceFileStoragePort`.

For developer machines and CI only — bootstrap refuses to select it anywhere
else, exactly as it refuses the stub identity and stub extraction adapters. It
has no encryption at rest, no object versioning, and no lifecycle policy, so it
cannot honour the retention and confidentiality expectations §6.2 stage 2 puts
on stored client evidence.

What it does honour is immutability: a key is written once. A repeat write of
the *same* bytes is accepted so a retried upload is idempotent; a write of
different bytes under a key that already exists is refused rather than
silently replacing evidence.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import structlog

from src.modules.document.domain.errors import (
    SourceObjectImmutableError,
    SourceObjectIntegrityError,
    SourceObjectNotFoundError,
)
from src.modules.document.infrastructure.object_store_support import (
    content_version,
    validate_object_key,
)

log = structlog.get_logger(__name__)


class FilesystemSourceFileStorage:
    """Stores each object as one file under a configured root directory."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        validate_object_key(key)
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Storage keys must resolve inside the storage root.")
        return path

    async def put(self, key: str, data: bytes) -> str:
        return await asyncio.to_thread(self._put_sync, key, data)

    def _put_sync(self, key: str, data: bytes) -> str:
        path = self._path(key)
        version = content_version(data)
        if path.exists():
            if content_version(path.read_bytes()) != version:
                raise SourceObjectImmutableError(storageObjectKey=key)
            return version
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a crash mid-write cannot leave a truncated object
        # that later reads would treat as the original evidence.
        handle, temp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".partial")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        log.info("source_file.storage.stored", storage_object_key=key, byte_length=len(data))
        return version

    async def get(self, key: str, *, version: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, key, version)

    def _get_sync(self, key: str, version: str) -> bytes:
        """Read the bytes, then prove they are the ones `version` names.

        A filesystem has no native object versioning, so the recorded version is
        a content hash and checking it is the only guarantee available. Doing
        the check here rather than skipping it keeps the local path from being
        structurally weaker than the deployed one: if a change breaks how the
        version is threaded through, it breaks in development instead of
        surfacing for the first time against real evidence.
        """
        path = self._path(key)
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise SourceObjectNotFoundError(
                storageObjectKey=key, storageObjectVersion=version
            ) from exc
        # Rejected-in-quarantine rows carry no version and never reach a read;
        # tolerate the empty case rather than inventing a failure for it.
        if version and content_version(data) != version:
            log.error(
                "source_file.storage.version_mismatch",
                storage_object_key=key,
                expected_version=version,
                found_version=content_version(data),
            )
            raise SourceObjectIntegrityError(storageObjectKey=key, storageObjectVersion=version)
        return data

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(lambda: self._path(key).is_file())

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
import hashlib
import os
import re
import tempfile
from pathlib import Path

import structlog

from src.modules.document.domain.errors import SourceObjectImmutableError

log = structlog.get_logger(__name__)

#: Keys are built from opaque server-generated ids. The pattern is defence in
#: depth: no client value reaches it, and nothing that could escape the root
#: directory is accepted even if one day one did.
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]{0,254}$")


def _version_of(data: bytes) -> str:
    """The content hash is the only version guarantee a filesystem can give.

    Returning a made-up counter would let a caller believe it had fetched the
    same object it hashed at upload. This value is checkable against the bytes.
    """
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class FilesystemSourceFileStorage:
    """Stores each object as one file under a configured root directory."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        if ".." in key or not _SAFE_KEY.match(key):
            raise ValueError("Storage keys are server-generated opaque paths.")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Storage keys must resolve inside the storage root.")
        return path

    async def put(self, key: str, data: bytes) -> str:
        return await asyncio.to_thread(self._put_sync, key, data)

    def _put_sync(self, key: str, data: bytes) -> str:
        path = self._path(key)
        version = _version_of(data)
        if path.exists():
            if _version_of(path.read_bytes()) != version:
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

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(lambda: self._path(key).read_bytes())

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(lambda: self._path(key).is_file())

"""Provider-neutral helpers shared by every `SourceFileStoragePort` adapter.

Nothing here imports a provider SDK or touches a filesystem, so this module is
the seam along which the storage adapters can be lifted into the
`storage_service` that `docs/services/storage-service.md` specifies. Anything
that needs `google.api_core` or a `Path` belongs in the adapter, not here.
"""

from __future__ import annotations

import hashlib
import re

#: Keys are built from opaque server-generated ids. The pattern is defence in
#: depth: no client value reaches it, and nothing that could escape a root
#: directory is accepted even if one day one did.
#:
#: `storage-service.md` §6 is the reason this is narrow rather than permissive:
#: file names, party names, matter references, email addresses, and document
#: titles never appear in a key.
OBJECT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-./]{0,254}$")


def validate_object_key(key: str) -> str:
    """Return `key` unchanged, or raise `ValueError` if it was not ours.

    Rejecting `..` separately from the pattern is deliberate: the pattern alone
    already excludes it, but a future widening of the character class should not
    silently reopen traversal.
    """
    if ".." in key or not OBJECT_KEY_PATTERN.match(key):
        raise ValueError("Storage keys are server-generated opaque paths.")
    return key


def content_sha256(data: bytes) -> str:
    """The evidence hash, bare hex.

    This is the value recorded on `SourceFile.sha256` and the one a download is
    checked against. It is Draftly's own integrity guarantee — a provider
    checksum such as GCS CRC32C protects the transfer, not the evidence.
    """
    return hashlib.sha256(data).hexdigest()


def content_version(data: bytes) -> str:
    """The version token an adapter with no native object versioning can give.

    Returning a made-up counter would let a caller believe it had fetched the
    same object it hashed at upload. This value is checkable against the bytes.
    A provider that versions objects natively returns that version instead.
    """
    return f"sha256:{content_sha256(data)}"

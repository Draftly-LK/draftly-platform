"""Local/test adapter for `FieldEncryptionPort` — NOT a production key manager.

`identifierValue` is the highest-sensitivity field in the product, so its key is
separate from the general database key by construction: nothing else in the
codebase reads `party_identifier_key` or `party_blind_index_key`.

Production key management is an **open decision**, not a default:
party-service.md §12 decision 7 and infrastructure.md §7 must settle the KMS,
the rotation schedule, and the re-encryption path before this service handles
real client data. Until then this adapter refuses to start in production and in
any environment where the keys are not explicitly configured — a hardcoded key
is a local-development convenience and must never silently become the live one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

from src.platform.config import Settings

# Deterministic development seeds. Only reachable when the environment is local
# or test AND no key is configured; see build_field_encryption_adapter.
_DEV_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"draftly-party-ident-v0-seed-key!")
_DEV_BLIND_INDEX_KEY = b"draftly-party-blind-index-dev-only"

_NON_PRODUCTION_ENVIRONMENTS = frozenset({"local", "test", "ci"})


class UnconfiguredPartyEncryptionError(RuntimeError):
    """Raised at wiring time rather than serving a request with a known key."""


class LocalFieldEncryptionAdapter:
    """Reversible Fernet encryption plus an HMAC blind index for exact-match probes.

    The blind index lets §7's duplicate probe compare identifiers without
    decrypting them, and it uses a different key from the ciphertext so that
    disclosure of one does not compromise the other.
    """

    def __init__(self, *, encryption_key: bytes, blind_index_key: bytes) -> None:
        self._fernet = Fernet(encryption_key)
        self._blind_index_key = blind_index_key

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode("utf-8")

    def blind_index(self, plaintext: str) -> str:
        normalised = plaintext.strip().upper()
        return hmac.new(
            self._blind_index_key, normalised.encode("utf-8"), hashlib.sha256
        ).hexdigest()


def build_field_encryption_adapter(settings: Settings) -> LocalFieldEncryptionAdapter:
    """Fail closed: never fall back to the development key outside local/test."""
    configured_key = settings.party_identifier_key.strip()
    configured_blind = settings.party_blind_index_key.strip()

    if configured_key and configured_blind:
        return LocalFieldEncryptionAdapter(
            encryption_key=configured_key.encode("ascii"),
            blind_index_key=configured_blind.encode("utf-8"),
        )

    if settings.environment not in _NON_PRODUCTION_ENVIRONMENTS:
        raise UnconfiguredPartyEncryptionError(
            "PARTY_IDENTIFIER_KEY and PARTY_BLIND_INDEX_KEY must be set outside "
            "local and test environments. Production key management for the "
            "protected identity tier is an unresolved decision "
            "(party-service.md §12 decision 7)."
        )

    return LocalFieldEncryptionAdapter(
        encryption_key=_DEV_ENCRYPTION_KEY,
        blind_index_key=_DEV_BLIND_INDEX_KEY,
    )


class StubFieldEncryptionAdapter(LocalFieldEncryptionAdapter):
    """Development-key adapter for unit tests and local runs only."""

    def __init__(self) -> None:
        super().__init__(
            encryption_key=_DEV_ENCRYPTION_KEY,
            blind_index_key=_DEV_BLIND_INDEX_KEY,
        )

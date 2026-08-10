"""Test-only field encryption — reversible Fernet with a fixed test key."""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

# Separate from general DB key — rotatable in production (infrastructure.md §7).
_TEST_KEY = base64.urlsafe_b64encode(b"draftly-party-ident-v0-seed-key!")
_BLIND_KEY = b"draftly-party-blind-index-test"


class StubFieldEncryptionAdapter:
    """Reversible encryption for V0 tests and local development only."""

    def __init__(self) -> None:
        self._fernet = Fernet(_TEST_KEY)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode("utf-8")

    def blind_index(self, plaintext: str) -> str:
        normalised = plaintext.strip().upper()
        digest = hmac.new(_BLIND_KEY, normalised.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest

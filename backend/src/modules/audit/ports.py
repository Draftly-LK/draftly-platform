"""Audit module port — AuditPort protocol.

Implemented by AuditService. Imported by every application service that
writes audit events (auth, matter, document, etc.).
"""

from __future__ import annotations

from typing import Protocol

from src.modules.auth.ports import AuditEventInput


class AuditPort(Protocol):
    """Append-only audit event recorder.

    record() participates in the same database transaction as the mutation
    (audit-service.md §5 — either both commit or neither does).
    """

    async def record(self, event: AuditEventInput) -> None:
        """Record an audit event in the current transaction."""
        ...

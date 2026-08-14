"""Unit tests for audit event hash canonicalisation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.modules.audit.application.audit_service import AuditService
from src.modules.auth.ports import AuditEventInput

_FIXED_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeAuditRepo:
    def __init__(self) -> None:
        self.inserts: list[dict[str, object]] = []

    async def get_last_hash(self, user_id: str) -> str:
        return ""

    async def insert(self, **kwargs: object) -> None:
        self.inserts.append(kwargs)


def _base_event(**overrides: object) -> AuditEventInput:
    defaults: dict[str, object] = {
        "user_id": "usr_test",
        "action": "user.role_changed",
        "target_type": "user",
        "target_id": "usr_target",
        "matter_id": None,
        "actor": "usr_actor",
        "before_ref": None,
        "after_ref": None,
        "reason": None,
        "correlation_id": "corr-1",
        "causation_id": None,
    }
    defaults.update(overrides)
    return AuditEventInput(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
@patch("src.modules.audit.application.audit_service.uuid.uuid4")
@patch("src.modules.audit.application.audit_service.datetime")
async def test_audit_hash_includes_tamper_evident_fields(
    mock_datetime: MagicMock,
    mock_uuid4: MagicMock,
) -> None:
    mock_uuid4.return_value = MagicMock(hex="a" * 32)
    mock_datetime.now.return_value = _FIXED_NOW

    repo = FakeAuditRepo()
    service = AuditService(repository=repo)  # type: ignore[arg-type]

    await service.record(_base_event())
    first_hash = repo.inserts[0]["hash_"]

    await service.record(_base_event(matter_id="mat_other"))
    second_hash = repo.inserts[1]["hash_"]

    assert first_hash != second_hash

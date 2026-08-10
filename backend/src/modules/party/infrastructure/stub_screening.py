"""Manual screening stub — returns clear unless caller supplies a result via service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.modules.party.domain.models import (
    ConfidentialityLevel,
    ScreeningOutcome,
    ScreeningResult,
)


class ManualScreeningAdapter:
    """V0 adapter: screening is recorded manually; this stub is unused by default."""

    async def screen(self, party_snapshot: dict[str, Any], list_version: str) -> ScreeningResult:
        _ = party_snapshot
        now = datetime.now(tz=UTC)
        return ScreeningResult(
            id=f"scr_{uuid4().hex}",
            party_id=str(party_snapshot.get("id", "")),
            list_version=list_version,
            provider_ref="manual-stub",
            outcome=ScreeningOutcome.CLEAR,
            match_count=0,
            reviewed_by=None,
            reviewed_at=None,
            disposition_reason=None,
            confidentiality_level=ConfidentialityLevel.RESTRICTED_COMPLIANCE,
            created_at=now,
        )

"""Identifier values never sit in the database in plaintext (Rule 3, §5.4).

party-service.md encrypts ``identifierValue`` at rest with a blind index for
lookup, and requires that "a database dump of the party tables contains no
plaintext identifier". tests/privacy/ proves it against a recording session;
this proves it against Postgres, dumping every row of every table as text.

Scope follows party-service.md: identifier values. Names and addresses are
stored readable by design, for display and search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_synthetic_matter import LAWYER_A, SeedIdentityAdapter, seed
from src.api.deps import get_party_service
from src.bootstrap import build_party_matter_access
from src.modules.audit.application.audit_service import AuditService
from src.modules.audit.infrastructure.repository import SqlAuditRepository
from src.modules.auth.application.auth_service import AuthService
from src.modules.auth.domain.models import Role
from src.modules.auth.infrastructure.repository import (
    SqlUserIdentityRepository,
    SqlUserRepository,
)
from src.modules.party.application.party_service import PartyService
from src.modules.party.infrastructure.orm import PartyRow
from src.modules.party.ports import RecordIdentityEvidenceInput
from src.platform.request_context import RequestContext
from tests.factories.party import SYNTHETIC_NIC, SYNTHETIC_NIC_OLD_FORMAT, SYNTHETIC_PASSPORT

pytestmark = pytest.mark.integration

Recorded = tuple[PartyService, RequestContext, str, list[Any]]

IDENTIFIERS = {
    "nic": SYNTHETIC_NIC,
    "passport": SYNTHETIC_PASSPORT,
}


@pytest.fixture
async def recorded(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Recorded:
    """Seed a matter, then record identifiers on one party, capturing logs."""
    monkeypatch.setenv("SOURCE_FILE_STORAGE", "filesystem")
    monkeypatch.setenv("SOURCE_FILE_STORAGE_DIR", str(tmp_path / "source-files"))
    report = await seed(db_session)
    ctx = RequestContext(
        actor_id=report.lawyer_id, account_role=Role.APPROVER, correlation_id="corr_privacy"
    )
    auth = AuthService(
        identity_port=SeedIdentityAdapter(LAWYER_A),
        user_identity_repo=SqlUserIdentityRepository(db_session),
        user_repo=SqlUserRepository(db_session),
        audit_port=AuditService(repository=SqlAuditRepository(db_session)),
    )
    parties = get_party_service(
        session=db_session, auth_service=auth, matter_access=build_party_matter_access()
    )
    party_id = (
        await db_session.execute(
            select(PartyRow.id).where(PartyRow.user_id == report.lawyer_id).limit(1)
        )
    ).scalar_one()

    with structlog.testing.capture_logs() as logs:
        for kind, value in [*IDENTIFIERS.items(), ("nic", SYNTHETIC_NIC_OLD_FORMAT)]:
            await parties.record_identity_evidence(
                ctx,
                party_id,
                RecordIdentityEvidenceInput(
                    evidence_kind=kind,
                    identifier_value=value,
                    issued_on=None,
                    expires_on=None,
                    issuing_authority=None,
                    document_id=None,
                    document_version_id=None,
                    evidence_span=None,
                    supersedes_evidence_id=None,
                ),
            )
    await db_session.flush()
    return parties, ctx, party_id, logs


async def _dump(session: AsyncSession) -> str:
    """Every row of every table in the schema, each rendered as text."""
    tables = (
        await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
        )
    ).scalars()
    chunks: list[str] = []
    for table in tables:
        rows = await session.execute(text(f'SELECT t::text FROM "{table}" AS t'))
        chunks.extend(f"{table}: {row}" for row in rows.scalars())
    return "\n".join(chunks)


@pytest.mark.parametrize("value", [SYNTHETIC_NIC, SYNTHETIC_NIC_OLD_FORMAT, SYNTHETIC_PASSPORT])
async def test_no_table_holds_an_identifier_in_plaintext(
    db_session: AsyncSession,
    recorded: Recorded,
    value: str,
) -> None:
    dump = await _dump(db_session)

    assert "identity_evidence:" in dump, "the evidence rows were not written"
    # Postgres renders a bytea column as hex inside row text, so a plaintext
    # value stored as bytes shows up only in that form.
    for form in (value, value.encode("utf-8").hex()):
        assert form not in dump


@pytest.mark.parametrize("value", [SYNTHETIC_NIC, SYNTHETIC_NIC_OLD_FORMAT, SYNTHETIC_PASSPORT])
async def test_no_log_line_carries_an_identifier(
    recorded: Recorded,
    value: str,
) -> None:
    _, _, _, logs = recorded

    assert value not in repr(logs)


async def test_an_identifier_is_recoverable_with_a_stated_purpose(
    recorded: Recorded,
) -> None:
    """Encrypted, not discarded: a read with a purpose gets the value back."""
    parties, ctx, party_id, _ = recorded
    evidence = await parties.list_identity_evidence(ctx, party_id)
    passport = next(item for item in evidence if item.evidence_kind.value == "passport")

    read = await parties.read_identity_value(
        ctx, party_id, passport.id, purpose="synthetic privacy test"
    )

    assert read.identifier_value == SYNTHETIC_PASSPORT

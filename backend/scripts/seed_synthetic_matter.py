"""Seed a synthetic demo matter through the real application services.

Every row is written by the same service a user's request would reach, so a
seeded matter carries the audit trail a walked-through one does, and the data
comes from ``tests/factories`` so seed and test data cannot drift apart.

Run against a local, test or CI database only:

    uv run python scripts/seed_synthetic_matter.py

Running it twice is safe. A matter is unique per owner and reference, so a
matter that already exists is left alone, together with everything seeded with
it: the whole profile commits as one transaction.

There is no reset flag. The audit log is append-only, so wiping seeded data
means dropping the local database, not deleting rows from it.

Only the ``smoke`` profile exists. The ``full`` profile needs the Appendix B
roster in docs/TESTING_PLAN.md, and that roster is a human gate.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Run as a file, the script's own directory is on sys.path instead of backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.deps import get_party_service  # noqa: E402
from src.bootstrap import (  # noqa: E402
    STUB_IDENTITY_ENVIRONMENTS,
    build_ingestion_service,
    build_matter_service,
    build_party_matter_access,
)
from src.modules.audit.application.audit_service import AuditService  # noqa: E402
from src.modules.audit.infrastructure.repository import SqlAuditRepository  # noqa: E402
from src.modules.auth.application.auth_service import AuthService  # noqa: E402
from src.modules.auth.infrastructure.repository import (  # noqa: E402
    SqlUserIdentityRepository,
    SqlUserRepository,
)
from src.modules.auth.ports import IdentityClaims  # noqa: E402
from src.modules.matter.application.matter_service import CreateMatterInput  # noqa: E402
from src.modules.matter.infrastructure.orm import MatterRow  # noqa: E402
from src.modules.party.ports import CreatePartyInput  # noqa: E402
from src.platform.config import get_settings  # noqa: E402
from src.platform.request_context import RequestContext  # noqa: E402
from tests.factories.document import synthetic_pdf  # noqa: E402
from tests.factories.party import SYNTHETIC_PARTY_A, SYNTHETIC_PARTY_B  # noqa: E402

PROFILES = ("smoke",)
CORRELATION_ID = "corr_seed_synthetic"
SEED_ISSUER = "https://seed.draftly.local"

#: Owner and reference together are the matter's natural key, which is what
#: makes a second run a no-op.
SMOKE_MATTER_REFERENCE = "SYN/SMOKE/0001 (synthetic)"
SMOKE_DOCUMENT_FILENAME = "synthetic-deed-of-transfer.pdf"


@dataclass(frozen=True)
class SeedLawyer:
    subject: str
    email: str


LAWYER_A = SeedLawyer(subject="seed-lawyer-a", email="lawyer-a@synthetic.draftly.local")


@dataclass(frozen=True)
class SeedReport:
    profile: str
    lawyer_id: str
    matter_id: str
    created: bool


class SeedIdentityAdapter:
    """Resolves a seed lawyer's subject to that lawyer's claims.

    The seed's stand-in for Clerk, so users are provisioned by the real
    ``AuthService``. It accepts any listed subject as a verified identity, so
    it carries the stub adapter's restriction: local, test and CI only.
    """

    def __init__(self, *lawyers: SeedLawyer) -> None:
        self._lawyers = {lawyer.subject: lawyer for lawyer in lawyers}

    async def validate_token(self, token: str) -> IdentityClaims:
        lawyer = self._lawyers[token]
        return IdentityClaims(
            issuer=SEED_ISSUER,
            subject=lawyer.subject,
            verified_email=lawyer.email,
            provider="seed",
        )


def refuse_unless_disposable_environment() -> None:
    """Seed only where a fake identity is already allowed."""
    environment = get_settings().environment
    if environment not in STUB_IDENTITY_ENVIRONMENTS:
        raise SystemExit(
            f"Refusing to seed synthetic data in environment '{environment}'. "
            f"Allowed: {', '.join(sorted(STUB_IDENTITY_ENVIRONMENTS))}."
        )


async def _existing_matter_id(session: AsyncSession, user_id: str, reference: str) -> str | None:
    result = await session.execute(
        select(MatterRow.id).where(MatterRow.user_id == user_id, MatterRow.reference == reference)
    )
    return result.scalar_one_or_none()


async def seed(session: AsyncSession, profile: str = "smoke") -> SeedReport:
    """Write ``profile`` into ``session`` without committing it.

    The caller commits, so the profile lands whole or not at all.
    """
    if profile not in PROFILES:
        raise ValueError(f"Unknown seed profile '{profile}'. Known: {', '.join(PROFILES)}.")
    refuse_unless_disposable_environment()

    auth = AuthService(
        identity_port=SeedIdentityAdapter(LAWYER_A),
        user_identity_repo=SqlUserIdentityRepository(session),
        user_repo=SqlUserRepository(session),
        audit_port=AuditService(repository=SqlAuditRepository(session)),
    )
    # Idempotent by itself: a linked identity returns its existing user.
    lawyer = await auth.provision_identity(LAWYER_A.subject, correlation_id=CORRELATION_ID)
    if lawyer.role is None:
        raise RuntimeError(f"Seed lawyer {lawyer.id} has no role; provisioning did not finish.")
    ctx = RequestContext(
        actor_id=lawyer.id, account_role=lawyer.role, correlation_id=CORRELATION_ID
    )

    existing = await _existing_matter_id(session, lawyer.id, SMOKE_MATTER_REFERENCE)
    if existing is not None:
        return SeedReport(profile=profile, lawyer_id=lawyer.id, matter_id=existing, created=False)

    matter = await build_matter_service(session).create_matter(
        ctx, CreateMatterInput(reference=SMOKE_MATTER_REFERENCE)
    )

    parties = get_party_service(
        session=session, auth_service=auth, matter_access=build_party_matter_access()
    )
    for party in (SYNTHETIC_PARTY_A, SYNTHETIC_PARTY_B):
        await parties.create_party(ctx, CreatePartyInput(**party))

    await build_ingestion_service(session).upload_source_file(
        user_id=lawyer.id,
        matter_id=matter.id,
        actor_id=lawyer.id,
        correlation_id=CORRELATION_ID,
        filename=SMOKE_DOCUMENT_FILENAME,
        declared_media_type="application/pdf",
        data=synthetic_pdf(pages=1),
    )
    return SeedReport(profile=profile, lawyer_id=lawyer.id, matter_id=matter.id, created=True)


async def _main(profile: str) -> None:
    from src.platform.db.session import get_session_maker

    refuse_unless_disposable_environment()
    async with get_session_maker()() as session:
        report = await seed(session, profile)
        await session.commit()
    outcome = "created" if report.created else "already present, left unchanged"
    print(f"Seed profile '{report.profile}': matter {report.matter_id} {outcome}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo data.")
    parser.add_argument("--profile", choices=PROFILES, default="smoke")
    arguments = parser.parse_args()
    if sys.platform == "win32":
        # psycopg's async mode cannot run on the Windows proactor loop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(arguments.profile))


if __name__ == "__main__":
    main()

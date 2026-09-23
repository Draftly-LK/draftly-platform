"""Grant a trial subscription — `python -m src.cli.grant_trial` (operator tool).

Accounts have no subscription until a Draftly platform admin grants one, and
every gated feature (research, drafting, export, document processing) is denied
without it. This is the same operation as
`POST /api/v1/admin/subscriptions/{userId}/grant-trial`, run from the server:
it goes through `BillingService.grant_trial`, so the platform-admin check, the
"account must be active" rule, the "no existing subscription" rule and the
audit event all apply. Nothing here writes tables directly.

The acting admin must be listed in PLATFORM_ADMIN_USER_IDS. The trial length is
a required argument on purpose: it is a billing policy, not a default.

    python -m src.cli.grant_trial --user usr_... --days 30 [--admin usr_...] [--plan plan_trial_v1]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence

from src.api.deps import build_billing_service
from src.modules.auth.domain.models import Role
from src.modules.billing.application.billing_service import DEFAULT_TRIAL_PLAN_VERSION_ID
from src.platform.config import get_settings
from src.platform.db.session import get_session_maker
from src.platform.db.unit_of_work import UnitOfWork
from src.platform.request_context import RequestContext

# Same plan ensure_trial grants automatically on signup (see PRODUCTION.md,
# "Accounts, plans and gated features") — this tool exists for the accounts
# that predate auto-granting, or that need a different plan or length.
DEFAULT_TRIAL_PLAN = DEFAULT_TRIAL_PLAN_VERSION_ID


def configured_admins(raw: str) -> list[str]:
    """Platform admin ids from PLATFORM_ADMIN_USER_IDS (comma separated)."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m src.cli.grant_trial", description=__doc__)
    parser.add_argument("--user", required=True, help="user id of the account to grant (usr_...)")
    parser.add_argument("--days", required=True, type=int, help="trial length in days (> 0)")
    parser.add_argument("--plan", default=DEFAULT_TRIAL_PLAN, help="active plan version id")
    parser.add_argument("--admin", help="acting platform admin; default: the first configured")
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error("--days must be a positive number of days")
    return args


def resolve_admin(requested: str | None, configured: list[str]) -> str:
    """The acting admin, which must be one PLATFORM_ADMIN_USER_IDS names."""
    if not configured:
        raise SystemExit(
            "PLATFORM_ADMIN_USER_IDS is empty: no one holds platform.administer. "
            "Set it to the Draftly staff user id(s) first."
        )
    if requested is None:
        return configured[0]
    if requested not in configured:
        raise SystemExit(f"{requested} is not listed in PLATFORM_ADMIN_USER_IDS.")
    return requested


async def grant(user_id: str, plan_version_id: str, days: int, admin_id: str) -> str:
    ctx = RequestContext(
        actor_id=admin_id,
        account_role=Role.ADMINISTRATOR,
        correlation_id=f"ops-grant-trial-{uuid.uuid4().hex[:12]}",
    )
    async with get_session_maker()() as session:
        billing = build_billing_service(session)
        async with UnitOfWork(session):
            subscription = await billing.grant_trial(
                ctx, user_id=user_id, plan_version_id=plan_version_id, trial_days=days
            )
    return f"granted {subscription.id}: trial until {subscription.trial_ends_at}"


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    admin = resolve_admin(args.admin, configured_admins(get_settings().platform_admin_user_ids))
    print(asyncio.run(grant(args.user, args.plan, args.days, admin)))


if __name__ == "__main__":
    main()

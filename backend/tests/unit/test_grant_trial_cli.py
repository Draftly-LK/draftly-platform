"""The grant-trial operator tool: argument and admin rules (the grant itself is
BillingService.grant_trial, covered by the billing tests)."""

from __future__ import annotations

import pytest

from src.cli.grant_trial import configured_admins, parse_args, resolve_admin


def test_days_is_required() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--user", "usr_1"])


@pytest.mark.parametrize("days", ["0", "-3"])
def test_days_must_be_positive(days: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--user", "usr_1", "--days", days])


def test_defaults_to_the_seeded_trial_plan() -> None:
    args = parse_args(["--user", "usr_1", "--days", "14"])
    assert (args.user, args.days, args.plan) == ("usr_1", 14, "plan_trial_v1")


def test_configured_admins_are_trimmed() -> None:
    assert configured_admins(" usr_a , ,usr_b ") == ["usr_a", "usr_b"]


def test_no_admin_configured_is_refused() -> None:
    with pytest.raises(SystemExit, match="PLATFORM_ADMIN_USER_IDS is empty"):
        resolve_admin(None, [])


def test_first_configured_admin_is_the_default() -> None:
    assert resolve_admin(None, ["usr_a", "usr_b"]) == "usr_a"


def test_an_unlisted_admin_is_refused() -> None:
    with pytest.raises(SystemExit, match="not listed"):
        resolve_admin("usr_x", ["usr_a"])

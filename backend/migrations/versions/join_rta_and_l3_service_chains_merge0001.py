"""merge0001 — join the RTA and L3 service migration chains

Revision ID: merge0001
Revises: approval0001, notarial0001
Create Date: 2026-08-18

Creates: nothing.

The RTA modules (matter → task → document → verification → check → draft →
approval) and the L3 services (platform outbox → party → notification →
obligations → notarial_register) were built as two independent chains, each
linear on its own branch. Bringing them together leaves Alembic with two heads,
and `alembic upgrade head` refuses to run against more than one. This revision
is the join: no schema change, it only gives the combined history a single head.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "merge0001"
down_revision: str | Sequence[str] | None = ("approval0001", "notarial0001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: this revision exists only to reconcile the two heads."""


def downgrade() -> None:
    """No-op: splitting back into two heads needs no schema change."""

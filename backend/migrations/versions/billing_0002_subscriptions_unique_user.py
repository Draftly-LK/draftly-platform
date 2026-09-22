"""billing_0002 — enforce one subscription per user in the database

`BillingService` (grant_trial, and the new self-serve trial start) only
guarded "one subscription per account" with a check-then-insert in application
code, which is a race under concurrent first requests. A unique index makes it
a database invariant instead.

Revision ID: billing0002
Revises: research0001
"""

from __future__ import annotations

from alembic import op

revision = "billing0002"
down_revision = "research0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ux_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_subscriptions_user_id", table_name="subscriptions")

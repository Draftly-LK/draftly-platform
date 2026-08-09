"""auth_0001 — users and user identities (single-user Gmail auth)

Revision ID: auth0001
Revises:
Create Date: 2026-08-09

Creates: users (with profile fields), user_identities
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "auth0001"
down_revision = None
branch_labels = ("auth",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("account_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("role", sa.String(32), nullable=True),
        sa.Column("notary_registration", sa.String(64), nullable=True),
        sa.Column("jurisdiction", sa.String(128), nullable=True),
        sa.Column("qualifications", sa.String(512), nullable=True),
        sa.Column("professional_titles", sa.String(255), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("certificate_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "user_identities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("verified_email", sa.String(255), nullable=True),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("issuer", "subject", name="uq_user_identity_issuer_subject"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.create_index(
        "uq_user_identities_verified_email",
        "user_identities",
        ["verified_email"],
        unique=True,
        postgresql_where=sa.text("verified_email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_identities_verified_email", table_name="user_identities")
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
    op.drop_table("users")

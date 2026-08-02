"""auth_0001 — initial identity and membership tables

Revision ID: auth0001
Revises:
Create Date: 2026-08-02

Creates: users, user_identities, organisations, organisation_memberships,
         matter_memberships, invitations
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

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

    op.create_table(
        "organisations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(32), nullable=False, server_default="firm"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "organisation_memberships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "organisation_id",
            sa.String(64),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_role", sa.String(32), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "organisation_id", "user_id", name="uq_org_membership_org_user"
        ),
    )
    op.create_index(
        "ix_org_memberships_org_id",
        "organisation_memberships",
        ["organisation_id"],
    )

    op.create_table(
        "matter_memberships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("matter_id", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False, server_default="assignee"),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "organisation_id",
            "matter_id",
            "user_id",
            name="uq_matter_membership_org_matter_user",
        ),
    )
    op.create_index(
        "ix_matter_memberships_org_user",
        "matter_memberships",
        ["organisation_id", "user_id"],
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organisation_id", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("assigned_role", sa.String(32), nullable=False),
        sa.Column("invited_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_expired", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_invitations_org_email",
        "invitations",
        ["organisation_id", "email"],
    )


def downgrade() -> None:
    op.drop_table("invitations")
    op.drop_table("matter_memberships")
    op.drop_table("organisation_memberships")
    op.drop_table("organisations")
    op.drop_table("user_identities")
    op.drop_table("users")

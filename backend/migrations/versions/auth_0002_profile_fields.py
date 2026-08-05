"""auth_0002 — notarial profile fields on users

Revision ID: auth0002
Revises: audit0001
Create Date: 2026-08-05

Adds qualifications, professional_titles, address lines, and phone for the
Draftly profile page. Photo remains Clerk-hosted (imageUrl).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "auth0002"
down_revision = "audit0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("qualifications", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("professional_titles", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("address_line1", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("address_line2", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
    op.drop_column("users", "address_line2")
    op.drop_column("users", "address_line1")
    op.drop_column("users", "professional_titles")
    op.drop_column("users", "qualifications")

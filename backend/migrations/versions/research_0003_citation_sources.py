"""research_0003: record what kind of authority each research citation is.

Research can now cite case law as well as statutes. A citation records its
kind (statute or case), the authority's title and reference (for example
"Registration of Title Act" / "Section 39", or a case name and its citation)
and, for case law, the source link. All four columns are nullable additions:
existing rows are untouched and keep displaying by authority id.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "research0003"
down_revision = "research0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("research_citations", sa.Column("authority_kind", sa.String(16), nullable=True))
    op.add_column("research_citations", sa.Column("title", sa.String(512), nullable=True))
    op.add_column("research_citations", sa.Column("reference", sa.String(256), nullable=True))
    op.add_column("research_citations", sa.Column("source_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("research_citations", "source_url")
    op.drop_column("research_citations", "reference")
    op.drop_column("research_citations", "title")
    op.drop_column("research_citations", "authority_kind")

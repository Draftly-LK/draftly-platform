"""Pin explicit Form 8 selections and successor history."""

import sqlalchemy as sa
from alembic import op

revision = "draft0002"
down_revision = "matteragent0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_forms", sa.Column("scope", sa.JSON(), nullable=True))
    op.add_column("generated_forms", sa.Column("missing_causes", sa.JSON(), nullable=True))
    op.add_column("generated_forms", sa.Column("predecessor_form_id", sa.String(64), nullable=True))


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM generated_forms WHERE scope IS NOT NULL OR predecessor_form_id IS NOT NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot remove scope pins while scoped draft history exists")
    op.drop_column("generated_forms", "predecessor_form_id")
    op.drop_column("generated_forms", "missing_causes")
    op.drop_column("generated_forms", "scope")

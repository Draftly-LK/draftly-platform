"""research_0002: name placeholder conversations after their first question.

Conversations created from "New conversation" kept the placeholder title even
after a question was asked. The service now renames them on the first question;
this backfills the ones created before that change, using the same rule as
`title_from_question` (copied here: migrations do not import application code).
Conversations with no question yet keep the placeholder.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "research0002"
down_revision = "matteragent0002"
branch_labels = None
depends_on = None

DEFAULT_TITLE = "New research"
TITLE_LENGTH = 80


def _title(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= TITLE_LENGTH:
        return text or DEFAULT_TITLE
    cut = text[: TITLE_LENGTH - 1].rsplit(" ", 1)[0] or text[: TITLE_LENGTH - 1]
    return cut + "…"


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT c.id, m.content FROM research_conversations c "
            "JOIN research_messages m ON m.conversation_id = c.id "
            "WHERE c.title = :placeholder AND m.role = 'user' "
            "AND m.sequence = (SELECT MIN(m2.sequence) FROM research_messages m2 "
            "WHERE m2.conversation_id = c.id AND m2.role = 'user')"
        ),
        {"placeholder": DEFAULT_TITLE},
    ).all()
    for conversation_id, content in rows:
        bind.execute(
            sa.text(
                "UPDATE research_conversations SET title = :title "
                "WHERE id = :id AND title = :placeholder"
            ),
            {"title": _title(content), "id": conversation_id, "placeholder": DEFAULT_TITLE},
        )


def downgrade() -> None:
    # Data-only backfill: restoring the placeholder would only lose information.
    pass

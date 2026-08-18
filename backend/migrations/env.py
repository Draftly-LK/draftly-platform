"""Alembic migration environment.

Uses DATABASE_URL_DIRECT (un-pooled) as required for Alembic with Neon
(infrastructure.md §Database — migrations misbehave through a transaction pooler).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import ORM metadata so Alembic can autogenerate migrations.
#
# Most modules share ``platform.db.session.Base``; importing their orm module is
# what registers their tables on that shared metadata. The audit module keeps a
# separate declarative base, so it is listed on its own below.
from src.modules.approval.infrastructure import orm as approval_orm  # noqa: E402, F401
from src.modules.audit.infrastructure.orm import Base as AuditBase  # noqa: E402
from src.modules.auth.infrastructure.orm import Base as AuthBase  # noqa: E402
from src.modules.billing.infrastructure import orm as billing_orm  # noqa: E402, F401
from src.modules.check.infrastructure import orm as check_orm  # noqa: E402, F401
from src.modules.document.infrastructure import orm as document_orm  # noqa: E402, F401
from src.modules.draft.infrastructure import orm as draft_orm  # noqa: E402, F401
from src.modules.matter.infrastructure import orm as matter_orm  # noqa: E402, F401
from src.modules.notarial_register.infrastructure import orm as notarial_orm  # noqa: E402, F401
from src.modules.notification.infrastructure import orm as notification_orm  # noqa: E402, F401
from src.modules.obligations.infrastructure import orm as obligations_orm  # noqa: E402, F401
from src.modules.party.infrastructure import orm as party_orm  # noqa: E402, F401
from src.modules.task.infrastructure import orm as task_orm  # noqa: E402, F401
from src.modules.verification.infrastructure import orm as verification_orm  # noqa: E402, F401
from src.platform.config import get_settings  # noqa: E402
from src.platform.db.session import Base as SharedBase  # noqa: E402
from src.platform.messaging import orm as messaging_orm  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine metadata from all registered modules. Every module except audit binds
# its tables to the shared declarative base, so listing those bases separately
# would hand Alembic the same MetaData object repeatedly.
target_metadata = [SharedBase.metadata, AuditBase.metadata]
assert AuthBase is SharedBase, "auth ORM is expected to use the shared declarative base"


def get_url() -> str:
    """Return the DIRECT (un-pooled) database URL for migrations."""
    settings = get_settings()
    url = settings.database_url_direct
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql+psycopg2://"
    )


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

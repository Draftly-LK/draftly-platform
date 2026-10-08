"""The migration chain, run for real (§5.3).

Each test that migrates gets its own throwaway schema, because one of them
downgrades to base and would otherwise take the shared test schema with it.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.pool import NullPool

import src.platform.config as settings_module
from tests.db.fixtures import BACKEND_ROOT
from tests.db.postgres import database_url

pytestmark = pytest.mark.integration

VERSIONS = Path(BACKEND_ROOT) / "migrations" / "versions"


def _config() -> Config:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "migrations"))
    return config


def _sync(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)


def _scoped(url: str, schema: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}options=-csearch_path%3D{schema}"


@pytest.fixture
def empty_schema(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A fresh schema that alembic targets through DATABASE_URL_DIRECT."""
    url = database_url()
    schema = f"mig_{uuid.uuid4().hex[:10]}"
    admin = create_engine(_sync(url), poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    monkeypatch.setenv("DATABASE_URL_DIRECT", _scoped(url, schema))
    settings_module._settings = None
    try:
        yield schema
    finally:
        settings_module._settings = None
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def _tables(schema: str) -> set[str]:
    engine = create_engine(_sync(_scoped(database_url(), schema)), poolclass=NullPool)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_the_chain_has_exactly_one_head() -> None:
    """Two heads means a bad merge; the next deploy would not know which to run."""
    assert len(ScriptDirectory.from_config(_config()).get_heads()) == 1


def test_upgrade_from_empty_then_downgrade_to_base(empty_schema: str) -> None:
    command.upgrade(_config(), "head")
    assert len(_tables(empty_schema)) > 20

    command.downgrade(_config(), "base")
    assert _tables(empty_schema) == set()


def test_migrations_use_the_direct_url_not_the_pooled_one(
    empty_schema: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neon's pooler breaks migrations; env.py must read DATABASE_URL_DIRECT.

    The pooled URL points nowhere, so reaching the schema proves which URL
    alembic used (DEPLOYMENT_PLAN.md §7.3).
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://synthetic:x@127.0.0.1:1/nowhere")
    settings_module._settings = None

    command.upgrade(_config(), "head")

    assert _tables(empty_schema)


def _import_every_model() -> None:
    """Import each src module that declares a table, so all are registered."""
    for path in sorted((Path(BACKEND_ROOT) / "src").rglob("*.py")):
        if "tests" in path.parts or "__tablename__" not in path.read_text(encoding="utf-8"):
            continue
        importlib.import_module(".".join(path.relative_to(BACKEND_ROOT).with_suffix("").parts))


def _all_model_metadata() -> MetaData:
    _import_every_model()
    from src.modules.audit.infrastructure.orm import Base as AuditBase
    from src.platform.db.session import Base as SharedBase

    merged = MetaData()
    for metadata in (SharedBase.metadata, AuditBase.metadata):
        for table in metadata.tables.values():
            table.to_metadata(merged)
    return merged


ENV_PROBE = """
import ast, importlib
tree = ast.parse(open("migrations/env.py", encoding="utf-8").read())
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src."):
        importlib.import_module(node.module)
        for alias in node.names:
            try:
                importlib.import_module(f"{node.module}.{alias.name}")
            except ModuleNotFoundError:
                pass
from src.modules.audit.infrastructure.orm import Base as AuditBase
from src.platform.db.session import Base as SharedBase
print(" ".join(sorted(set(SharedBase.metadata.tables) | set(AuditBase.metadata.tables))))
"""


def test_env_py_registers_every_table() -> None:
    """migrations/env.py must know every model, or autogenerate proposes
    dropping the tables it cannot see.

    Run in a fresh interpreter that imports only what env.py imports, because
    this process has already registered every model.
    """
    result = subprocess.run(
        [sys.executable, "-c", ENV_PROBE],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    known_to_env = set(result.stdout.split())

    assert set(_all_model_metadata().tables) - known_to_env == set()


def _describe(change: Any) -> str:
    """A stable one-line name for an autogenerate diff entry."""
    if isinstance(change, list):
        return "; ".join(_describe(item) for item in change)
    op = change[0]
    if op in {"add_table", "remove_table"}:
        return f"{op} {change[1].name}"
    if op in {"add_column", "remove_column"}:
        return f"{op} {change[2]}.{change[3].name}"
    if op in {"add_index", "remove_index", "add_constraint", "remove_constraint"}:
        return f"{op} {change[1].table.name}.{change[1].name}"
    if op in {"add_fk", "remove_fk"}:
        columns = ",".join(column.name for column in change[1].columns)
        return f"{op} {change[1].parent.name}.{columns}"
    if op.startswith("modify_"):
        return f"{op} {change[2]}.{change[3]}"
    return repr(change)


def _drift(schema: str) -> list[str]:
    command.upgrade(_config(), "head")
    engine = create_engine(_sync(_scoped(database_url(), schema)), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            return sorted(_describe(c) for c in compare_metadata(context, _all_model_metadata()))
    finally:
        engine.dispose()


#: Model-versus-migration drift that exists today. Each entry needs a decision
#: (is the model or the migration right?) and then a migration or a model fix.
#: Remove an entry when it is fixed; test_the_models_match_the_migrated_schema
#: starts passing once the list is empty.
KNOWN_DRIFT = frozenset(
    {
        "add_fk agent_jobs.session_id",
        "remove_fk agent_jobs.session_id",
        "add_fk agent_messages.session_id",
        "remove_fk agent_messages.session_id",
        "add_fk agent_pending_actions.session_id",
        "remove_fk agent_pending_actions.session_id",
        "add_fk agent_tool_calls.session_id",
        "remove_fk agent_tool_calls.session_id",
        "modify_type api_idempotency_keys.response",
        "add_index beneficial_owners.ix_beneficial_owners_owner_party_id",
        "remove_index identity_evidence.ix_identity_evidence_blind_index",
        "add_index identity_evidence.ix_identity_evidence_identifier_blind_index",
        "remove_index notification_preferences.ix_notification_preferences_org_user",
        "remove_index user_identities.ix_user_identities_user_id",
    }
)


def test_no_new_drift_between_models_and_migrations(empty_schema: str) -> None:
    """A model change must ship with its migration; only known drift is allowed."""
    assert set(_drift(empty_schema)) - KNOWN_DRIFT == set()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="KNOWN_DRIFT is not empty: each entry needs a model or migration fix.",
)
def test_the_models_match_the_migrated_schema(empty_schema: str) -> None:
    assert _drift(empty_schema) == []


#: Migrations that shipped before this check. Both tighten or backfill columns
#: they created (NOT NULL after a backfill, a replaced unique key). Whether each
#: was safe under one release of backward compatibility is the team's call;
#: they are listed so a new migration cannot quietly join them.
PREDATES_THE_ADDITIVE_RULE = frozenset(
    {"notification_0002_outbox_inbox.py", "party_0002_tenant_key.py"}
)

# Reviewed 2026-10-09: one literal metadata backfill, exercised with historical
# and foreign rows by test_scoped_fact_migration. It never rewrites values,
# types or decisions, and only withholds an unproven NIC transaction role.
# This is intentionally a statement fingerprint, not a whole-file exemption.
REVIEWED_METADATA_BACKFILLS = {
    "matter_0002_scoped_fact_review.py": "3efd909ed6d4b6396a4c82c598290fc34b604395575df9504e52b494d4c717c8"
}


def _unsafe_upgrade_steps(filename: str, source: str) -> list[str]:
    upgrade = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
    expected = REVIEWED_METADATA_BACKFILLS.get(filename)
    if expected:
        tree = ast.parse(source)
        function = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade"
        )
        matches = []
        for node in ast.walk(function):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "op"
                and node.func.attr == "execute"
                and len(node.args) == 1
                and not node.keywords
            ):
                continue
            argument = node.args[0]
            if not (
                isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Attribute)
                and isinstance(argument.func.value, ast.Name)
                and argument.func.value.id == "sa"
                and argument.func.attr == "text"
                and len(argument.args) == 1
                and not argument.keywords
                and isinstance(argument.args[0], ast.Constant)
                and isinstance(argument.args[0].value, str)
            ):
                continue
            digest = hashlib.sha256(" ".join(argument.args[0].value.split()).encode()).hexdigest()
            if digest == expected:
                matches.append(ast.get_source_segment(source, node))
        if len(matches) == 1 and matches[0]:
            upgrade = upgrade.replace(matches[0], "", 1)
    destructive = re.compile(
        r"op\.(drop_column|alter_column|drop_table|drop_constraint|rename_table|execute)\("
    )
    return [f"{filename}: {m.group(1)}" for m in destructive.finditer(upgrade)]


def test_no_new_upgrade_step_drops_or_alters_a_column() -> None:
    """One release of backward compatibility (DEPLOYMENT_PLAN.md §7.2).

    A static scan of every upgrade(): the running release must still work
    against the schema the next one migrates to, so upgrades only add.
    """
    offenders: list[str] = []
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name in PREDATES_THE_ADDITIVE_RULE:
            continue
        source = path.read_text(encoding="utf-8")
        offenders += _unsafe_upgrade_steps(path.name, source)

    assert offenders == []


@pytest.mark.parametrize(
    "extra",
    [
        "op.execute(sa.text('DELETE FROM extracted_facts'))",
        "op.execute(query)",
        "op.drop_table('source_files')",
        "op.alter_column('extracted_facts', 'value')",
    ],
)
def test_reviewed_backfill_does_not_allow_additional_or_dynamic_steps(extra: str) -> None:
    filename = "matter_0002_scoped_fact_review.py"
    source = (VERSIONS / filename).read_text(encoding="utf-8")
    modified = source.replace("def upgrade() -> None:", f"def upgrade() -> None:\n    {extra}")
    assert _unsafe_upgrade_steps(filename, modified)
    assert _unsafe_upgrade_steps(filename, source.replace("original_value =", "value ="))


def test_the_exempt_migrations_still_exist() -> None:
    """A stale exemption would hide nothing and mislead the next reader."""
    assert {path.name for path in VERSIONS.glob("*.py")} >= PREDATES_THE_ADDITIVE_RULE

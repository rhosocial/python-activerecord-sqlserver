# docs/examples/migration/02_named_migration.py
"""Class-style migration on SQL Server, driven by MigrationRunner.

The migration system itself is documented in the core migration chapter;
this script only shows the SQL Server wiring. The same class is what this
backend's `named-migration` command resolves by its dotted qualified name:

    python -m rhosocial.activerecord.backend.impl.sqlserver named-migration \
        myapp.migrations.CreateUsers \
        --database myapp --direction up --record-store migrations.json

Requires a reachable SQL Server (see docs/examples/README.md for the
connection environment variables).
"""
import os
import tempfile
from typing import Annotated, Optional

from rhosocial.activerecord.base import UseSqlType
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.migration import (
    JSONFileMigrationRecordStore,
    MigrationContext,
    MigrationDirection,
    MigrationRunner,
    NamedMigration,
)
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    @classmethod
    def table_name(cls) -> str:
        return "users"

    id: Annotated[Optional[int], UseSqlType(IntegerType())] = None
    name: Annotated[str, UseSqlType(VarCharType(length=64))]


class CreateUsers(NamedMigration):
    """A single class-style migration; the version is its unique identifier."""

    version = "v001_create_users"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(User.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(User.drop_table_statement(if_exists=True, backend=ctx.backend))


def make_config() -> SQLServerConnectionConfig:
    """Build the connection config for this example from environment variables."""
    return SQLServerConnectionConfig(
        host=os.environ.get("SQLSERVER_HOST", "localhost"),
        port=int(os.environ.get("SQLSERVER_PORT", "1433")),
        database=os.environ.get("SQLSERVER_DATABASE", "test_db"),
        username=os.environ.get("SQLSERVER_USERNAME", "sa"),
        password=os.environ.get("SQLSERVER_PASSWORD", ""),
        driver=os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
        trust_server_certificate=(
            os.environ.get("SQLSERVER_TRUST_SERVER_CERTIFICATE", "false").lower() == "true"
        ),
    )


def main() -> None:
    rec_path = tempfile.mktemp(suffix=".json")
    backend = SQLServerBackend(connection_config=make_config())
    backend.connect()
    try:
        # Version gates consult the detected server version; refresh it first.
        backend.introspect_and_adapt()

        store = JSONFileMigrationRecordStore(rec_path)
        # NamedMigration FQNs are dotted: module.Class (not module:function).
        fqn = f"{__name__}.CreateUsers"
        runner = MigrationRunner(fqn)

        up = runner.run(backend, MigrationDirection.UP, record_store=store)
        print("== UP ==")
        print("  version:", up.version, "success:", up.success)
        print("  applied versions:", [r.version for r in store.get_applied()])

        down = runner.run(backend, MigrationDirection.DOWN, record_store=store)
        print("\n== DOWN ==")
        print("  version:", down.version, "success:", down.success)
        print("  applied versions after rollback:", [r.version for r in store.get_applied()])
    finally:
        backend.disconnect()
        if os.path.exists(rec_path):
            os.remove(rec_path)


if __name__ == "__main__":
    main()

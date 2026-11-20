# docs/examples/migration/01_function_migration.py
"""Function-style migrations on SQL Server: dry run -> UP -> DOWN.

Requires a reachable SQL Server (see docs/examples/README.md for the
connection environment variables). Uses this backend's own config/backend
classes and a JSONFileMigrationRecordStore. The migration system itself is
documented in the core migration chapter.
"""
import os
import tempfile
from typing import Annotated, Optional

from rhosocial.activerecord.base import UseSqlType
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.migration import (
    MigrationDirection,
    migration,
    run_migration_group,
)
from rhosocial.activerecord.backend.migration.record import JSONFileMigrationRecordStore
from rhosocial.activerecord.model import ActiveRecord


# ActiveRecord already mixes in MigrationMixin, so create_table_statement()
# and drop_table_statement() are available on every model.
class User(ActiveRecord):
    @classmethod
    def table_name(cls) -> str:
        return "users"

    id: Annotated[Optional[int], UseSqlType(IntegerType())] = None
    name: Annotated[str, UseSqlType(VarCharType(length=64))]


@migration("v001_create_users", description="create the initial users table on SQL Server")
def create_users(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(User.create_table_statement(backend=ctx.backend))
    else:
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
        print("Server version:", backend.dialect.get_server_version())

        store = JSONFileMigrationRecordStore(rec_path)
        fqn = f"{__name__}:create_users"

        # 1) dry run — renders T-SQL through this backend's dialect, writes nothing
        preview = run_migration_group(backend, [fqn], dry_run=True)
        print("\n== dry run ==")
        print("  statements:", preview.dry_run_total)
        for label, sql, params in preview.dry_run_sql:
            print(f"  [{label}] {sql}")
        print("  records written:", preview.records_written)

        # 2) real UP — applies the DDL inside a transaction and writes a record
        up = run_migration_group(backend, [fqn], record_store=store)
        print("\n== UP ==")
        print("  applied:", up.applied, "versions:", up.versions)
        print("  records written:", up.records_written)
        print("  applied versions:", [r.version for r in store.get_applied()])

        # 3) DOWN — rolls back and clears the applied version
        down = run_migration_group(
            backend, [fqn], direction=MigrationDirection.DOWN, record_store=store
        )
        print("\n== DOWN ==")
        print("  rolled back:", down.rolled_back)
        print("  applied versions after rollback:", [r.version for r in store.get_applied()])
    finally:
        backend.disconnect()
        if os.path.exists(rec_path):
            os.remove(rec_path)


if __name__ == "__main__":
    main()

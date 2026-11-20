# docs/examples/03_introspection_and_partition.py
"""Introspect a SQL Server database and preview partition maintenance.

All partition operations here use dry runs, so the script reads the catalogue
but does not change schema. Run against a scratch database (see
docs/examples/README.md).
"""
import os
from datetime import date

from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
    SQLServerPartitionMaintenance,
    SQLServerPartitionPlan,
)


def make_backend() -> SQLServerBackend:
    config = SQLServerConnectionConfig(
        host=os.environ.get("SQLSERVER_HOST", "localhost"),
        port=int(os.environ.get("SQLSERVER_PORT", "1433")),
        database=os.environ.get("SQLSERVER_DATABASE", "test_db"),
        username=os.environ.get("SQLSERVER_USERNAME", "sa"),
        password=os.environ.get("SQLSERVER_PASSWORD", ""),
        driver=os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
    )
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    backend.introspect_and_adapt()
    return backend


def show_introspection(backend: SQLServerBackend) -> None:
    introspector = backend.introspector

    info = introspector.get_database_info()
    print("Database:", info.name, info.version, info.collation)

    for schema in introspector.list_schemas():
        print("Schema:", schema.name, "owner:", schema.owner)

    for table in introspector.list_tables():
        print("Table:", table.name, table.table_type.value)

    for column in introspector.list_columns("example_users"):
        print("Column:", column.name, column.data_type_full, column.nullable.value)

    if backend.dialect.supports_unused_indexes_detection():
        for index in introspector.list_unused_indexes():
            print("Unused index:", f"{index.table_name}.{index.index_name}")


def show_partition_plan(backend: SQLServerBackend) -> None:
    plan = SQLServerPartitionPlan(
        function="pf_example_logs",
        data_type="DATE",
        boundaries=(date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)),
        scheme="ps_example_logs",
        all_filegroup="PRIMARY",
    )
    maintenance = SQLServerPartitionMaintenance(backend)

    # Catalogue report: functions, schemes, tables and per-partition ranges.
    report = maintenance.list(plan, table="example_logs", schema="dbo")
    print("Partition functions:", report.functions)
    print("Ranges:", report.ranges)

    # Checks only; never repairs.
    report = maintenance.validate(plan, table="example_logs", schema="dbo")
    print("Issues:", report.issues)

    # Render the SPLIT statements without executing them (SQL Server DDL
    # auto-commits, so a dry run is the safe way to review the plan).
    report = maintenance.ensure(plan, dry_run=True)
    print("Planned operations:", report.operations)


def main() -> None:
    backend = make_backend()
    try:
        show_introspection(backend)
        show_partition_plan(backend)
    finally:
        backend.disconnect()


if __name__ == "__main__":
    main()

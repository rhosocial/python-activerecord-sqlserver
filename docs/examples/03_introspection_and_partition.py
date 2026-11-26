# docs/examples/03_introspection_and_partition.py
"""Introspect a SQL Server database and preview partition suggestions.

The example only reads the catalogue and renders the dialect's suggested
expression chains; it executes no partition DDL. Run against a scratch
database (see docs/examples/README.md).
"""

import os
from datetime import date

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.statements import PartitionByRangeClause
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
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

    for schema in introspector.list_schema_infos():
        print("Schema:", schema.name, "owner:", schema.owner)

    for table in introspector.list_tables():
        print("Table:", table.name, table.table_type.value)

    for column in introspector.list_columns("example_users"):
        print("Column:", column.name, column.data_type_full, column.nullable.value)

    if backend.dialect.supports_unused_indexes_detection():
        for index in introspector.list_unused_indexes():
            print("Unused index:", f"{index.table_name}.{index.index_name}")


def show_partition_plan(backend: SQLServerBackend) -> None:
    dialect = backend.dialect
    plan = SQLServerPartitionPlan(
        function="pf_example_logs",
        data_type="DATE",
        boundaries=(date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)),
        scheme="ps_example_logs",
        all_filegroup="PRIMARY",
    )
    fields = plan.__dict__
    strategy = PartitionByRangeClause(dialect, [Column(dialect, "created_at")])
    preview = {
        "build": dialect.suggest_partition_build(strategy, plan),
        "table_drop": dialect.suggest_partition_table_drop(strategy, plan),
        "add": dialect.suggest_partition_add(strategy, {**fields, "boundary": date(2026, 3, 15)}),
        "drop": dialect.suggest_partition_drop(strategy, {**fields, "boundary": date(2026, 1, 1)}),
        "retention": dialect.suggest_partition_retention(
            strategy, {**fields, "cutoff": date(2026, 2, 1)}
        ),
    }
    for name, suggestion in preview.items():
        operations = suggestion.operations
        if operations is False:
            print(f"{name}: not supported by SQL Server")
        elif operations is None:
            print(f"{name}: no action needed")
        else:
            print(f"{name}:")
            for operation in operations:
                print("  ", operation.to_sql()[0])


def main() -> None:
    backend = make_backend()
    try:
        show_introspection(backend)
        show_partition_plan(backend)
    finally:
        backend.disconnect()


if __name__ == "__main__":
    main()

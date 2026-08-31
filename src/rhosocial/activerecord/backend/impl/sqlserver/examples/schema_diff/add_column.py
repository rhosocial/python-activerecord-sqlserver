"""
Schema diff: detect an added column.

SQL Server ALTER TABLE ADD always appends columns at the end of the table.
The SQLServerSchemaDiffer checks ordinal_position to detect column reordering.

Supported versions: SQL Server 2012+
"""

import os
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    host=os.getenv("SQLSERVER_HOST", "localhost"),
    port=int(os.getenv("SQLSERVER_PORT", "1433")),
    database=os.getenv("SQLSERVER_DATABASE", "test_db"),
    username=os.getenv("SQLSERVER_USERNAME", "sa"),
    password=os.getenv("SQLSERVER_PASSWORD", ""),
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import (
    DropTableExpression, CreateTableExpression, ColumnDefinition,
    ColumnConstraint, ColumnConstraintType,
    AlterTableExpression, AddColumn,
)
from rhosocial.activerecord.backend.expression.types import (
    IntegerType, VarCharType,
)

expr = DropTableExpression(dialect, "users", if_exists=True)
sql, params = expr.to_sql()
backend.execute(sql, params)

# Baseline table: ID, NAME
expr = CreateTableExpression(
    dialect=dialect, table="users", columns=[
        ColumnDefinition("id", IntegerType(),
            constraints=[
                ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
            ]),
        ColumnDefinition("name", VarCharType(length=100)),
    ]
)
sql, params = expr.to_sql()
backend.execute(sql, params)

from rhosocial.activerecord.backend.schema import (
    SyncSchemaSnapshotBuilder, SchemaDiffer,
)

builder = SyncSchemaSnapshotBuilder(
    introspector=backend.introspector,
    dialect=dialect,
)
snap_before = builder.build()

# Add a column
alter = AlterTableExpression(
    dialect=dialect, table_name="users",
    actions=[
        AddColumn(dialect, column=ColumnDefinition("email", VarCharType(length=255))),
    ],
)
sql, params = alter.to_sql()
backend.execute(sql, params)

snap_after = builder.build()

from rhosocial.activerecord.backend.impl.sqlserver.schema import SQLServerSchemaDiffer
differ = SQLServerSchemaDiffer()
diff = differ.compare(snap_before, snap_after)

assert "users" in diff.modified_tables
table_diff = diff.table_diffs["users"]
assert table_diff.is_modified
added_cols = [cd for cd in table_diff.column_diffs if cd.is_added]
assert len(added_cols) == 1
assert added_cols[0].column_name == "email"

print("Schema diff detected added column 'email'.")
backend.disconnect()

"""
Batch insert multiple rows efficiently.
"""

import os

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)

config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', '11434')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
    driver=os.environ.get('SQLSERVER_DRIVER', 'SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=(
        os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
    ),
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import CreateTableExpression
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

create_table = CreateTableExpression(
    dialect=dialect,
    table_name='batch_users',
    columns=[
        ColumnDefinition('id', 'INT', constraints=[
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
        ]),
        ColumnDefinition('name', 'NVARCHAR(100)', constraints=[
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        ]),
        ColumnDefinition('email', 'NVARCHAR(200)'),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params, options=ddl_options)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import InsertExpression, ValuesSource
from rhosocial.activerecord.backend.expression.core import Literal

# Prepare batch data
users = [
    ('Alice', 'alice@example.com'),
    ('Bob', 'bob@example.com'),
    ('Charlie', 'charlie@example.com'),
]

# Create batch insert with multiple value rows
insert_expr = InsertExpression(
    dialect=dialect,
    into='batch_users',
    columns=['name', 'email'],
    source=ValuesSource(
        dialect,
        [[Literal(dialect, name), Literal(dialect, email)] for name, email in users],
    ),
)

sql, params = insert_expr.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params)
print(f"Affected rows: {result.affected_rows}")

# Verify insertion
from rhosocial.activerecord.backend.expression import QueryExpression, TableExpression, Column

query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, 'id'), Column(dialect, 'name'), Column(dialect, 'email')],
    from_=TableExpression(dialect, 'batch_users'),
)
sql, params = query.to_sql()
dql_options = ExecutionOptions(stmt_type=StatementType.DQL)
result = backend.execute(sql, params, options=dql_options)
print(f"Inserted rows:")
for row in result.data or []:
    print(f" {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression import DropTableExpression

drop_expr = DropTableExpression(dialect=dialect, table_name='batch_users', if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params, options=ddl_options)

backend.disconnect()

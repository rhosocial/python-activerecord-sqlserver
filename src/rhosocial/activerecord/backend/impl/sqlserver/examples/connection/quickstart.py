"""
Quick Start: Connect to SQL Server and execute queries.

This example demonstrates:
1. How to establish a connection to SQL Server
2. How to view connection information
3. How to execute expression-based queries
4. How to access query results and handle transactions
"""

import os

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    InsertExpression,
    QueryExpression,
    TableExpression,
    ValuesSource,
    WhereClause,
)
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', '11434')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', ''),
    driver=os.environ.get('SQLSERVER_DRIVER', 'SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=(
        os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
    ),
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

dql_options = ExecutionOptions(stmt_type=StatementType.DQL)
ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)


def execute_expression(expression, options=None):
    """Execute an expression and print the generated SQL."""
    sql, params = expression.to_sql()
    print(f"SQL: {sql}")
    print(f"Params: {params}")
    return backend.execute(sql, params, options=options)


# Create demo tables
users_table = CreateTableExpression(
    dialect=dialect,
    table='quickstart_users',
    columns=[
        ColumnDefinition(
            'id',
            'INT',
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
            ],
        ),
        ColumnDefinition(
            'name',
            'NVARCHAR(100)',
            constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)],
        ),
        ColumnDefinition('status', 'NVARCHAR(20)'),
    ],
    if_not_exists=True,
)
execute_expression(users_table, ddl_options)

logs_table = CreateTableExpression(
    dialect=dialect,
    table='quickstart_logs',
    columns=[
        ColumnDefinition(
            'id',
            'INT',
            constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
            ],
        ),
        ColumnDefinition(
            'message',
            'NVARCHAR(255)',
            constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)],
        ),
    ],
    if_not_exists=True,
)
execute_expression(logs_table, ddl_options)

# Seed demo data
insert_users = InsertExpression(
    dialect=dialect,
    into='quickstart_users',
    columns=['name', 'status'],
    source=ValuesSource(
        dialect,
        [
            [Literal(dialect, 'Alice'), Literal(dialect, 'active')],
            [Literal(dialect, 'Bob'), Literal(dialect, 'inactive')],
        ],
    ),
)
execute_expression(insert_users)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
# Create a simple SELECT query with WHERE clause
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, 'id'),
        Column(dialect, 'name'),
        Column(dialect, 'status'),
    ],
    from_=TableExpression(dialect, 'quickstart_users'),
    where=WhereClause(
        dialect,
        condition=ComparisonPredicate(
            dialect,
            '=',
            Column(dialect, 'status'),
            Literal(dialect, 'active'),
        ),
    ),
)

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = execute_expression(query, dql_options)

print(f"Result data: {result.data}")
print(f"Rows: {result.affected_rows}")
print(f"Duration: {result.duration:.3f}s")

if result.data:
    row = result.data[0]
    print(f"Value from first row: {row['name']}")

# ============================================================
# SECTION: Business Logic - Parameterized Query
# ============================================================
# Use complex predicates with AND/OR
from rhosocial.activerecord.backend.expression.predicates import LogicalPredicate

filtered_query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, 'id'),
        Column(dialect, 'name'),
        Column(dialect, 'status'),
    ],
    from_=TableExpression(dialect, 'quickstart_users'),
    where=WhereClause(
        dialect,
        condition=LogicalPredicate(
            dialect,
            'AND',
            ComparisonPredicate(dialect, '=', Column(dialect, 'id'), Literal(dialect, 1)),
            ComparisonPredicate(dialect, '=', Column(dialect, 'status'), Literal(dialect, 'active')),
        ),
    ),
)

# ============================================================
# SECTION: Execution
# ============================================================
result = execute_expression(filtered_query, dql_options)
print(f"Parameterized query result: {result.data}")

# ============================================================
# SECTION: Business Logic - Transaction
# ============================================================
# Use transaction context manager for automatic commit/rollback
with backend.transaction():
    insert_log = InsertExpression(
        dialect=dialect,
        into='quickstart_logs',
        columns=['message'],
        source=ValuesSource(dialect, [[Literal(dialect, 'quickstart transaction')]]),
    )
    execute_expression(insert_log)

    logs_query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, 'id'), Column(dialect, 'message')],
        from_=TableExpression(dialect, 'quickstart_logs'),
    )
    result = execute_expression(logs_query, dql_options)
    print(f"Transaction result: {result.data}")

# ============================================================
# SECTION: Business Logic - Error Handling
# ============================================================
try:
    invalid_query = QueryExpression(
        dialect=dialect,
        select=[Column(dialect, 'id')],
        from_=TableExpression(dialect, 'nonexistent_table'),
    )
    execute_expression(invalid_query, dql_options)
except Exception as error:
    print(f"Error: {error}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
drop_logs = DropTableExpression(
    dialect=dialect, table='quickstart_logs', if_exists=True
)
execute_expression(drop_logs, ddl_options)

drop_users = DropTableExpression(
    dialect=dialect, table='quickstart_users', if_exists=True
)
execute_expression(drop_users, ddl_options)

backend.disconnect()

# ============================================================
# SECTION: Summary
# ============================================================
# Key points:
# 1. Create SQLServerConnectionConfig with environment variables or defaults
# 2. Create SQLServerBackend with the config and call backend.connect()
# 3. Use expressions to create schema, insert data, and query data
# 4. Use backend.transaction() for transaction control
# 5. Access QueryResult.data for returned rows
# 6. Disconnect when done

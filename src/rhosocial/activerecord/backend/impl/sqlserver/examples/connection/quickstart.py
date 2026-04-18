"""Quick Start: Connect to SQL Server and execute queries.

This example demonstrates:
1. How to establish a connection to SQL Server
2. How to view connection information
3. How to execute expression-based queries
4. How to access query results and handle transactions

Connection configuration is loaded from environment variables with defaults:
- SQLSERVER_HOST: Server hostname (default: localhost)
- SQLSERVER_PORT: Server port (default: 1433)
- SQLSERVER_DATABASE: Database name (default: test_db)
- SQLSERVER_USERNAME: Username (default: sa)
- SQLSERVER_PASSWORD: Password (default: Password123!)
- SQLSERVER_DRIVER: ODBC driver (default: ODBC Driver 17 for SQL Server)
"""

import os

# ============================================================
# SECTION: Connection Setup
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

# Load configuration from environment variables with defaults
config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', '1433')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
    driver=os.environ.get('SQLSERVER_DRIVER', 'ODBC Driver 17 for SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true',
    autocommit=False,
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


def create_demo_tables():
    """Create demo tables for the example."""
    users_table = CreateTableExpression(
        dialect=dialect,
        table_name='users',
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
    )
    execute_expression(users_table, ddl_options)

    logs_table = CreateTableExpression(
        dialect=dialect,
        table_name='logs',
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
    )
    execute_expression(logs_table, ddl_options)


def seed_demo_data():
    """Insert demo data into tables."""
    insert_users = InsertExpression(
        dialect=dialect,
        into='users',
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


create_demo_tables()
seed_demo_data()

# ============================================================
# SECTION: View Connection Information
# ============================================================
print(f"Server: {config.host}:{config.port}")
print(f"Database: {config.database}")
print(f"Driver: {config.driver}")
print(f"SQL Server Version: {backend.get_server_version()}")

# ============================================================
# SECTION: Execute Queries
# ============================================================
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, 'id'),
        Column(dialect, 'name'),
        Column(dialect, 'status'),
    ],
    from_=TableExpression(dialect, 'users'),
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
result = execute_expression(query, dql_options)

# ============================================================
# SECTION: Access Query Results
# ============================================================
print(f"Result data: {result.data}")
print(f"Rows: {result.affected_rows}")
print(f"Duration: {result.duration:.3f}s")

if result.data:
    row = result.data[0]
    print(f"Value from first row: {row['name']}")

# ============================================================
# SECTION: Execute Parameterized Queries (Recommended)
# ============================================================
filtered_query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, 'id'),
        Column(dialect, 'name'),
        Column(dialect, 'status'),
    ],
    from_=TableExpression(dialect, 'users'),
    where=WhereClause(
        dialect,
        condition=ComparisonPredicate(
            dialect,
            '=',
            Column(dialect, 'id'),
            Literal(dialect, 1),
        )
        & ComparisonPredicate(
            dialect,
            '=',
            Column(dialect, 'status'),
            Literal(dialect, 'active'),
        ),
    ),
)
result = execute_expression(filtered_query, dql_options)
print(f"Parameterized query result: {result.data}")

# ============================================================
# SECTION: Handle Transactions
# ============================================================
with backend.transaction():
    insert_log = InsertExpression(
        dialect=dialect,
        into='logs',
        columns=['message'],
        source=ValuesSource(dialect, [[Literal(dialect, 'quickstart transaction')]]),
    )
    execute_expression(insert_log)

logs_query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, 'id'), Column(dialect, 'message')],
    from_=TableExpression(dialect, 'logs'),
)
result = execute_expression(logs_query, dql_options)
print(f"Transaction result: {result.data}")

# ============================================================
# SECTION: SQL Server Specific Features - OUTPUT Clause
# ============================================================
# SQL Server uses OUTPUT clause instead of RETURNING
insert_with_output = InsertExpression(
    dialect=dialect,
    into='logs',
    columns=['message'],
    source=ValuesSource(dialect, [[Literal(dialect, 'OUTPUT example')]]),
    returning=['id', 'message'],  # dialect will convert to OUTPUT
)
result = execute_expression(insert_with_output, dql_options)
print(f"OUTPUT clause result: {result.data}")

# ============================================================
# SECTION: Error Handling
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
# SECTION: Disconnect
# ============================================================
drop_logs = DropTableExpression(dialect=dialect, table_name='logs', if_exists=True)
execute_expression(drop_logs, ddl_options)

drop_users = DropTableExpression(dialect=dialect, table_name='users', if_exists=True)
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
# 6. SQL Server uses OUTPUT clause for RETURNING functionality
# 7. Disconnect when done

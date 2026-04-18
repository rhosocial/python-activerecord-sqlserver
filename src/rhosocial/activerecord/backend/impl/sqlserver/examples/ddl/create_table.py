"""
Create a table with primary key, IDENTITY, and constraints.
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
    port=int(os.environ.get('SQLSERVER_PORT', '1433')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
    driver=os.environ.get('SQLSERVER_DRIVER', 'ODBC Driver 17 for SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=(
        os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
    ),
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import IndexDefinition

columns = [
    ColumnDefinition(
        name='id',
        data_type='INT',
        constraints=[
            ColumnConstraint(
                constraint_type=ColumnConstraintType.PRIMARY_KEY,
                is_auto_increment=True,
            ),
        ],
    ),
    ColumnDefinition(
        name='name',
        data_type='NVARCHAR(100)',
        constraints=[
            ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL),
        ],
    ),
    ColumnDefinition(
        name='email',
        data_type='NVARCHAR(200)',
        constraints=[
            ColumnConstraint(constraint_type=ColumnConstraintType.UNIQUE),
        ],
    ),
    ColumnDefinition(
        name='created_at',
        data_type='DATETIME2',
    ),
]

indexes = [
    IndexDefinition(
        name='idx_users_email',
        columns=['email'],
    ),
]

create_expr = CreateTableExpression(
    dialect=dialect,
    table_name='users',
    columns=columns,
    indexes=indexes,
    if_not_exists=True,
    dialect_options={},
)

sql, params = create_expr.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
result = backend.execute(sql, params, options=ddl_options)
print("Table created: users")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression import DropTableExpression

drop_expr = DropTableExpression(dialect=dialect, table_name='users', if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params, options=ddl_options)

backend.disconnect()

"""
Create a table with primary key, IDENTITY, and constraints.
"""

import os

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

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

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (
    CreateTableStatement,
    ColumnDefinition,
    ColumnConstraint,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnNotNullConstraint,
    ColumnPrimaryKeyConstraint,
    ColumnUniqueConstraint,
    IndexDefinition,
)

columns = [
    ColumnDefinition(
        name='id',
        data_type='INT',
        constraints=[
            ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect, is_auto_increment=True)),
        ],
    ),
    ColumnDefinition(
        name='name',
        data_type='NVARCHAR(100)',
        constraints=[
            ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
        ],
    ),
    ColumnDefinition(
        name='email',
        data_type='NVARCHAR(200)',
        constraints=[
            ColumnConstraint(dialect, branch=ColumnUniqueConstraint(dialect)),
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

create_expr = CreateTableStatement(
    dialect=dialect,
    table=Table(dialect, 'users'),
    columns=columns,
    indexes=indexes,
    if_not_exists=True,
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
from rhosocial.activerecord.backend.expression import DropTableStatement

drop_expr = DropTableStatement(dialect=dialect, table=Table(dialect, 'users'), if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params, options=ddl_options)

backend.disconnect()
